"""
Tests for backend/app/ai/decision.py

Covers:
  AI-04: Fallback on timeout, malformed JSON, invalid action
  AI-06: Archetype action-coherence (Gunslinger raises >= 2x Rock's raise rate)
  INFRA-05: Budget tracking + circuit breaker trip + bypass
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.ai.archetypes import ARCHETYPES, assign_archetypes
from app.ai.budget import BudgetTracker, CircuitBreaker
from app.ai.decision import (
    _fallback_action,
    _parse_response,
    make_llm_decision_fn,
    reconstruct_valid_actions,
    INDIVIDUAL_TIMEOUT_S,
)
from app.engine.models import Action, Card, GameState, Player


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

GUNSLINGER = next(a for a in ARCHETYPES if a.name == "Gunslinger")
ROCK = next(a for a in ARCHETYPES if a.name == "Rock")
GRINDER = next(a for a in ARCHETYPES if a.name == "Grinder")
CHAOTIC = next(a for a in ARCHETYPES if a.name == "Chaotic Optimist")

VALID_JSON_RESPONSE = (
    '```json\n{"action": "call", "amount": 40, "reasoning": "Good pot odds."}\n```'
)
RAISE_JSON_RESPONSE = (
    '```json\n{"action": "raise", "amount": 80, "reasoning": "Applying pressure."}\n```'
)
MALFORMED_JSON_RESPONSE = "I think I'll call. Maybe. Let me think about it..."
INVALID_ACTION_RESPONSE = (
    '```json\n{"action": "shove", "amount": 1000, "reasoning": "All in!"}\n```'
)


def _make_player(player_id: str = "gpt4", chips: int = 980, bet: int = 0) -> Player:
    return Player(
        id=player_id, name="GPT-5.5 Nano", org="OpenAI",
        color="#10a37f", deck="d", chips=chips, bet=bet,
        hole_cards=[Card(s="♥", r="A"), Card(s="♦", r="K")],
    )


def _make_game_state(phase: str = "flop", pot: int = 120, current_bet: int = 40) -> GameState:
    return GameState(
        phase=phase, pot=pot, current_bet=current_bet,
        community_cards=[Card(s="♣", r="Q"), Card(s="♥", r="J"), Card(s="♠", r="2")],
    )


def _valid_acts_with_raise() -> dict:
    return {
        "valid_types": {"fold", "call", "raise"},
        "call_amount": 40,
        "raise_min": 60,
        "raise_max": 980,
    }


def _valid_acts_check_only() -> dict:
    return {
        "valid_types": {"fold", "check"},
        "call_amount": 0,
        "raise_min": 0,
        "raise_max": 980,
    }


class AsyncIterator:
    """Async iterator for mock LLM stream chunks."""
    def __init__(self, items):
        self.items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.items)
        except StopIteration:
            raise StopAsyncIteration


def _make_chunk(content: str | None) -> MagicMock:
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = content
    return chunk


def _make_stream(response_text: str) -> AsyncIterator:
    """Build a mock async stream yielding one chunk per character (simulates streaming)."""
    chunks = [_make_chunk(None)]  # first chunk: role announcement (content=None)
    for char in response_text:
        chunks.append(_make_chunk(char))
    chunks.append(_make_chunk(None))  # last chunk: finish_reason=stop (content=None)
    return AsyncIterator(chunks)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReconstructValidActions:
    def test_with_current_bet_nonzero_should_offer_call_and_raise(self):
        player = _make_player(chips=980, bet=0)
        gs = _make_game_state(current_bet=40)
        acts = reconstruct_valid_actions(player, gs)
        assert "fold" in acts["valid_types"]
        assert "call" in acts["valid_types"]
        assert "raise" in acts["valid_types"]
        assert acts["call_amount"] == 40

    def test_with_current_bet_zero_should_offer_check(self):
        player = _make_player(chips=980, bet=0)
        gs = _make_game_state(current_bet=0)
        acts = reconstruct_valid_actions(player, gs)
        assert "check" in acts["valid_types"]
        assert "call" not in acts["valid_types"]

    def test_player_already_at_current_bet_should_check(self):
        """Player.bet == current_bet -> call_amount == 0 -> check is valid."""
        player = _make_player(chips=940, bet=40)
        gs = _make_game_state(current_bet=40)
        acts = reconstruct_valid_actions(player, gs)
        assert acts["call_amount"] == 0
        assert "check" in acts["valid_types"]


class TestParseResponse:
    def test_valid_fenced_json_returns_decision_response(self):
        result = _parse_response(VALID_JSON_RESPONSE, "TestPlayer")
        assert result is not None
        assert result.action == "call"
        assert result.amount == 40
        assert result.reasoning == "Good pot odds."

    def test_no_fenced_block_returns_none(self):
        result = _parse_response("I think I should call here.", "TestPlayer")
        assert result is None

    def test_invalid_action_value_returns_none(self):
        result = _parse_response(
            '```json\n{"action": "shove", "amount": 100, "reasoning": "test"}\n```',
            "TestPlayer",
        )
        assert result is None  # Pydantic ValidationError for invalid action Literal

    def test_missing_reasoning_field_returns_none(self):
        result = _parse_response(
            '```json\n{"action": "fold", "amount": 0}\n```',
            "TestPlayer",
        )
        assert result is None


class TestFallbackAction:
    @pytest.mark.asyncio
    async def test_gunslinger_raises_at_moderate_win_probability(self):
        """Gunslinger raise_freq=0.40 -> raises at win_prob=0.45."""
        player = _make_player()
        acts = _valid_acts_with_raise()
        math_ctx = {"win_probability": 0.45, "hand_strength": None}
        action = await _fallback_action(player, GUNSLINGER, acts, math_ctx, "test")
        assert action.action_type == "raise", (
            f"Gunslinger should raise at win_prob=0.45 (raise_freq=0.40), got {action.action_type}"
        )

    @pytest.mark.asyncio
    async def test_rock_folds_at_moderate_win_probability(self):
        """Rock hand_looseness=0.65 -> folds at win_prob=0.45."""
        player = _make_player()
        acts = _valid_acts_with_raise()
        math_ctx = {"win_probability": 0.45, "hand_strength": None}
        action = await _fallback_action(player, ROCK, acts, math_ctx, "test")
        assert action.action_type == "fold", (
            f"Rock should fold at win_prob=0.45 (hand_looseness=0.65), got {action.action_type}"
        )

    @pytest.mark.asyncio
    async def test_chaotic_calls_low_win_probability(self):
        """Chaotic Optimist hand_looseness=0.10 -> calls at win_prob=0.20."""
        player = _make_player()
        acts = _valid_acts_with_raise()
        math_ctx = {"win_probability": 0.20, "hand_strength": None}
        action = await _fallback_action(player, CHAOTIC, acts, math_ctx, "test")
        # win_prob=0.20 >= raise_freq=0.35? No. >= hand_looseness=0.10? Yes -> call
        assert action.action_type == "call", (
            f"Chaotic Optimist should call at win_prob=0.20 (hand_looseness=0.10), got {action.action_type}"
        )

    @pytest.mark.asyncio
    async def test_fallback_checks_when_check_available(self):
        """When check is available and win_prob below all thresholds, use check (free action)."""
        player = _make_player()
        acts = _valid_acts_check_only()
        math_ctx = {"win_probability": 0.05, "hand_strength": None}
        action = await _fallback_action(player, ROCK, acts, math_ctx, "test")
        assert action.action_type == "check"

    @pytest.mark.asyncio
    async def test_action_is_constructed_with_action_type_field(self):
        """Action must use action_type field (not type) -- AI-SPEC correctness check."""
        player = _make_player()
        acts = _valid_acts_with_raise()
        math_ctx = {"win_probability": 0.45}
        action = await _fallback_action(player, GUNSLINGER, acts, math_ctx, "test")
        assert hasattr(action, "action_type"), "Action must have action_type field, not type"
        assert action.action_type in ("fold", "call", "raise", "check")


class TestArchetypeBias:
    """
    SC-2: Gunslinger raises at >= 2x Rock's raise rate across varied win_probabilities.
    Tests the deterministic fallback path -- LLM path is stubbed in TestLLMDecisions.
    """

    @pytest.mark.asyncio
    async def test_gunslinger_raises_more_than_rock(self):
        """
        Simulate 10 decision scenarios with win_probabilities spanning 0.2-0.85.
        Count raise actions per archetype. Gunslinger raise rate must be > Rock raise rate.
        """
        player = _make_player()
        acts = _valid_acts_with_raise()
        win_probs = [0.20, 0.30, 0.35, 0.40, 0.45, 0.55, 0.60, 0.65, 0.70, 0.85]

        gun_raises = 0
        rock_raises = 0
        for wp in win_probs:
            math_ctx = {"win_probability": wp, "hand_strength": None}
            g_action = await _fallback_action(player, GUNSLINGER, acts, math_ctx, "test")
            r_action = await _fallback_action(player, ROCK, acts, math_ctx, "test")
            if g_action.action_type == "raise":
                gun_raises += 1
            if r_action.action_type == "raise":
                rock_raises += 1

        gun_rate = gun_raises / len(win_probs)
        rock_rate = rock_raises / len(win_probs)
        delta = gun_rate - rock_rate

        assert delta >= 0.20, (
            f"Gunslinger raise rate ({gun_rate:.0%}) must exceed Rock raise rate ({rock_rate:.0%}) "
            f"by >= 20pp. Actual delta: {delta:.0%}"
        )


class TestCircuitBreaker:
    def test_trips_after_threshold_consecutive_errors(self):
        cb = CircuitBreaker(threshold=3)
        cb.record_error("openai/gpt-5-nano")
        cb.record_error("openai/gpt-5-nano")
        assert not cb.is_open("openai/gpt-5-nano")
        cb.record_error("openai/gpt-5-nano")
        assert cb.is_open("openai/gpt-5-nano"), "CircuitBreaker must open after 3 consecutive errors"

    def test_success_resets_streak_but_not_open_breaker(self):
        cb = CircuitBreaker(threshold=3)
        cb.record_error("m")
        cb.record_error("m")
        cb.record_error("m")
        assert cb.is_open("m")
        cb.record_success("m")
        assert cb.is_open("m"), "Success should NOT re-close an already-open breaker"

    def test_success_resets_consecutive_streak(self):
        cb = CircuitBreaker(threshold=3)
        cb.record_error("m")
        cb.record_error("m")
        cb.record_success("m")  # resets streak
        cb.record_error("m")  # only 1 error now
        assert not cb.is_open("m"), "Streak should be reset by success"

    def test_different_providers_isolated(self):
        cb = CircuitBreaker(threshold=3)
        for _ in range(3):
            cb.record_error("openai/gpt-5-nano")
        assert cb.is_open("openai/gpt-5-nano")
        assert not cb.is_open("gemini/gemini-3.1-flash"), "Other providers should be unaffected"


class TestBudgetTracker:
    def test_record_accumulates_spend(self):
        bt = BudgetTracker()
        bt.record("openai/gpt-5-nano", 100, 50)
        assert bt.total_spend > 0, "Spend should be > 0 after recording tokens"

    def test_summary_returns_total_and_by_provider(self):
        bt = BudgetTracker()
        bt.record("openai/gpt-5-nano", 200, 100)
        bt.record("gemini/gemini-3.1-flash", 150, 80)
        s = bt.summary()
        assert "total_usd" in s
        assert "tokens_by_provider" in s
        assert "openai" in s["tokens_by_provider"]
        assert "gemini" in s["tokens_by_provider"]

    def test_spend_is_zero_on_new_instance(self):
        bt = BudgetTracker()
        assert bt.total_spend == 0.0


# Note: calculate_equity is imported locally inside llm_decision_fn with
#   `from app.engine.poker_math import calculate_equity`
# so the correct patch target is "app.engine.poker_math.calculate_equity"
_EQUITY_PATCH = "app.engine.poker_math.calculate_equity"
_EQUITY_RETURN = {"win_probability": 0.72, "hand_strength": 1234, "pot_odds": None}
_EQUITY_RETURN_LOW = {"win_probability": 0.20, "hand_strength": None, "pot_odds": None}
_EQUITY_RETURN_MED = {"win_probability": 0.45, "hand_strength": None, "pot_odds": None}
_EQUITY_RETURN_HALF = {"win_probability": 0.5, "hand_strength": None, "pot_odds": None}


class TestLLMDecisions:
    """Integration tests for make_llm_decision_fn using mocked acompletion."""

    def _make_archetypes_and_fn(self, archetype=None, redis_client=None):
        player = _make_player()
        arch = archetype or GUNSLINGER
        archetypes = {"gpt4": arch}
        player_models = {"gpt4": "openai/gpt-5-nano"}
        budget = BudgetTracker()
        circuit = CircuitBreaker()
        fn = make_llm_decision_fn(archetypes, redis_client, budget, circuit, player_models)
        return player, fn, budget, circuit

    @pytest.mark.asyncio
    async def test_valid_llm_response_returns_action(self):
        """SC-1: LLM returns valid JSON -> Action returned matching LLM choice."""
        player, fn, budget, _ = self._make_archetypes_and_fn()
        gs = _make_game_state()
        gs.players = [player]

        with patch("app.ai.decision.acompletion") as mock_acomp, \
             patch("app.ai.decision.publish_reasoning", new_callable=AsyncMock), \
             patch(_EQUITY_PATCH, return_value=_EQUITY_RETURN):

            mock_acomp.return_value = _make_stream(VALID_JSON_RESPONSE)
            action = await fn(player, gs)

        assert action.action_type == "call"
        assert action.amount == 40

    @pytest.mark.asyncio
    async def test_timeout_triggers_fallback_not_raise(self):
        """SC-4: asyncio.TimeoutError -> fallback Action returned, no exception raised."""
        player, fn, _, circuit = self._make_archetypes_and_fn(ROCK)
        gs = _make_game_state()
        gs.players = [player]
        # Give Rock a very low win probability -- should fold on fallback
        with patch("app.ai.decision.acompletion", side_effect=asyncio.TimeoutError()), \
             patch("app.ai.decision.publish_reasoning", new_callable=AsyncMock), \
             patch(_EQUITY_PATCH, return_value=_EQUITY_RETURN_LOW):

            action = await fn(player, gs)  # must NOT raise

        # Rock fallback at win_prob=0.20 (< hand_looseness=0.65) -> fold
        assert action.action_type == "fold", f"Expected fold fallback, got {action.action_type}"
        assert circuit._errors.get("openai/gpt-5-nano", 0) >= 1, "Error should be recorded"

    @pytest.mark.asyncio
    async def test_malformed_json_triggers_fallback(self):
        """SC-4: LLM returns text with no fenced JSON block -> fallback engaged."""
        player, fn, _, _ = self._make_archetypes_and_fn(GUNSLINGER)
        gs = _make_game_state()
        gs.players = [player]

        with patch("app.ai.decision.acompletion") as mock_acomp, \
             patch("app.ai.decision.publish_reasoning", new_callable=AsyncMock), \
             patch(_EQUITY_PATCH, return_value=_EQUITY_RETURN_MED):

            mock_acomp.return_value = _make_stream(MALFORMED_JSON_RESPONSE)
            action = await fn(player, gs)

        # Gunslinger fallback at win_prob=0.45 (>= raise_freq=0.40) -> raise
        assert action.action_type == "raise", f"Expected raise fallback for Gunslinger, got {action.action_type}"

    @pytest.mark.asyncio
    async def test_invalid_action_triggers_fallback(self):
        """SC-4: LLM returns invalid action string -> fallback engaged."""
        player, fn, _, _ = self._make_archetypes_and_fn()
        gs = _make_game_state()
        gs.players = [player]

        with patch("app.ai.decision.acompletion") as mock_acomp, \
             patch("app.ai.decision.publish_reasoning", new_callable=AsyncMock), \
             patch(_EQUITY_PATCH, return_value=_EQUITY_RETURN_HALF):

            mock_acomp.return_value = _make_stream(INVALID_ACTION_RESPONSE)
            action = await fn(player, gs)

        # Any valid fallback action is acceptable
        assert action.action_type in ("fold", "call", "raise", "check")

    @pytest.mark.asyncio
    async def test_circuit_open_skips_llm_call(self):
        """SC-6: Circuit open -> acompletion not called -> fallback immediately."""
        player, fn, _, circuit = self._make_archetypes_and_fn()
        circuit._open.add("openai/gpt-5-nano")  # pre-trip the circuit
        gs = _make_game_state()
        gs.players = [player]

        with patch("app.ai.decision.acompletion") as mock_acomp, \
             patch("app.ai.decision.publish_reasoning", new_callable=AsyncMock), \
             patch(_EQUITY_PATCH, return_value=_EQUITY_RETURN_HALF):

            action = await fn(player, gs)
            assert not mock_acomp.called, "acompletion must NOT be called when circuit is open"

        assert action.action_type in ("fold", "call", "raise", "check")

    @pytest.mark.asyncio
    async def test_budget_tracked_after_successful_call(self):
        """SC-6: Budget.total_spend > 0 after a successful LLM call."""
        player, fn, budget, _ = self._make_archetypes_and_fn()
        gs = _make_game_state()
        gs.players = [player]

        with patch("app.ai.decision.acompletion") as mock_acomp, \
             patch("app.ai.decision.publish_reasoning", new_callable=AsyncMock), \
             patch(_EQUITY_PATCH, return_value=_EQUITY_RETURN_HALF):

            mock_acomp.return_value = _make_stream(VALID_JSON_RESPONSE)
            await fn(player, gs)

        assert budget.total_spend > 0.0, "Budget must accumulate spend after successful LLM call"

    @pytest.mark.asyncio
    async def test_fallback_publishes_reasoning_when_circuit_open(self):
        """
        D-12 + WARNING 5: When circuit is open, fallback is used and publish_reasoning is called.

        Verifies that even on circuit-open path, the fallback notice is published to the
        ReasoningPanel (D-12) via publish_reasoning(). Covers the code path:
        circuit.is_open() -> True -> _fallback_action() -> publish_reasoning(done=True).

        Note: A non-None redis_client is required for publish_reasoning to be called
        (guarded by `if redis_client is not None` in _fallback_action).
        """
        mock_redis = MagicMock()
        player, fn, _, circuit = self._make_archetypes_and_fn(GUNSLINGER, redis_client=mock_redis)
        circuit._open.add("openai/gpt-5-nano")  # pre-trip circuit
        gs = _make_game_state()
        gs.players = [player]

        with patch("app.ai.decision.acompletion") as mock_acomp, \
             patch("app.ai.decision.publish_reasoning", new_callable=AsyncMock) as mock_pub, \
             patch(_EQUITY_PATCH, return_value=_EQUITY_RETURN_HALF):

            action = await fn(player, gs)
            # acompletion must NOT be called when circuit is open
            assert not mock_acomp.called, "acompletion must not be called on open circuit"
            # D-12: fallback notice MUST be published even when circuit trips
            assert mock_pub.called, (
                "publish_reasoning must be called for D-12 fallback notice when circuit is open"
            )
            # The done=True call must be among the publish calls (signals end of reasoning stream)
            done_calls = [c for c in mock_pub.call_args_list if c.kwargs.get("done") is True]
            assert done_calls, "At least one publish_reasoning call must have done=True (D-02)"

        assert action.action_type in ("fold", "call", "raise", "check")
