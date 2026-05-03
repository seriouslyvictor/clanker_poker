"""
test_game_engine.py — TDD tests for backend/app/engine/game.py

RED phase: All tests import from game.py which does not yet exist.
GREEN phase: All tests pass after game.py is implemented.

Test coverage map (from RESEARCH.md):
  SC1 - Complete hand structure (dealing, community cards, showdown phase)
  SC2 - Correct action order (pre-flop UTG, post-flop SB first)
  SC3 - Chip conservation (sum(stacks) + pot == starting_total)
  SC4 - valid_actions logic
  SC5 - is_round_closed logic
  SC6 - BB has_acted bug NOT present (BB gets option to act)
  SC7 - Early termination when all-but-one fold
"""
import asyncio
from collections import defaultdict

import pytest

from app.engine.models import Player, GameState, Action, BettingRoundState
from app.engine.game import run_hand, mock_decision, valid_actions, is_round_closed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_players(n: int = 4, chips: int = 1000) -> list[Player]:
    """Create n mock players with given starting chips."""
    return [
        Player(
            id=f"player-{i}",
            name=f"Bot{i}",
            org="Org",
            color="red",
            deck="default",
            chips=chips,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# SC1: valid_actions — correct action set per situation
# ---------------------------------------------------------------------------

class TestValidActions:
    """valid_actions(player, state) returns correct action options."""

    def test_check_available_when_no_bet_outstanding(self):
        """Player can check when their bet matches current_bet (no bet to call)."""
        player = make_players(1)[0]
        player.bet = 0
        state = BettingRoundState(current_bet=0, last_raise_size=20, aggressor_seat=-1)
        actions = valid_actions(player, state)
        assert "check" in actions
        assert "call" not in actions

    def test_fold_always_available(self):
        """fold is always valid regardless of situation."""
        player = make_players(1)[0]
        player.bet = 0
        state = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        actions = valid_actions(player, state)
        assert "fold" in actions

    def test_call_available_when_bet_outstanding(self):
        """Player gets call when current_bet > player.bet."""
        player = make_players(1)[0]
        player.bet = 0
        state = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        actions = valid_actions(player, state)
        assert "call" in actions
        assert "check" not in actions

    def test_raise_available_when_chips_exceed_call(self):
        """Player can raise when chips > call_amount."""
        player = make_players(1)[0]
        player.bet = 0
        player.chips = 1000
        state = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        actions = valid_actions(player, state)
        assert "raise" in actions

    def test_no_raise_when_only_enough_to_call(self):
        """Player with chips <= call_amount cannot raise (all-in only)."""
        player = make_players(1)[0]
        player.bet = 0
        player.chips = 20  # exactly call amount
        state = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        actions = valid_actions(player, state)
        assert "call" in actions
        assert "raise" not in actions

    def test_raise_available_when_no_bet_and_has_chips(self):
        """Player can raise (or check) when no bet outstanding and has chips."""
        player = make_players(1)[0]
        player.bet = 0
        player.chips = 100
        state = BettingRoundState(current_bet=0, last_raise_size=20, aggressor_seat=-1)
        actions = valid_actions(player, state)
        assert "check" in actions
        assert "raise" in actions

    def test_no_raise_when_no_chips(self):
        """Player with 0 chips cannot raise."""
        player = make_players(1)[0]
        player.bet = 0
        player.chips = 0
        state = BettingRoundState(current_bet=0, last_raise_size=20, aggressor_seat=-1)
        actions = valid_actions(player, state)
        assert "check" in actions
        assert "raise" not in actions


# ---------------------------------------------------------------------------
# SC2: is_round_closed — correct termination logic
# ---------------------------------------------------------------------------

class TestIsRoundClosed:
    """is_round_closed(state, players) returns correct boolean."""

    def test_open_when_not_all_acted(self):
        """Round not closed when active player hasn't acted."""
        players = make_players(2)
        state = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        state.has_acted = {0}  # player 1 hasn't acted
        players[0].bet = 20
        players[1].bet = 0
        assert is_round_closed(state, players) is False

    def test_open_when_bets_not_equal(self):
        """Round not closed when a player owes chips."""
        players = make_players(2)
        state = BettingRoundState(current_bet=40, last_raise_size=20, aggressor_seat=-1)
        state.has_acted = {0, 1}  # both acted
        players[0].bet = 40
        players[1].bet = 20  # player 1 still owes 20
        players[1].chips = 100  # not all-in
        assert is_round_closed(state, players) is False

    def test_closed_when_all_acted_and_bets_equal(self):
        """Round closed when all active players acted and bets match."""
        players = make_players(2)
        state = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        state.has_acted = {0, 1}
        players[0].bet = 20
        players[1].bet = 20
        assert is_round_closed(state, players) is True

    def test_closed_when_only_one_active(self):
        """Round closed immediately when only one player is active."""
        players = make_players(2)
        players[1].is_folded = True
        state = BettingRoundState(current_bet=0, last_raise_size=20, aggressor_seat=-1)
        assert is_round_closed(state, players) is True

    def test_closed_for_all_in_player_with_lower_bet(self):
        """All-in player (chips==0) with bet < current_bet does not block round close."""
        players = make_players(2)
        state = BettingRoundState(current_bet=100, last_raise_size=20, aggressor_seat=-1)
        state.has_acted = {0, 1}
        players[0].bet = 100
        players[0].chips = 900
        players[1].bet = 50    # all-in — can't pay more
        players[1].chips = 0   # chips == 0 means all-in
        assert is_round_closed(state, players) is True


# ---------------------------------------------------------------------------
# SC3 / SC4 / SC6: run_hand — full integration
# ---------------------------------------------------------------------------

class TestRunHand:
    """Integration tests for run_hand() — full single-hand lifecycle."""

    def test_run_hand_reaches_showdown(self):
        """run_hand() with mock_decision completes to showdown phase."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert state.phase == "showdown"

    def test_showdown_has_winner(self):
        """state.winner is not None after showdown."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert state.winner is not None

    def test_showdown_show_cards_true(self):
        """state.show_cards == True at showdown."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert state.show_cards is True

    def test_five_community_cards_at_showdown(self):
        """5 community cards dealt by showdown (flop 3 + turn 1 + river 1)."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert len(state.community_cards) == 5

    def test_each_player_has_two_hole_cards(self):
        """Each player received exactly 2 hole cards."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        for p in state.players:
            assert len(p.hole_cards) == 2, f"{p.id} has {len(p.hole_cards)} hole cards"

    def test_chip_conservation(self):
        """sum(p.chips) + state.pot == 4000 at end (chip conservation)."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        total = sum(p.chips for p in state.players) + state.pot
        assert total == 4000, f"Chip conservation failed: {total} != 4000"

    def test_no_negative_chips(self):
        """No player ends with negative chips."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        for p in state.players:
            assert p.chips >= 0, f"{p.id} has negative chips: {p.chips}"

    def test_does_not_mutate_original_players(self):
        """run_hand() deep-copies players — caller's list is not mutated."""
        players = make_players()
        original_chips = [p.chips for p in players]
        asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        for i, p in enumerate(players):
            assert p.chips == original_chips[i], f"Player {i} chips mutated: {p.chips} != {original_chips[i]}"

    def test_winner_is_marked(self):
        """Winning player has is_winner==True."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert state.winner is not None
        assert state.players[state.winner].is_winner is True

    def test_winner_hand_is_set(self):
        """state.winner_hand is a non-empty string at showdown."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert isinstance(state.winner_hand, str)
        assert len(state.winner_hand) > 0


# ---------------------------------------------------------------------------
# SC5: BB has_acted bug — BB gets option to act pre-flop
# ---------------------------------------------------------------------------

class TestBBOption:
    """Big blind gets the option to act (check/raise) pre-flop even with no raise."""

    def test_bb_gets_to_act_preflop(self):
        """
        Pre-flop with no raise: BB must be offered action.
        Track seats offered action via decision_fn calls.
        dealer=0, BB=seat 2, so BB should appear in action_log.
        """
        action_log = []

        async def logging_decision(player: Player, game_state: GameState) -> Action:
            action_log.append(player.id)
            # Always check/call — no raise means BB gets option
            max_bet = max((p.bet for p in game_state.players if not p.is_folded), default=0)
            if player.bet >= max_bet:
                return Action(action_type="check")
            return Action(action_type="call")

        players = make_players()
        asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=logging_decision))

        # BB is seat 2 (dealer=0, sb=1, bb=2)
        bb_id = "player-2"
        assert bb_id in action_log, f"BB ({bb_id}) was never offered action; log: {action_log}"

    def test_preflop_first_actor_is_utg(self):
        """
        Pre-flop: UTG = (dealer+3) % n = seat 3 with dealer=0.
        UTG must be the first seat in the action log.
        """
        action_log = []

        async def logging_decision(player: Player, game_state: GameState) -> Action:
            action_log.append(player.id)
            max_bet = max((p.bet for p in game_state.players if not p.is_folded), default=0)
            if player.bet >= max_bet:
                return Action(action_type="check")
            return Action(action_type="call")

        players = make_players()
        asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=logging_decision))

        # First actor pre-flop should be UTG = seat 3
        assert action_log[0] == "player-3", f"First pre-flop actor should be player-3 (UTG), got {action_log[0]}"


# ---------------------------------------------------------------------------
# SC7: mock_decision — correct behavior
# ---------------------------------------------------------------------------

class TestMockDecision:
    """mock_decision returns check when no outstanding bet, call otherwise."""

    def test_mock_decision_returns_check_when_no_bet(self):
        """mock_decision returns check when player.bet >= max other bets."""
        player = make_players(1)[0]
        player.bet = 20
        # All players have bet 20 (equal)
        game_state = GameState(
            phase="pre-flop",
            pot=40,
            players=[
                Player(id="p0", name="B0", org="O", color="r", deck="d", chips=980, bet=20),
                Player(id="p1", name="B1", org="O", color="r", deck="d", chips=980, bet=20),
            ],
        )
        result = asyncio.run(mock_decision(player, game_state))
        assert result.action_type == "check"

    def test_mock_decision_returns_call_when_bet_outstanding(self):
        """mock_decision returns call when current_bet > player.bet."""
        player = make_players(1)[0]
        player.bet = 0  # no bet posted yet
        game_state = GameState(
            phase="pre-flop",
            pot=20,
            players=[
                Player(id="p0", name="B0", org="O", color="r", deck="d", chips=980, bet=20),
                Player(id="p1", name="B1", org="O", color="r", deck="d", chips=1000, bet=0),
            ],
        )
        result = asyncio.run(mock_decision(player, game_state))
        assert result.action_type == "call"


# ---------------------------------------------------------------------------
# SC8: Early termination — all-but-one fold
# ---------------------------------------------------------------------------

class TestEarlyTermination:
    """Hand ends early without showdown when all-but-one fold."""

    def test_hand_ends_without_showdown_on_fold(self):
        """
        Decision fn that always folds (except one player) should NOT reach showdown.
        The last standing player wins without needing 5 community cards.
        """
        fold_count = [0]

        async def fold_first_three(player: Player, game_state: GameState) -> Action:
            # Fold for the first 3 voluntary actions, then check/call
            if fold_count[0] < 3:
                fold_count[0] += 1
                return Action(action_type="fold")
            max_bet = max((p.bet for p in game_state.players if not p.is_folded), default=0)
            if player.bet >= max_bet:
                return Action(action_type="check")
            return Action(action_type="call")

        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=fold_first_three))
        # Winner must be set even without showdown
        assert state.winner is not None
        # Chip conservation must still hold
        total = sum(p.chips for p in state.players) + state.pot
        assert total == 4000, f"Chip conservation failed on early termination: {total} != 4000"
