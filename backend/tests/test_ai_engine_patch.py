"""
test_ai_engine_patch.py — Tests for engine/models.py patches (Plan 04-01, Task 2).

Covers:
  - GameState.current_bet field: exists, defaults to 0, is assignable
  - Existing GameState construction is unaffected (backward compatibility)
"""
import pytest
from app.engine.models import GameState, Player


class TestGameStateCurrentBet:
    def test_current_bet_field_exists(self):
        """GameState must have a current_bet field."""
        gs = GameState(phase="flop", pot=100)
        assert hasattr(gs, "current_bet"), "current_bet field missing from GameState"

    def test_current_bet_defaults_to_zero(self):
        """current_bet defaults to 0 when not specified."""
        gs = GameState(phase="flop", pot=100)
        assert gs.current_bet == 0, f"Expected current_bet=0, got {gs.current_bet}"

    def test_current_bet_assignable(self):
        """current_bet can be set to a positive value."""
        gs = GameState(phase="turn", pot=200, current_bet=40)
        assert gs.current_bet == 40, f"Expected current_bet=40, got {gs.current_bet}"

    def test_current_bet_serializes_to_camel_case(self):
        """current_bet must serialize to currentBet in JSON (camelCase)."""
        gs = GameState(phase="river", pot=300, current_bet=80)
        dumped = gs.model_dump(by_alias=True)
        assert "currentBet" in dumped, "currentBet missing from camelCase serialization"
        assert dumped["currentBet"] == 80

    def test_existing_construction_unaffected(self):
        """Existing GameState constructors without current_bet still work."""
        gs = GameState(phase="pre-flop", pot=0)
        assert gs.phase == "pre-flop"
        assert gs.pot == 0
        assert gs.current_bet == 0  # default

    def test_current_bet_with_full_state(self):
        """GameState with all fields including current_bet works correctly."""
        gs = GameState(
            phase="flop",
            pot=150,
            current_bet=50,
            show_cards=False,
            winner=None,
            winner_hand="",
        )
        assert gs.current_bet == 50

    def test_reasoning_field_still_exists(self):
        """reasoning field still exists on GameState (not broken by patch)."""
        gs = GameState(phase="flop", pot=100)
        assert hasattr(gs, "reasoning")
        assert isinstance(gs.reasoning, list)
        assert len(gs.reasoning) == 0  # empty by default
