"""
session.py — multi-hand Texas Hold'em session with dealer rotation.

Manages:
  - Player initialization from models.config.json (D-13, Phase 4)
  - Dealer button rotation (clockwise, one seat per hand)
  - Stack carry-over between hands (no reset within a session)
  - Player elimination: players with 0 chips are skipped (not dealt in);
    dealer button continues to rotate through all seat indices

Usage:
    session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
    hand_states = asyncio.run(session.run(n_hands=10))

Phase 3: The game loop in session.run() is the seam where SSE broadcast hooks in.
         Each hand's final GameState will be pushed to SSE subscribers.
Phase 4: _load_players_from_config() replaces _make_players() mock (D-13).
         player_models dict added to GameSession for LLM routing in game_loop.py.
"""
from __future__ import annotations

import json
import logging
import pathlib
from typing import Optional

from app.engine.game import run_hand, mock_decision, BroadcastFn
from app.engine.models import Player, GameState, DecisionFn

logger = logging.getLogger(__name__)


def _find_models_config() -> pathlib.Path:
    """
    Locate models.config.json searching from the session.py location upward.

    Search order:
      1. Worktree root (parent.parent.parent.parent of this file)
      2. Project root three levels above worktree root (for worktrees inside
         .claude/worktrees/ — i.e., worktree_root.parent.parent.parent)

    This two-step resolution works in:
      - Local dev (project root)
      - Git worktree (worktree root or project root above .claude/)
    """
    this_file = pathlib.Path(__file__).resolve()
    worktree_root = this_file.parent.parent.parent.parent  # engine/ -> app/ -> backend/ -> worktree root

    candidate = worktree_root / "models.config.json"
    if candidate.exists():
        return candidate

    # Worktree is inside .claude/worktrees/<name>/ — project root is 3 levels up
    project_root = worktree_root.parent.parent.parent
    candidate = project_root / "models.config.json"
    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        f"models.config.json not found at {worktree_root} or {project_root}. "
        "Ensure the file exists in the project root."
    )


def _load_players_from_config(starting_chips: int) -> tuple[list[Player], dict[str, str]]:
    """
    Load player roster from models.config.json (D-13).

    Returns:
        players:       list[Player] using id/name/org/color/deck from config
        player_models: dict[str, str] mapping player_id -> litellmModel string
                       Stored on GameSession separately — Player model has no litellm_model field.
    """
    config_path = _find_models_config()
    configs = json.loads(config_path.read_text())
    players = []
    player_models: dict[str, str] = {}
    for cfg in configs:
        players.append(Player(
            id=cfg["id"],
            name=cfg["name"],
            org=cfg["org"],
            color=cfg["color"],
            deck=cfg["deck"],
            chips=starting_chips,
        ))
        player_models[cfg["id"]] = cfg["litellmModel"]
    return players, player_models


class GameSession:
    """
    Manages a sequence of Texas Hold'em hands with dealer rotation and stack carry-over.

    Attributes:
        n_players:     Number of players (default 4)
        starting_chips: Initial chip stack per player (reset on new GameSession only)
        big_blind:     Big blind amount; small blind = big_blind // 2
        player_models: dict mapping player_id -> LiteLLM model string (Phase 4, D-14)
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
        players, player_models = _load_players_from_config(starting_chips)
        # Respect n_players cap: slice to the requested count
        self.players: list[Player] = players[:n_players]
        self.player_models: dict[str, str] = {
            pid: model for pid, model in player_models.items()
            if pid in {p.id for p in self.players}
        }
        self.dealer_seat: int = 0

    async def run(
        self,
        n_hands: int = 10,
        decision_fn: Optional[DecisionFn] = None,
        broadcast_fn: Optional[BroadcastFn] = None,
    ) -> list[GameState]:
        """
        Run n_hands of Texas Hold'em. Returns list of final GameState per hand.

        Args:
            n_hands: Number of hands to play
            decision_fn: Async decision function. Defaults to mock_decision (always call/check).
                         Phase 4 passes the LLM decision function here.
            broadcast_fn: Optional async callable receiving GameState at each phase transition.
                          Defaults to None (Phase 2 tests unaffected). Phase 3 passes publish().

        Returns:
            list[GameState] — final state of each completed hand, in order
        """
        if decision_fn is None:
            decision_fn = mock_decision

        completed_hands: list[GameState] = []

        for hand_num in range(n_hands):
            active_players = [p for p in self.players if p.chips > 0]
            if len(active_players) < 2:
                break

            dealer_name = self.players[self.dealer_seat].name
            stacks = "  ".join(f"{p.name} {p.chips}" for p in self.players)
            logger.info(
                "[bold blue]── Hand %d/%d ──[/bold blue]  Dealer: [blue]%s[/blue]",
                hand_num + 1, n_hands, dealer_name,
            )
            logger.info("  Stacks: %s", stacks)

            final_state = await run_hand(
                players=self.players,
                dealer_seat=self.dealer_seat,
                big_blind=self.big_blind,
                decision_fn=decision_fn,
                broadcast_fn=broadcast_fn,
            )

            for i, returned_player in enumerate(final_state.players):
                self.players[i].chips = returned_player.chips

            winner = next((p for p in final_state.players if p.is_winner), None)
            hand_name = final_state.winner_hand or "last standing"
            pot_won = sum(p.chips for p in final_state.players) - sum(p.chips for p in self.players) + (final_state.pot or 0)
            if winner:
                logger.info(
                    "[green]Hand %d → %s[/green]  (%s)",
                    hand_num + 1, winner.name, hand_name,
                )
            stacks_after = "  ".join(f"{p.name} {p.chips}" for p in self.players)
            logger.info("  Stacks: %s", stacks_after)

            completed_hands.append(final_state)
            self.dealer_seat = (self.dealer_seat + 1) % self.n_players

        return completed_hands
