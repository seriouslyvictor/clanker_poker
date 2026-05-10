"""
test_ai_decision.py — TDD RED tests for backend/app/ai/decision.py

Tests for:
  - reconstruct_valid_actions(): action reconstruction from GameState
  - _fallback_action(): archetype-biased deterministic decision
  - make_llm_decision_fn(): factory returns async callable
  - CancelledError: never swallowed
  - Action field: action_type not type
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.archetypes import ARCHETYPES
from app.ai.budget import BudgetTracker, CircuitBreaker
from app.engine.models import Player, GameState, Card, Action


@pytest.fixture
def gunslinger():
    return next(a for a in ARCHETYPES if a.name == "Gunslinger")


@pytest.fixture
def rock():
    return next(a for a in ARCHETYPES if a.name == "Rock")


@pytest.fixture
def chaotic():
    return next(a for a in ARCHETYPES if a.name == "Chaotic Optimist")


@pytest.fixture
def player():
    return Player(
        id="gpt4",
        name="GPT-5.5 Nano",
        org="OpenAI",
        color="#10a37f",
        deck="d",
        chips=980,
        bet=0,
    )


@pytest.fixture
def gs_call():
    """GameState where current_bet=40, player.bet=0, so call_amount=40"""
    return GameState(phase="flop", pot=120, current_bet=40)


@pytest.fixture
def gs_check():
    """GameState where current_bet=0, player.bet=0, so can check"""
    return GameState(phase="flop", pot=120, current_bet=0)


@pytest.fixture
def valid_acts_with_raise():
    return {
        "valid_types": {"fold", "call", "raise"},
        "call_amount": 40,
        "raise_min": 60,
        "raise_max": 980,
    }


@pytest.fixture
def valid_acts_no_raise():
    return {
        "valid_types": {"fold", "call"},
        "call_amount": 40,
        "raise_min": 0,
        "raise_max": 0,
    }


@pytest.fixture
def math_low():
    """win_probability=0.25 — below all archetype thresholds"""
    return {"win_probability": 0.25, "hand_strength": None, "pot_odds": None}


@pytest.fixture
def math_medium():
    """win_probability=0.45 — Gunslinger raises (>=0.40), Rock folds (<0.65)"""
    return {"win_probability": 0.45, "hand_strength": None, "pot_odds": None}


@pytest.fixture
def math_high():
    """win_probability=0.80 — above all archetype raise thresholds"""
    return {"win_probability": 0.80, "hand_strength": None, "pot_odds": None}


# ---------------------------------------------------------------------------
# reconstruct_valid_actions tests
# ---------------------------------------------------------------------------

class TestReconstructValidActions:
    def test_imports_work(self):
        from app.ai.decision import reconstruct_valid_actions
        assert callable(reconstruct_valid_actions)

    def test_fold_always_valid(self, player, gs_call):
        from app.ai.decision import reconstruct_valid_actions
        result = reconstruct_valid_actions(player, gs_call)
        assert "fold" in result["valid_types"]

    def test_call_when_current_bet_above_player_bet(self, player, gs_call):
        from app.ai.decision import reconstruct_valid_actions
        result = reconstruct_valid_actions(player, gs_call)
        assert "call" in result["valid_types"]
        assert result["call_amount"] == 40

    def test_check_when_no_bet_to_call(self, player, gs_check):
        from app.ai.decision import reconstruct_valid_actions
        result = reconstruct_valid_actions(player, gs_check)
        assert "check" in result["valid_types"]
        assert "call" not in result["valid_types"]
        assert result["call_amount"] == 0

    def test_raise_available_when_chips_exceed_call(self, player, gs_call):
        from app.ai.decision import reconstruct_valid_actions
        result = reconstruct_valid_actions(player, gs_call)
        # player has 980 chips, call=40 — can raise
        assert "raise" in result["valid_types"]
        assert result["raise_max"] == player.chips + player.bet

    def test_no_raise_when_only_enough_for_call(self, gs_call):
        from app.ai.decision import reconstruct_valid_actions
        # player with exactly call_amount chips — cannot raise
        poor_player = Player(id="gpt4", name="X", org="o", color="c", deck="d", chips=40, bet=0)
        result = reconstruct_valid_actions(poor_player, gs_call)
        assert "raise" not in result["valid_types"]

    def test_returns_dict_with_required_keys(self, player, gs_call):
        from app.ai.decision import reconstruct_valid_actions
        result = reconstruct_valid_actions(player, gs_call)
        assert "valid_types" in result
        assert "call_amount" in result
        assert "raise_min" in result
        assert "raise_max" in result
        assert isinstance(result["valid_types"], set)


# ---------------------------------------------------------------------------
# _fallback_action tests
# ---------------------------------------------------------------------------

class TestFallbackAction:
    def test_imports_work(self):
        from app.ai.decision import _fallback_action
        assert callable(_fallback_action)

    def test_gunslinger_raises_at_medium_prob(self, player, gunslinger, valid_acts_with_raise, math_medium):
        """Gunslinger (raise_freq=0.40): win_prob=0.45 >= 0.40 → raise"""
        from app.ai.decision import _fallback_action
        action = asyncio.run(_fallback_action(player, gunslinger, valid_acts_with_raise, math_medium, "test"))
        assert action.action_type == "raise"
        assert isinstance(action, Action)

    def test_rock_folds_at_medium_prob(self, player, rock, valid_acts_with_raise, math_medium):
        """Rock (hand_looseness=0.65): win_prob=0.45 < 0.65 → fold"""
        from app.ai.decision import _fallback_action
        action = asyncio.run(_fallback_action(player, rock, valid_acts_with_raise, math_medium, "test"))
        assert action.action_type == "fold"

    def test_rock_raises_at_high_prob(self, player, rock, valid_acts_with_raise, math_high):
        """Rock (raise_freq=0.80): win_prob=0.80 >= 0.80 → raise"""
        from app.ai.decision import _fallback_action
        action = asyncio.run(_fallback_action(player, rock, valid_acts_with_raise, math_high, "test"))
        assert action.action_type == "raise"

    def test_check_preferred_over_fold_when_available(self, player, rock, math_low):
        """Any archetype: check if available and win_prob is too low to call"""
        from app.ai.decision import _fallback_action
        valid = {"valid_types": {"fold", "check"}, "call_amount": 0, "raise_min": 0, "raise_max": 0}
        action = asyncio.run(_fallback_action(player, rock, valid, math_low, "test"))
        assert action.action_type == "check"

    def test_action_uses_action_type_field(self, player, gunslinger, valid_acts_with_raise, math_medium):
        """Action must use action_type field not type field"""
        from app.ai.decision import _fallback_action
        action = asyncio.run(_fallback_action(player, gunslinger, valid_acts_with_raise, math_medium, "test"))
        assert hasattr(action, "action_type")
        # Verify it is a valid Action model
        assert action.action_type in ("fold", "call", "raise", "check")

    def test_raise_amount_is_raise_min(self, player, gunslinger, valid_acts_with_raise, math_medium):
        """When raising, amount should be raise_min"""
        from app.ai.decision import _fallback_action
        action = asyncio.run(_fallback_action(player, gunslinger, valid_acts_with_raise, math_medium, "test"))
        assert action.action_type == "raise"
        assert action.amount == 60  # raise_min=60

    def test_call_amount_correct(self, player, rock, math_high):
        """Rock calls when win_prob >= hand_looseness but no raise available"""
        from app.ai.decision import _fallback_action
        # Rock: raise_freq=0.80, hand_looseness=0.65; win_prob=0.80 but NO raise
        valid_no_raise = {"valid_types": {"fold", "call"}, "call_amount": 40, "raise_min": 0, "raise_max": 0}
        # win_prob=0.80 >= raise_freq=0.80 but raise not available; 0.80 >= hand_looseness=0.65 → call
        action = asyncio.run(_fallback_action(player, rock, valid_no_raise, math_high, "test"))
        assert action.action_type == "call"
        assert action.amount == 40

    def test_no_redis_no_crash(self, player, gunslinger, valid_acts_with_raise, math_medium):
        """No redis_client and no game_state: no crash"""
        from app.ai.decision import _fallback_action
        action = asyncio.run(
            _fallback_action(player, gunslinger, valid_acts_with_raise, math_medium, "test",
                             redis_client=None, game_state=None)
        )
        assert action.action_type in ("fold", "call", "raise", "check")


# ---------------------------------------------------------------------------
# make_llm_decision_fn tests
# ---------------------------------------------------------------------------

class TestMakeLlmDecisionFn:
    def test_imports_work(self):
        from app.ai.decision import make_llm_decision_fn
        assert callable(make_llm_decision_fn)

    def test_returns_async_callable(self, gunslinger):
        from app.ai.decision import make_llm_decision_fn
        archetypes_map = {"gpt4": gunslinger}
        fn = make_llm_decision_fn(archetypes_map, None, BudgetTracker(), CircuitBreaker())
        assert asyncio.iscoroutinefunction(fn)

    def test_no_archetype_returns_fold(self, player):
        """Player not in archetypes dict → fold fallback, no crash"""
        from app.ai.decision import make_llm_decision_fn
        fn = make_llm_decision_fn({}, None, BudgetTracker(), CircuitBreaker())
        gs = GameState(phase="flop", pot=120, current_bet=0, players=[player])
        action = asyncio.run(fn(player, gs))
        assert action.action_type == "fold"

    def test_circuit_open_returns_fallback(self, player, gunslinger):
        """Circuit open → fallback immediately, no LLM call"""
        from app.ai.decision import make_llm_decision_fn
        circuit = CircuitBreaker()
        budget = BudgetTracker()
        archetypes_map = {"gpt4": gunslinger}

        # Pre-configure model string same as _get_model would return
        import json
        from pathlib import Path
        # models.config.json lives in the project root (one above the worktree root / backend parent)
        # Try worktree root first, then project root (for local dev vs CI)
        worktree_root = Path(__file__).parent.parent.parent
        project_root = worktree_root.parent.parent.parent  # worktree is inside .claude/worktrees/
        config_path = worktree_root / "models.config.json"
        if not config_path.exists():
            config_path = project_root / "models.config.json"
        with open(config_path) as f:
            configs = json.load(f)
        model_str = next(c["litellmModel"] for c in configs if c["id"] == "gpt4")

        # Trip the circuit
        for _ in range(3):
            circuit.record_error(model_str)
        assert circuit.is_open(model_str)

        fn = make_llm_decision_fn(archetypes_map, None, budget, circuit)
        gs = GameState(
            phase="pre-flop", pot=60, current_bet=20,
            players=[player],
        )
        action = asyncio.run(fn(player, gs))
        assert action.action_type in ("fold", "call", "raise", "check")


# ---------------------------------------------------------------------------
# No Action(type=...) pattern tests
# ---------------------------------------------------------------------------

class TestActionFieldName:
    def test_no_action_type_wrong_field_in_decision_module(self):
        """Verify decision.py never uses Action(type=...) — grep check"""
        import re
        from pathlib import Path
        decision_path = Path(__file__).parent.parent / "app" / "ai" / "decision.py"
        content = decision_path.read_text(encoding="utf-8")
        # Ensure no wrong field usage
        matches = re.findall(r"Action\(type=", content)
        assert len(matches) == 0, f"Found Action(type=...) in decision.py: {matches}"

    def test_action_type_field_used(self):
        """Verify decision.py uses action_type= field"""
        from pathlib import Path
        decision_path = Path(__file__).parent.parent / "app" / "ai" / "decision.py"
        content = decision_path.read_text(encoding="utf-8")
        assert "action_type=" in content


# ---------------------------------------------------------------------------
# CancelledError tests
# ---------------------------------------------------------------------------

class TestCancelledError:
    def test_cancelled_error_not_swallowed_in_decision_module(self):
        """Verify every except asyncio.CancelledError in decision.py has raise"""
        import re
        from pathlib import Path
        decision_path = Path(__file__).parent.parent / "app" / "ai" / "decision.py"
        content = decision_path.read_text(encoding="utf-8")
        # Find all CancelledError except blocks
        # Check that "CancelledError" appears and is always followed by "raise"
        blocks = re.findall(
            r"except asyncio\.CancelledError.*?(?=except|finally|else:|return|$)",
            content, re.DOTALL
        )
        assert len(blocks) > 0, "No CancelledError handling found in decision.py"
        for block in blocks:
            assert "raise" in block, f"CancelledError block lacks 'raise': {block[:100]}"
