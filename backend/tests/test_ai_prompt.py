"""
test_ai_prompt.py — TDD RED tests for backend/app/ai/prompt.py

Tests for:
  - build_system_prompt(): persona injection, format instruction
  - build_user_prompt(): hand state, math context, valid actions, opponents
  - Edge cases: pre-flop (hand_strength=None), empty community cards
"""
import pytest
from app.ai.archetypes import ARCHETYPES
from app.engine.models import Player, GameState, Card


@pytest.fixture
def gunslinger():
    return next(a for a in ARCHETYPES if a.name == "Gunslinger")


@pytest.fixture
def rock():
    return next(a for a in ARCHETYPES if a.name == "Rock")


@pytest.fixture
def player_ak():
    return Player(
        id="gpt4",
        name="GPT-5.5 Nano",
        org="OpenAI",
        color="#10a37f",
        deck="d",
        chips=980,
        hole_cards=[Card(s="♥", r="A"), Card(s="♦", r="K")],
    )


@pytest.fixture
def player_opponent():
    return Player(
        id="gemini",
        name="Gemini Flash",
        org="Google",
        color="#4285f4",
        deck="d",
        chips=750,
        bet=40,
        action="call",
    )


@pytest.fixture
def gs_flop(player_ak, player_opponent):
    return GameState(
        phase="flop",
        pot=120,
        community_cards=[Card(s="♣", r="Q"), Card(s="♥", r="J"), Card(s="♠", r="2")],
        players=[player_ak, player_opponent],
        current_bet=40,
    )


@pytest.fixture
def gs_preflop(player_ak):
    return GameState(
        phase="pre-flop",
        pot=30,
        community_cards=[],
        players=[player_ak],
        current_bet=20,
    )


@pytest.fixture
def math_ctx_flop():
    return {"hand_strength": 1234, "win_probability": 0.72, "pot_odds": None}


@pytest.fixture
def math_ctx_preflop():
    return {"hand_strength": None, "win_probability": 0.50, "pot_odds": None}


@pytest.fixture
def valid_acts_call():
    return {
        "valid_types": {"fold", "call", "raise"},
        "call_amount": 40,
        "raise_min": 80,
        "raise_max": 980,
    }


@pytest.fixture
def valid_acts_check():
    return {
        "valid_types": {"fold", "check", "raise"},
        "call_amount": 0,
        "raise_min": 40,
        "raise_max": 980,
    }


# ---------------------------------------------------------------------------
# build_system_prompt tests
# ---------------------------------------------------------------------------

class TestBuildSystemPrompt:
    def test_imports_work(self):
        from app.ai.prompt import build_system_prompt
        assert callable(build_system_prompt)

    def test_contains_player_name(self, gunslinger, player_ak):
        from app.ai.prompt import build_system_prompt
        result = build_system_prompt(player_ak, gunslinger)
        assert "GPT-5.5 Nano" in result

    def test_contains_archetype_name(self, gunslinger, player_ak):
        from app.ai.prompt import build_system_prompt
        result = build_system_prompt(player_ak, gunslinger)
        assert "Gunslinger" in result

    def test_contains_archetype_description(self, gunslinger, player_ak):
        from app.ai.prompt import build_system_prompt
        result = build_system_prompt(player_ak, gunslinger)
        # Gunslinger description starts with "An aggressive, fearless raiser"
        assert "aggressive" in result.lower() or "raiser" in result.lower()

    def test_contains_format_instruction(self, gunslinger, player_ak):
        from app.ai.prompt import build_system_prompt
        result = build_system_prompt(player_ak, gunslinger)
        assert "fold|call|raise|check" in result

    def test_contains_fenced_json_block(self, gunslinger, player_ak):
        from app.ai.prompt import build_system_prompt
        result = build_system_prompt(player_ak, gunslinger)
        assert "```json" in result

    def test_returns_string(self, gunslinger, player_ak):
        from app.ai.prompt import build_system_prompt
        result = build_system_prompt(player_ak, gunslinger)
        assert isinstance(result, str)
        assert len(result) > 50

    def test_rock_archetype(self, rock, player_ak):
        from app.ai.prompt import build_system_prompt
        result = build_system_prompt(player_ak, rock)
        assert "Rock" in result


# ---------------------------------------------------------------------------
# build_user_prompt tests
# ---------------------------------------------------------------------------

class TestBuildUserPrompt:
    def test_imports_work(self):
        from app.ai.prompt import build_user_prompt
        assert callable(build_user_prompt)

    def test_contains_win_probability(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        # 0.72 formatted as 72%
        assert "72%" in result or "Win probability" in result

    def test_contains_pot_odds_computed(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        # call=40, pot=120 → pot_odds = 40/(120+40) = 0.25 = 25%
        assert "25%" in result or "Pot odds" in result

    def test_pot_odds_exact_value(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        """pot_odds = 40/(120+40) = 0.25 → '25%'"""
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert "25%" in result

    def test_contains_hand_strength(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert "1234" in result or "Hand strength" in result

    def test_contains_pot(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert "Pot: 120" in result or "pot" in result.lower()

    def test_contains_call_action(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert "call 40" in result

    def test_contains_fold(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert "fold" in result

    def test_contains_raise_range(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert "raise" in result
        assert "80" in result  # raise_min

    def test_contains_opponents_label(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert "Opponents" in result or "opponents" in result

    def test_preflop_hand_strength_na(self, gs_preflop, math_ctx_preflop, valid_acts_call, player_ak):
        """Pre-flop: hand_strength=None → 'n/a' in output"""
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_preflop, math_ctx_preflop, valid_acts_call, player_ak)
        assert "n/a" in result

    def test_empty_community_cards_no_crash(self, gs_preflop, math_ctx_preflop, valid_acts_call, player_ak):
        """Empty community cards: no crash; shows 'none'"""
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_preflop, math_ctx_preflop, valid_acts_call, player_ak)
        assert "none" in result.lower() or "Board" in result

    def test_pot_odds_zero_when_no_call(self, gs_flop, math_ctx_flop, valid_acts_check, player_ak):
        """call_amount=0 → pot_odds=0%"""
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_check, player_ak)
        assert "0%" in result

    def test_check_action_present(self, gs_flop, math_ctx_flop, valid_acts_check, player_ak):
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_check, player_ak)
        assert "check" in result

    def test_returns_string(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        from app.ai.prompt import build_user_prompt
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert isinstance(result, str)
        assert len(result) > 50
