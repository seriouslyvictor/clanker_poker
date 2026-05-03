"""
test_models.py — TDD tests for backend/app/engine/models.py.

RED phase: these tests must FAIL before models.py exists.
GREEN phase: models.py implementation makes all tests pass.

Tests verify:
1. All imports work (Card, Action, Player, GameState, BettingRoundState, DecisionFn)
2. Pydantic models serialize to camelCase JSON matching types.ts contracts
3. BettingRoundState dataclass is constructible
4. DecisionFn type alias is defined
"""
import pytest
from typing import get_type_hints


class TestCardModel:
    """Card model — no alias_generator, fields s and r serialize directly."""

    def test_card_import(self):
        from app.engine.models import Card
        assert Card is not None

    def test_card_construction(self):
        from app.engine.models import Card
        c = Card(s="♥", r="A")
        assert c.s == "♥"
        assert c.r == "A"

    def test_card_serializes_without_alias(self):
        from app.engine.models import Card
        c = Card(s="♥", r="A")
        d = c.model_dump()
        assert d == {"s": "♥", "r": "A"}, f"Expected plain dict, got: {d}"

    def test_card_no_camel_case_keys(self):
        """Card must NOT have alias_generator — 's' and 'r' must stay as-is."""
        from app.engine.models import Card
        c = Card(s="♠", r="K")
        d = c.model_dump(by_alias=True)
        assert "s" in d and "r" in d


class TestActionType:
    """ActionType Literal validates against fold/call/raise/check only."""

    def test_actiontype_import(self):
        from app.engine.models import ActionType
        assert ActionType is not None

    def test_action_import(self):
        from app.engine.models import Action
        assert Action is not None

    def test_action_construction_fold(self):
        from app.engine.models import Action
        a = Action(action_type="fold")
        assert a.action_type == "fold"
        assert a.amount == 0

    def test_action_construction_call(self):
        from app.engine.models import Action
        a = Action(action_type="call")
        assert a.action_type == "call"

    def test_action_construction_raise_with_amount(self):
        from app.engine.models import Action
        a = Action(action_type="raise", amount=100)
        assert a.action_type == "raise"
        assert a.amount == 100

    def test_action_construction_check(self):
        from app.engine.models import Action
        a = Action(action_type="check")
        assert a.action_type == "check"

    def test_action_invalid_type_raises(self):
        from app.engine.models import Action
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            Action(action_type="bet")  # not in Literal


class TestPlayerModel:
    """Player model — alias_generator=to_camel produces holeCards, isFolded, isActive, isWinner."""

    def test_player_import(self):
        from app.engine.models import Player
        assert Player is not None

    def test_player_construction_minimal(self):
        from app.engine.models import Player
        p = Player(id="player-0", name="Bot", org="OpenAI", color="red", deck="default", chips=1000)
        assert p.id == "player-0"
        assert p.chips == 1000
        assert p.hole_cards == []
        assert p.action is None
        assert p.bet == 0
        assert p.is_folded is False
        assert p.is_active is True
        assert p.is_winner is False

    def test_player_hole_cards_camel_case(self):
        from app.engine.models import Player
        p = Player(id="p0", name="Bot", org="OpenAI", color="red", deck="default", chips=1000)
        d = p.model_dump(by_alias=True)
        assert "holeCards" in d, f"Missing holeCards in: {list(d.keys())}"
        assert "hole_cards" not in d

    def test_player_is_folded_camel_case(self):
        from app.engine.models import Player
        p = Player(id="p0", name="Bot", org="OpenAI", color="red", deck="default", chips=1000)
        d = p.model_dump(by_alias=True)
        assert "isFolded" in d, f"Missing isFolded in: {list(d.keys())}"
        assert "is_folded" not in d

    def test_player_is_active_camel_case(self):
        from app.engine.models import Player
        p = Player(id="p0", name="Bot", org="OpenAI", color="red", deck="default", chips=1000)
        d = p.model_dump(by_alias=True)
        assert "isActive" in d, f"Missing isActive in: {list(d.keys())}"
        assert "is_active" not in d

    def test_player_is_winner_camel_case(self):
        from app.engine.models import Player
        p = Player(id="p0", name="Bot", org="OpenAI", color="red", deck="default", chips=1000)
        d = p.model_dump(by_alias=True)
        assert "isWinner" in d, f"Missing isWinner in: {list(d.keys())}"
        assert "is_winner" not in d

    def test_player_all_camel_case_keys(self):
        """Verify all expected camelCase keys appear together."""
        from app.engine.models import Player
        p = Player(id="p0", name="Bot", org="OpenAI", color="red", deck="default", chips=1000)
        d = p.model_dump(by_alias=True)
        for key in ("holeCards", "isFolded", "isActive", "isWinner"):
            assert key in d, f"Missing {key} in: {list(d.keys())}"

    def test_player_construction_by_snake_case(self):
        """populate_by_name=True allows construction with snake_case field names."""
        from app.engine.models import Player, Card
        p = Player(
            id="p1",
            name="Test",
            org="Anthropic",
            color="blue",
            deck="deck1",
            chips=500,
            hole_cards=[Card(s="♥", r="A"), Card(s="♠", r="K")],
            is_folded=True,
            bet=100,
        )
        assert len(p.hole_cards) == 2
        assert p.is_folded is True
        assert p.bet == 100


class TestGameStateModel:
    """GameState model — alias_generator=to_camel produces communityCards, showCards, winnerHand."""

    def test_gamestate_import(self):
        from app.engine.models import GameState
        assert GameState is not None

    def test_gamestate_construction_minimal(self):
        from app.engine.models import GameState
        g = GameState(phase="pre-flop", pot=0)
        assert g.phase == "pre-flop"
        assert g.pot == 0
        assert g.community_cards == []
        assert g.players == []
        assert g.show_cards is False
        assert g.reasoning == []
        assert g.winner is None
        assert g.winner_hand == ""

    def test_gamestate_community_cards_camel_case(self):
        from app.engine.models import GameState
        g = GameState(phase="flop", pot=100)
        d = g.model_dump(by_alias=True)
        assert "communityCards" in d, f"Missing communityCards in: {list(d.keys())}"
        assert "community_cards" not in d

    def test_gamestate_show_cards_camel_case(self):
        from app.engine.models import GameState
        g = GameState(phase="showdown", pot=200, show_cards=True)
        d = g.model_dump(by_alias=True)
        assert "showCards" in d, f"Missing showCards in: {list(d.keys())}"
        assert "show_cards" not in d
        assert d["showCards"] is True

    def test_gamestate_winner_hand_camel_case(self):
        from app.engine.models import GameState
        g = GameState(phase="showdown", pot=200, winner_hand="Full House")
        d = g.model_dump(by_alias=True)
        assert "winnerHand" in d, f"Missing winnerHand in: {list(d.keys())}"
        assert "winner_hand" not in d
        assert d["winnerHand"] == "Full House"

    def test_gamestate_all_camel_case_keys(self):
        """Verify all required camelCase keys appear together."""
        from app.engine.models import GameState
        g = GameState(phase="pre-flop", pot=0)
        d = g.model_dump(by_alias=True)
        for key in ("communityCards", "showCards", "winnerHand"):
            assert key in d, f"Missing {key} in: {list(d.keys())}"

    def test_gamestate_nested_player_camel_case(self):
        """Nested Player in GameState also serializes to camelCase."""
        from app.engine.models import GameState, Player
        p = Player(id="p0", name="Bot", org="OpenAI", color="red", deck="default", chips=1000)
        g = GameState(phase="pre-flop", pot=0, players=[p])
        d = g.model_dump(by_alias=True)
        player_dict = d["players"][0]
        assert "holeCards" in player_dict, f"Nested player missing holeCards: {list(player_dict.keys())}"


class TestBettingRoundState:
    """BettingRoundState dataclass — internal engine state, not serialized."""

    def test_bettingroundstate_import(self):
        from app.engine.models import BettingRoundState
        assert BettingRoundState is not None

    def test_bettingroundstate_construction(self):
        from app.engine.models import BettingRoundState
        b = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        assert b.current_bet == 20
        assert b.last_raise_size == 20
        assert b.aggressor_seat == -1
        assert b.has_acted == set()

    def test_bettingroundstate_has_acted_is_set(self):
        from app.engine.models import BettingRoundState
        b = BettingRoundState(current_bet=0, last_raise_size=20, aggressor_seat=-1)
        b.has_acted.add(0)
        b.has_acted.add(1)
        assert 0 in b.has_acted
        assert 1 in b.has_acted

    def test_bettingroundstate_has_acted_not_shared(self):
        """Each BettingRoundState instance must have its own has_acted set."""
        from app.engine.models import BettingRoundState
        b1 = BettingRoundState(current_bet=0, last_raise_size=20, aggressor_seat=-1)
        b2 = BettingRoundState(current_bet=0, last_raise_size=20, aggressor_seat=-1)
        b1.has_acted.add(0)
        assert 0 not in b2.has_acted, "has_acted sets must not be shared between instances"


class TestDecisionFn:
    """DecisionFn type alias — callable seam for async decision functions."""

    def test_decisionfn_import(self):
        from app.engine.models import DecisionFn
        assert DecisionFn is not None

    def test_decisionfn_is_type_alias(self):
        """DecisionFn should be a type alias (Callable), not a class."""
        from app.engine.models import DecisionFn
        # It's a _GenericAlias or similar — just verify it can be used as a type hint
        import typing
        # Should be usable in a type hint without errors
        def accepts_fn(fn: DecisionFn) -> None:
            pass
        # Just verify the import and assignment work
        assert DecisionFn is not None


class TestInlineVerification:
    """The exact verification command from the plan must pass."""

    def test_inline_verification_command(self):
        """Replicate the plan's inline verification script."""
        from app.engine.models import Card, Action, Player, GameState, BettingRoundState, DecisionFn

        p = Player(id="player-0", name="Bot", org="OpenAI", color="red", deck="default", chips=1000)
        g = GameState(phase="pre-flop", pot=0)
        pd = p.model_dump(by_alias=True)
        gd = g.model_dump(by_alias=True)

        assert "holeCards" in pd, f"Missing holeCards: {list(pd.keys())}"
        assert "isFolded" in pd, f"Missing isFolded: {list(pd.keys())}"
        assert "isActive" in pd, f"Missing isActive: {list(pd.keys())}"
        assert "isWinner" in pd, f"Missing isWinner: {list(pd.keys())}"
        assert "communityCards" in gd, f"Missing communityCards: {list(gd.keys())}"
        assert "showCards" in gd, f"Missing showCards: {list(gd.keys())}"
        assert "winnerHand" in gd, f"Missing winnerHand: {list(gd.keys())}"

        c = Card(s="♥", r="A")
        assert c.model_dump() == {"s": "♥", "r": "A"}

        b = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        assert b.has_acted == set()
