"""
decision.py — LLM decision function implementation for Phase 4.

make_llm_decision_fn(): Factory that returns a closure matching DecisionFn signature.
  The closure curries extra context (archetypes, redis, budget, circuit) so game.py
  sees only: async def _(player: Player, game_state: GameState) -> Action.

Pattern: partial/closure from game_loop.py's `partial(publish, redis_client)` convention.

Critical correctness rules (from RESEARCH.md):
  - Action field is `action_type` NOT `type` (AI-SPEC code samples contain error)
  - ActionType is a Literal string union — no .RAISE attribute access
  - asyncio.CancelledError MUST always be re-raised — never swallowed
  - valid_actions() requires BettingRoundState (not available) — use reconstruct_valid_actions()
  - chunk.choices[0].delta.content is None on first/last chunks — guard with `if delta:`
  - num_retries silently ignored with stream=True — circuit breaker handles retries

NOTE on card conversion: cards.py exposes new_card(r, s) for unicode→treys.
  card_to_treys() does NOT exist in cards.py. Use new_card(card.r, card.s) directly.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import TYPE_CHECKING

from litellm import acompletion
from litellm.exceptions import (
    Timeout as APITimeoutError, RateLimitError, APIError, BadRequestError, AuthenticationError,
)
from pydantic import ValidationError

from app.ai.archetypes import Archetype
from app.ai.budget import BudgetTracker, CircuitBreaker
from app.ai.models import LLMDecisionResponse
from app.ai.prompt import build_system_prompt, build_user_prompt
from app.broadcast.publisher import publish_reasoning
from app.engine.cards import new_card
from app.engine.models import Action, Player, GameState

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Regex: extracts the JSON object from a ```json ... ``` fenced block (D-06)
_JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)

INDIVIDUAL_TIMEOUT_S = 2.0  # per-call hard deadline (D-11)


def reconstruct_valid_actions(player: Player, game_state: GameState) -> dict:
    """
    Reconstruct valid actions and amounts from GameState alone (Pattern 2, RESEARCH.md).

    valid_actions() in game.py requires BettingRoundState which is not stored in GameState.
    This reconstruction is safe because game.py enforces true min-raise limits at execution
    time regardless of the approximate raise_min returned here.

    Returns dict with keys:
      valid_types: set of valid action type strings
      call_amount: chips required to call (0 if can check)
      raise_min:   approximate minimum raise total (game.py enforces exact min)
      raise_max:   player.chips + player.bet (all-in cap)
    """
    current_bet = game_state.current_bet  # populated by game.py in Plan 04
    call_amount = max(0, current_bet - player.bet)
    can_raise = player.chips > call_amount

    valid = {"fold"}
    amounts = {}

    if call_amount == 0:
        valid.add("check")
        amounts["call_amount"] = 0
    else:
        valid.add("call")
        amounts["call_amount"] = min(call_amount, player.chips)  # all-in cap

    if can_raise:
        big_blind_approx = 20  # approximate; game.py enforces actual min raise
        amounts["raise_min"] = current_bet + big_blind_approx
        amounts["raise_max"] = player.chips + player.bet  # all-in
        valid.add("raise")

    return {
        "valid_types": valid,
        "call_amount": amounts.get("call_amount", 0),
        "raise_min": amounts.get("raise_min", 0),
        "raise_max": amounts.get("raise_max", player.chips),
    }


def make_llm_decision_fn(
    archetypes: dict[str, Archetype],
    redis_client,
    budget: BudgetTracker,
    circuit: CircuitBreaker,
    player_models: dict[str, str] | None = None,  # player_id -> litellm model string (Plan 04)
):
    """
    Factory returning a DecisionFn closure for LLM-driven decisions (D-14).

    The closure captures archetypes, redis_client, budget, circuit, and player_models.
    The returned function signature matches DecisionFn exactly:
        async def _(player: Player, game_state: GameState) -> Action

    Args:
        player_models: Optional dict mapping player_id -> LiteLLM model string.
                       When provided (Plan 04+), used directly for model routing.
                       Falls back to _get_model() for backward compat (tests without dict).

    Usage in game_loop.py:
        decision_fn = make_llm_decision_fn(
            archetypes, redis_client, budget, circuit,
            player_models=session.player_models,
        )
        await session.run(n_hands=10, decision_fn=decision_fn, broadcast_fn=...)
    """
    async def llm_decision_fn(player: Player, game_state: GameState) -> Action:
        archetype = archetypes.get(player.id)
        if archetype is None:
            # Player not in archetypes dict (shouldn't happen in normal operation)
            logger.warning("No archetype for player %s — using fold fallback", player.id)
            return Action(action_type="fold")

        # Reconstruct valid actions from GameState (Pattern 2 — BettingRoundState unavailable)
        valid_acts_info = reconstruct_valid_actions(player, game_state)

        # Build math context from calculate_equity
        from app.engine.poker_math import calculate_equity
        hole_treys = [new_card(c.r, c.s) for c in player.hole_cards]
        board_treys = [new_card(c.r, c.s) for c in game_state.community_cards]
        num_opponents = sum(1 for p in game_state.players if p.id != player.id and not p.is_folded)
        math_ctx = calculate_equity(
            hole_treys, board_treys,
            num_opponents=max(1, num_opponents),
            n_simulations=500,  # fast enough for 2s budget; accuracy sufficient for prompts
        )

        # Circuit breaker: skip LLM if provider has tripped (D-16)
        # player_models dict (Plan 04) takes priority; fall back to _get_model() for tests
        litellm_model = (player_models or {}).get(player.id) or _get_model(player)
        if circuit.is_open(litellm_model):
            logger.info("[%s] Circuit open — using fallback immediately", player.name)
            fallback_action = await _fallback_action(
                player, archetype, valid_acts_info, math_ctx,
                reason="circuit open", redis_client=redis_client, game_state=game_state,
            )
            _append_reasoning_to_state(
                game_state=game_state, player_id=player.id,
                text=f"[{player.name} circuit open — acting on instinct]",
                phase=game_state.phase, action=fallback_action.action_type, amount=fallback_action.amount,
            )
            return fallback_action

        # Build prompts (D-04, D-05)
        system_prompt = build_system_prompt(player, archetype)
        user_prompt = build_user_prompt(game_state, math_ctx, valid_acts_info, player)

        # LLM call with streaming + dual timeout (AI-SPEC Pitfall 1)
        raw_text: str | None = await _call_llm_streaming(
            litellm_model, system_prompt, user_prompt,
            player.id, game_state.phase, redis_client,
        )

        if raw_text is None:
            # Failure already logged in _call_llm_streaming
            circuit.record_error(litellm_model)
            fallback_action = await _fallback_action(
                player, archetype, valid_acts_info, math_ctx,
                reason="timed out", redis_client=redis_client, game_state=game_state,
            )
            # Append finalized ReasoningEntry for late-joiner snapshot correctness (OQ-3)
            _append_reasoning_to_state(
                game_state=game_state, player_id=player.id,
                text=f"[{player.name} timed out — acting on instinct]",
                phase=game_state.phase, action=fallback_action.action_type, amount=fallback_action.amount,
            )
            return fallback_action

        # Parse and validate LLM response (AI-04)
        circuit.record_success(litellm_model)
        parsed = _parse_response(raw_text, player.name)
        if parsed is None:
            fallback_action = await _fallback_action(
                player, archetype, valid_acts_info, math_ctx,
                reason="parse error", redis_client=redis_client, game_state=game_state,
            )
            _append_reasoning_to_state(
                game_state=game_state, player_id=player.id,
                text=f"[{player.name} parse error — acting on instinct]",
                phase=game_state.phase, action=fallback_action.action_type, amount=fallback_action.amount,
            )
            return fallback_action

        # Validate action is in valid actions (AI-04)
        if parsed.action not in valid_acts_info["valid_types"]:
            logger.warning(
                "[%s] LLM returned invalid action '%s' — valid: %s",
                player.name, parsed.action, valid_acts_info["valid_types"],
            )
            fallback_action = await _fallback_action(
                player, archetype, valid_acts_info, math_ctx,
                reason="invalid action", redis_client=redis_client, game_state=game_state,
            )
            _append_reasoning_to_state(
                game_state=game_state, player_id=player.id,
                text=f"[{player.name} invalid action — acting on instinct]",
                phase=game_state.phase, action=fallback_action.action_type, amount=fallback_action.amount,
            )
            return fallback_action

        # Clamp raise amount to all-in cap (Section 6 online guardrail)
        amount = parsed.amount
        if parsed.action == "raise" and amount > player.chips:
            logger.debug(
                "[%s] Clamping raise %d -> %d (all-in cap)", player.name, amount, player.chips,
            )
            amount = player.chips

        # Token budget tracking (D-15)
        prompt_tokens = (len(system_prompt) + len(user_prompt)) // 4
        completion_tokens = len(raw_text) // 4
        budget.record(litellm_model, prompt_tokens, completion_tokens)

        # CORRECT: action_type field, not type; Literal string, not Enum
        final_action = Action(action_type=parsed.action, amount=amount)

        # BLOCKER 1 FIX: Append finalized ReasoningEntry to game_state.reasoning
        # BEFORE returning, so the subsequent publish() snapshot in game_loop.py
        # carries this entry. Late-joiners see completed reasoning via snapshot. (D-03, OQ-3)
        _append_reasoning_to_state(
            game_state=game_state,
            player_id=player.id,
            text=raw_text,
            phase=game_state.phase,
            action=final_action.action_type,
            amount=final_action.amount,
        )
        return final_action

    return llm_decision_fn


async def _call_llm_streaming(
    model: str,
    system_prompt: str,
    user_prompt: str,
    player_id: str,
    phase: str,
    redis_client,
) -> str | None:
    """
    Call LiteLLM with streaming. Publishes each token delta via publish_reasoning().
    Returns full response text or None on any failure.

    Double-layer timeout (AI-SPEC Pitfall 1):
      - asyncio.wait_for: hard asyncio wall
      - timeout= on acompletion: HTTP connection cleanup

    AUTHORITATIVE: This plan's CancelledError handling is the implementation contract.
    The RESEARCH.md code example omits the stream-iteration CancelledError re-raise.
    This plan's version is authoritative: CancelledError inside the async-for loop
    MUST be re-raised immediately (see: except asyncio.CancelledError: raise).
    """
    try:
        stream = await asyncio.wait_for(
            acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                stream=True,
                max_tokens=300,           # hard cap — prevents token blowout (INFRA-05)
                temperature=0.7,
                timeout=INDIVIDUAL_TIMEOUT_S,  # HTTP-level cleanup (Pitfall 1)
            ),
            timeout=INDIVIDUAL_TIMEOUT_S,      # asyncio hard wall (Pitfall 1)
        )
    except asyncio.CancelledError:
        raise  # NEVER swallow CancelledError — game loop shutdown signal
    except (asyncio.TimeoutError, APITimeoutError) as exc:
        logger.warning("[%s] LLM timeout: %s", model, exc)
        return None
    except (RateLimitError, APIError, BadRequestError, AuthenticationError) as exc:
        logger.warning("[%s] LLM error (%s): %s", model, type(exc).__name__, exc)
        return None
    except Exception as exc:
        logger.warning("[%s] LLM unexpected error: %s", model, exc)
        return None

    full_text = ""
    try:
        async for chunk in stream:
            # None guard: first chunk has role announcement (content=None),
            # last chunk has finish_reason="stop" (content=None) — Pitfall 2
            if delta := chunk.choices[0].delta.content:
                full_text += delta
                if redis_client is not None:
                    await publish_reasoning(redis_client, player_id, phase, delta, done=False)
    except asyncio.CancelledError:
        raise  # NEVER swallow CancelledError
    except Exception as exc:
        logger.warning("[%s] Stream iteration error: %s", model, exc)
        return None

    # Signal end of this player's reasoning stream to SSE clients (D-02)
    if redis_client is not None:
        await publish_reasoning(redis_client, player_id, phase, "", done=True)
    return full_text


def _parse_response(raw_text: str, player_name: str) -> LLMDecisionResponse | None:
    """
    Extract fenced JSON block and validate with Pydantic (D-06).
    Returns None on any failure — caller engages fallback.
    """
    match = _JSON_FENCE_RE.search(raw_text)
    if not match:
        logger.warning(
            "[%s] No fenced JSON block in LLM response. raw[:200]=%r",
            player_name, raw_text[:200],
        )
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        logger.warning("[%s] JSONDecodeError at pos %d: %s", player_name, exc.pos, exc.msg)
        return None
    try:
        return LLMDecisionResponse.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            logger.warning(
                "[%s] ValidationError field=%s msg=%s value=%r",
                player_name, err["loc"], err["msg"], err.get("input"),
            )
        return None


async def _fallback_action(
    player: Player,
    archetype: Archetype,
    valid_acts_info: dict,
    math_ctx: dict,
    reason: str,
    redis_client=None,
    game_state: GameState | None = None,
) -> Action:
    """
    Deterministic decision based on hand strength + archetype bias (D-11).
    Publishes a single fallback notice to the ReasoningPanel (D-12).

    Archetype bias thresholds (RESEARCH.md Pattern 2 calibration):
      - Raise if win_probability >= archetype.raise_freq AND raise is valid
      - Call if win_probability >= archetype.hand_looseness AND call is valid
      - Check if check is valid (free action — always take it)
      - Fold otherwise
    """
    win_prob = math_ctx.get("win_probability", 0.5)
    valid_types = valid_acts_info.get("valid_types", {"fold"})

    if win_prob >= archetype.raise_freq and "raise" in valid_types:
        raise_min = valid_acts_info.get("raise_min", 0)
        action = Action(action_type="raise", amount=raise_min)
    elif win_prob >= archetype.hand_looseness and "call" in valid_types:
        call_amount = valid_acts_info.get("call_amount", 0)
        action = Action(action_type="call", amount=call_amount)
    elif "check" in valid_types:
        action = Action(action_type="check")
    else:
        action = Action(action_type="fold")

    # Publish fallback notice — character-consistent, not a technical error string (D-12)
    if redis_client is not None and game_state is not None:
        notice = f"[{player.name} {reason} — acting on instinct]"
        await publish_reasoning(
            redis_client,
            player_id=player.id,
            phase=game_state.phase,
            delta=notice,
            done=True,
        )

    logger.info(
        "[%s] Fallback engaged (reason=%s, win_prob=%.2f) -> %s",
        player.name, reason, win_prob, action.action_type,
    )
    return action


def _get_model(player: Player) -> str:
    """
    Get the LiteLLM model string for a player.

    Player objects from session.py are initialized from models.config.json.
    The litellm_model is stored in a parallel dict on GameSession (Plan 04).
    For now, derive from player.id via the config file.

    IMPORTANT: This function is called at decision time. The player object
    does not carry litellm_model directly (Player Pydantic model has no such field —
    adding it would break game.py validation). The model string is loaded from
    models.config.json at session init and passed via a closure dict in Plan 04.

    Temporary: derive from id lookup. Plan 04 replaces this with closure injection.
    """
    import pathlib
    _config_path = pathlib.Path(__file__).parent.parent.parent.parent / "models.config.json"
    try:
        configs = json.loads(_config_path.read_text())
        for cfg in configs:
            if cfg["id"] == player.id:
                return cfg["litellmModel"]
    except Exception:
        pass
    # Fallback if id not found (shouldn't happen in production)
    return "openai/gpt-4o"


def _append_reasoning_to_state(
    game_state: GameState,
    player_id: str,
    text: str,
    phase: str,
    action: str,
    amount: int,
) -> None:
    """
    Append a finalized ReasoningEntry to game_state.reasoning after each player decision.

    BLOCKER 1 FIX (Open Question 3 RESOLVED): The publish() call in game_loop.py occurs AFTER
    decision_fn() returns. Appending the finalized entry here ensures the Redis snapshot
    (written by publish()) captures it. Late-joining viewers see all completed reasoning
    via the SNAPSHOT_KEY, not just real-time streaming deltas.

    Call this in every return path of llm_decision_fn — both success and all fallback cases.
    """
    from app.ai.models import ReasoningEntry
    entry = ReasoningEntry(
        player_id=player_id,
        text=text,
        phase=phase,
        streaming=False,       # finalized — streaming is complete
        action=action,
        amount=amount,
    )
    game_state.reasoning.append(entry)
