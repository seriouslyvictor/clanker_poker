"""
models.py — Pydantic game state models for the LLM Poker Arena.

JSON contract: GameState.model_dump(by_alias=True) produces the exact camelCase
shape that app/_components/types.ts GameState interface expects.

alias_generator=to_camel is applied ONLY to Player and GameState — the models
with snake_case fields that must serialize to camelCase. Card (fields: s, r) and
Action do not need aliasing.

Phase 3 SSE: serialize game state with game_state.model_dump(by_alias=True).
Phase 4 LLM: DecisionFn type alias is the plug-in seam for LLM decision functions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Awaitable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------

class Card(BaseModel):
    """Single playing card. s = suit unicode symbol, r = rank string."""
    s: str  # suit unicode symbol: '♠', '♥', '♦', '♣'
    r: str  # rank string: 'A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'
    # No alias_generator needed — 's' and 'r' are already valid in both Python and JSON.


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------

ActionType = Literal['fold', 'call', 'raise', 'check']


class Action(BaseModel):
    """A player decision: action type plus optional raise amount."""
    action_type: ActionType
    amount: int = 0  # chips for raise; 0 for fold / call / check


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

class Player(BaseModel):
    """Player state. Serializes to camelCase JSON matching types.ts Player."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str                          # Phase 2: 'player-0' through 'player-3'. Phase 4: ModelId.
    name: str
    org: str
    color: str
    deck: str
    chips: int
    hole_cards: list[Card] = Field(default_factory=list)  # → holeCards in JSON
    action: Optional[ActionType] = None
    bet: int = 0                     # chips committed this street
    is_folded: bool = False          # → isFolded in JSON
    is_active: bool = True           # → isActive in JSON
    is_winner: bool = False          # → isWinner in JSON


# ---------------------------------------------------------------------------
# GameState
# ---------------------------------------------------------------------------

class GameState(BaseModel):
    """Full game state snapshot. Serializes to camelCase JSON matching types.ts GameState."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    phase: str                        # 'pre-flop', 'flop', 'turn', 'river', 'showdown'
    pot: int
    community_cards: list[Card] = Field(default_factory=list)  # → communityCards in JSON
    players: list[Player] = Field(default_factory=list)
    show_cards: bool = False          # → showCards in JSON
    current_bet: int = 0             # → currentBet in JSON; highest live bet this street (Phase 4)
    reasoning: list = Field(default_factory=list)  # list[ReasoningEntry] — Phase 4
    winner: Optional[int] = None     # player index, or None if no winner yet
    winner_hand: str = ""            # → winnerHand in JSON (e.g. 'Full House')


# ---------------------------------------------------------------------------
# BettingRoundState — internal game engine state, not serialized
# ---------------------------------------------------------------------------

@dataclass
class BettingRoundState:
    """
    Mutable state for one betting round.
    Not a Pydantic model — internal to game.py, never serialized.
    """
    current_bet: int           # highest bet on the table this round
    last_raise_size: int       # size of the most recent raise (min re-raise reference)
    aggressor_seat: int        # seat index of last aggressor; -1 if no bet/raise yet
    has_acted: set = field(default_factory=set)  # seat indices who have voluntarily acted


# ---------------------------------------------------------------------------
# DecisionFn — async plug-in seam for Phase 4 LLM decision functions
# ---------------------------------------------------------------------------

DecisionFn = Callable[[Player, GameState], Awaitable[Action]]
"""
Type alias for the decision function signature.
Phase 2: mock_decision (always call/check).
Phase 4: LLM-driven decision function — drop-in replacement, no refactor needed.

Signature: async def make_decision(player: Player, game_state: GameState) -> Action
"""
