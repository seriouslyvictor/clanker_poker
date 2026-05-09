"""
Tests for backend/app/ai/prompt.py

Covers:
  AI-03: Structured math context delivery -- all required fields present in prompts
"""
import pytest

from app.ai.archetypes import ARCHETYPES
from app.ai.prompt import build_system_prompt, build_user_prompt
from app.engine.models import Card, GameState, Player


# ---------------------------------------------------------------------------
# Module-level helpers (AI-03 coverage tests)
# ---------------------------------------------------------------------------

def _make_player(**kwargs) -> Player:
    defaults = dict(id="gpt4", name="GPT-5.5 Nano", org="OpenAI", color="#10a37f", deck="d", chips=980,
                    hole_cards=[Card(s="♥", r="A"), Card(s="♦", r="K")])
    defaults.update(kwargs)
    return Player(**defaults)


def _make_game_state(**kwargs) -> GameState:
    defaults = dict(phase="flop", pot=120, current_bet=40,
                    community_cards=[Card(s="♣", r="Q"), Card(s="♥", r="J"), Card(s="♠", r="2")])
    defaults.update(kwargs)
    return GameState(**defaults)


GUNSLINGER = next(a for a in ARCHETYPES if a.name == "Gunslinger")
ROCK = next(a for a in ARCHETYPES if a.name == "Rock")

VALID_ACTS = {"valid_types": {"fold", "call", "raise"}, "call_amount": 40, "raise_min": 60, "raise_max": 980}
MATH_CTX = {"win_probability": 0.72, "hand_strength": 1234, "pot_odds": None}


# ---------------------------------------------------------------------------
# Pytest fixtures (for extended test coverage)
# ---------------------------------------------------------------------------

@pytest.fixture
def gunslinger():
    return GUNSLINGER


@pytest.fixture
def rock():
    return ROCK


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
    def test_contains_player_name(self):
        p = _make_player()
        sp = build_system_prompt(p, GUNSLINGER)
        assert "GPT-5.5 Nano" in sp

    def test_contains_archetype_name(self):
        p = _make_player()
        sp = build_system_prompt(p, GUNSLINGER)
        assert "Gunslinger" in sp

    def test_contains_format_instruction(self):
        """AI-03: System prompt must include the fenced JSON format instruction."""
        p = _make_player()
        sp = build_system_prompt(p, GUNSLINGER)
        assert "fold|call|raise|check" in sp

    def test_contains_archetype_description(self):
        p = _make_player()
        sp = build_system_prompt(p, ROCK)
        assert "tight" in sp.lower() or "fold" in sp.lower(), "Rock description should mention tight/fold behavior"

    def test_contains_fenced_json_block(self):
        p = _make_player()
        sp = build_system_prompt(p, GUNSLINGER)
        assert "```json" in sp

    def test_returns_string(self):
        p = _make_player()
        sp = build_system_prompt(p, GUNSLINGER)
        assert isinstance(sp, str)
        assert len(sp) > 50

    def test_rock_archetype_name_present(self):
        p = _make_player()
        sp = build_system_prompt(p, ROCK)
        assert "Rock" in sp


# ---------------------------------------------------------------------------
# build_user_prompt tests
# ---------------------------------------------------------------------------

class TestBuildUserPrompt:
    def test_contains_win_probability(self):
        """AI-03: win_probability must be in user prompt."""
        p = _make_player()
        gs = _make_game_state()
        gs.players = [p]
        prompt = build_user_prompt(gs, MATH_CTX, VALID_ACTS, p)
        assert "win probability" in prompt.lower() or "Win probability" in prompt

    def test_contains_pot_odds(self):
        """AI-03: pot_odds must be computed and included."""
        p = _make_player()
        gs = _make_game_state()
        gs.players = [p]
        prompt = build_user_prompt(gs, MATH_CTX, VALID_ACTS, p)
        assert "pot odds" in prompt.lower() or "Pot odds" in prompt

    def test_contains_hand_strength(self):
        """AI-03: hand_strength must be in user prompt."""
        p = _make_player()
        gs = _make_game_state()
        gs.players = [p]
        prompt = build_user_prompt(gs, MATH_CTX, VALID_ACTS, p)
        assert "hand strength" in prompt.lower() or "Hand strength" in prompt

    def test_contains_available_actions(self):
        """AI-03: available actions with amounts must be in user prompt."""
        p = _make_player()
        gs = _make_game_state()
        gs.players = [p]
        prompt = build_user_prompt(gs, MATH_CTX, VALID_ACTS, p)
        assert "fold" in prompt
        assert "call" in prompt

    def test_contains_current_pot(self):
        """AI-03: current pot must be in user prompt."""
        p = _make_player()
        gs = _make_game_state(pot=300)
        gs.players = [p]
        prompt = build_user_prompt(gs, MATH_CTX, VALID_ACTS, p)
        assert "300" in prompt or "Pot: 300" in prompt

    def test_contains_community_cards(self):
        """AI-03: community cards must be in user prompt."""
        p = _make_player()
        gs = _make_game_state()
        gs.players = [p]
        prompt = build_user_prompt(gs, MATH_CTX, VALID_ACTS, p)
        # Board line should contain the community cards (Q, J, 2)
        assert "Q" in prompt or "J" in prompt

    def test_preflop_no_hand_strength_shows_na(self):
        """Pre-flop: hand_strength is None -> 'n/a' in prompt (not crash)."""
        p = _make_player()
        gs = _make_game_state(phase="pre-flop", community_cards=[])
        gs.players = [p]
        preflop_math = {"win_probability": 0.55, "hand_strength": None, "pot_odds": None}
        prompt = build_user_prompt(gs, preflop_math, VALID_ACTS, p)
        assert "n/a" in prompt.lower() or "none" in prompt.lower() or "pre-flop" in prompt.lower()

    def test_pot_odds_computed_correctly(self):
        """pot_odds = call_amount / (pot + call_amount) = 40 / (120+40) = 25%."""
        p = _make_player()
        gs = _make_game_state(pot=120, current_bet=40)
        gs.players = [p]
        prompt = build_user_prompt(gs, MATH_CTX, VALID_ACTS, p)
        assert "25%" in prompt, f"Expected 25% pot odds in prompt. Got: {prompt}"

    # ---------------------------------------------------------------------------
    # Extended coverage tests (from TDD RED phase)
    # ---------------------------------------------------------------------------

    def test_contains_pot_fixture(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert "Pot: 120" in result or "pot" in result.lower()

    def test_contains_call_action_amount(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert "call 40" in result

    def test_contains_raise_range(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert "raise" in result
        assert "80" in result  # raise_min

    def test_contains_opponents_label(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert "Opponents" in result or "opponents" in result

    def test_preflop_hand_strength_na_fixture(self, gs_preflop, math_ctx_preflop, valid_acts_call, player_ak):
        """Pre-flop: hand_strength=None -> 'n/a' in output"""
        result = build_user_prompt(gs_preflop, math_ctx_preflop, valid_acts_call, player_ak)
        assert "n/a" in result

    def test_empty_community_cards_no_crash(self, gs_preflop, math_ctx_preflop, valid_acts_call, player_ak):
        """Empty community cards: no crash; shows 'none'"""
        result = build_user_prompt(gs_preflop, math_ctx_preflop, valid_acts_call, player_ak)
        assert "none" in result.lower() or "Board" in result

    def test_pot_odds_zero_when_no_call(self, gs_flop, math_ctx_flop, valid_acts_check, player_ak):
        """call_amount=0 -> pot_odds=0%"""
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_check, player_ak)
        assert "0%" in result

    def test_check_action_present(self, gs_flop, math_ctx_flop, valid_acts_check, player_ak):
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_check, player_ak)
        assert "check" in result

    def test_returns_string_fixture(self, gs_flop, math_ctx_flop, valid_acts_call, player_ak):
        result = build_user_prompt(gs_flop, math_ctx_flop, valid_acts_call, player_ak)
        assert isinstance(result, str)
        assert len(result) > 50
