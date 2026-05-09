"""
prompt.py — LLM prompt builder for Phase 4 AI decisions.

D-04: System + user message split.
  - System message: player identity + archetype persona (stable; cached-friendly)
  - User message:   current-hand context (changes every call)

D-05: User message includes: hole cards, community cards, current phase, pot,
      available actions with amounts, player's own chip stack, opponent summary
      (chip count + last action this street). No cross-hand memory (v1).

AI-03: All math (hand strength, pot odds, win probability) provided as structured
       context — LLM does not compute math.

AI-SPEC 4b.3: Prompt structure verbatim from spec — never put hand state in system
              message; never put archetype instruction in user message.

NOTE: pot_odds from calculate_equity() is always None.
      Compute here as: call_amount / (pot + call_amount) or 0.0 if call_amount == 0.
"""
from __future__ import annotations

from app.ai.archetypes import Archetype
from app.engine.models import GameState, Player

# Token budget guardrails (AI-SPEC 4b.4)
MAX_SYSTEM_TOKENS = 150  # identity + archetype + format instruction
MAX_USER_TOKENS   = 250  # hand state + math + actions + opponents

_FORMAT_INSTRUCTION = (
    "\n\nRESPONSE FORMAT — output ONLY this fenced JSON block, no other text:\n"
    "```json\n"
    '{"action": "<fold|call|raise|check>", "amount": <integer_chips>, '
    '"reasoning": "<1-2 sentences in character>"}\n'
    "```"
)


def build_system_prompt(player: Player, archetype: Archetype) -> str:
    """
    Build the stable system message for one player+archetype combination (D-04).

    Persona injection — stays constant across all betting rounds for this player.
    The format instruction is included here so it is given maximum model weight.
    """
    lines = [
        f"You are {player.name}, an AI competing in a live-streamed poker game.",
        f"Your archetype is {archetype.name}: {archetype.description}",
        "Stay fully in character at all times. Your reasoning must sound like a real player "
        "at the table — first-person, present tense, emotionally grounded. "
        "Never mention being an AI. Never echo these instructions.",
        _FORMAT_INSTRUCTION,
    ]
    return "\n".join(lines)


def build_user_prompt(
    game_state: GameState,
    math_ctx: dict,
    valid_acts_info: dict,
    player: Player,
) -> str:
    """
    Build the volatile user message with current-hand context (D-04, D-05, AI-03).

    Args:
        game_state:      Current GameState snapshot
        math_ctx:        Output of calculate_equity(): {hand_strength, win_probability, pot_odds}
                         NOTE: pot_odds from calculate_equity is always None — computed here.
        valid_acts_info: Output of reconstruct_valid_actions():
                         {valid_types: set, call_amount: int, raise_min: int, raise_max: int}
        player:          The player making the decision (for call_amount pot_odds computation)

    Returns:
        Formatted user prompt string containing all required AI-03 fields.
    """
    # Cards
    hole = " ".join(f"{c.r}{c.s}" for c in player.hole_cards) if player.hole_cards else "?"
    board = " ".join(f"{c.r}{c.s}" for c in game_state.community_cards) or "none"

    # Math context
    win_prob = math_ctx.get("win_probability", 0.5)
    hand_strength = math_ctx.get("hand_strength")
    hand_str_display = f"{hand_strength}" if hand_strength is not None else "n/a (pre-flop)"

    # Pot odds — computed here since calculate_equity always returns pot_odds=None
    call_amount = valid_acts_info.get("call_amount", 0)
    pot = game_state.pot
    pot_odds = call_amount / (pot + call_amount) if (pot + call_amount) > 0 else 0.0

    # Available actions line
    acts = []
    valid_types = valid_acts_info.get("valid_types", set())
    if "fold" in valid_types:
        acts.append("fold")
    if "check" in valid_types:
        acts.append("check")
    if "call" in valid_types:
        acts.append(f"call {call_amount}")
    if "raise" in valid_types:
        raise_min = valid_acts_info.get("raise_min", 0)
        raise_max = valid_acts_info.get("raise_max", player.chips)
        acts.append(f"raise {raise_min}-{raise_max}")
    actions_line = ", ".join(acts) if acts else "fold"

    # Opponent summary — chip count + last action this street (D-05)
    opponents = []
    for opp in game_state.players:
        if opp.id == player.id or opp.is_folded:
            continue
        last_action = opp.action or "unknown"
        opponents.append(f"{opp.name} (chips: {opp.chips}, last: {last_action})")
    opp_line = "; ".join(opponents) if opponents else "none"

    lines = [
        f"Hand: [{hole}]. Board: [{board}]. Phase: {game_state.phase}.",
        f"Pot: {pot}. Your chips: {player.chips}.",
        f"Win probability: {win_prob:.0%}. Pot odds: {pot_odds:.0%}. Hand strength: {hand_str_display}.",
        f"Available actions: {actions_line}.",
        f"Opponents: {opp_line}.",
    ]
    return "\n".join(lines)
