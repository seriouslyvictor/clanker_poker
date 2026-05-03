"""
session.py — multi-hand Texas Hold'em session with dealer rotation.

Manages:
  - Player initialization with starting chip stacks
  - Dealer button rotation (clockwise, one seat per hand)
  - Stack carry-over between hands (no reset within a session)
  - Player elimination: players with 0 chips are skipped (not dealt in);
    dealer button continues to rotate through all seat indices

Usage:
    session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
    hand_states = asyncio.run(session.run(n_hands=10))

Phase 3: The game loop in session.run() is the seam where SSE broadcast hooks in.
         Each hand's final GameState will be pushed to SSE subscribers.
"""
from __future__ import annotations

from typing import Optional

from app.engine.game import run_hand, mock_decision
from app.engine.models import Player, GameState, DecisionFn


def _make_players(n_players: int, starting_chips: int) -> list[Player]:
    """Create mock player roster for Phase 2. Phase 4 replaces with LLM-backed players."""
    return [
        Player(
            id=f'player-{i}',
            name=f'Player {i}',
            org='mock',
            color='gray',
            deck='default',
            chips=starting_chips,
        )
        for i in range(n_players)
    ]


class GameSession:
    """
    Manages a sequence of Texas Hold'em hands with dealer rotation and stack carry-over.

    Attributes:
        n_players: Number of players (default 4)
        starting_chips: Initial chip stack per player (reset on new GameSession only)
        big_blind: Big blind amount; small blind = big_blind // 2
    """

    def __init__(
        self,
        n_players: int = 4,
        starting_chips: int = 1000,
        big_blind: int = 20,
    ) -> None:
        self.n_players = n_players
        self.starting_chips = starting_chips
        self.big_blind = big_blind
        self.players: list[Player] = _make_players(n_players, starting_chips)
        self.dealer_seat: int = 0

    async def run(
        self,
        n_hands: int = 10,
        decision_fn: Optional[DecisionFn] = None,
    ) -> list[GameState]:
        """
        Run n_hands of Texas Hold'em. Returns list of final GameState per hand.

        Args:
            n_hands: Number of hands to play
            decision_fn: Async decision function. Defaults to mock_decision (always call/check).
                         Phase 4 passes the LLM decision function here.

        Returns:
            list[GameState] — final state of each completed hand, in order
        """
        if decision_fn is None:
            decision_fn = mock_decision

        completed_hands: list[GameState] = []

        for hand_num in range(n_hands):
            # Determine which players are active this hand (chips > 0)
            active_players = [p for p in self.players if p.chips > 0]
            if len(active_players) < 2:
                # Session over — not enough players to continue
                break

            # Run the hand — run_hand deep copies internally; chip updates come back in GameState.players
            final_state = await run_hand(
                players=self.players,  # run_hand deep copies internally
                dealer_seat=self.dealer_seat,
                big_blind=self.big_blind,
                decision_fn=decision_fn,
            )

            # Update persistent player chip counts from the completed hand
            # run_hand returns GameState.players with updated chips
            for i, returned_player in enumerate(final_state.players):
                self.players[i].chips = returned_player.chips

            completed_hands.append(final_state)

            # Rotate dealer button clockwise (always advances, regardless of elimination)
            self.dealer_seat = (self.dealer_seat + 1) % self.n_players

        return completed_hands
