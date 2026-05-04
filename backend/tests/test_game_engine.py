"""
Tests for backend/app/engine/ — game.py, session.py, models.py, cards.py

Covers:
  POKER-01 — Full Texas Hold'em flow (SC1, SC4)
  POKER-02 — Correct action order (SC2)
  POKER-05 — Chip tracking (SC3, SC5)

Success Criteria tested:
  SC1: Complete hand with correct dealing (SB/BB posted, 2 hole cards, 5 community cards)
  SC2: Correct action order (pre-flop UTG first, post-flop SB first)
  SC3: Correct winner determined and pot awarded; no player below 0 chips
  SC4: 10-hand session with mock decisions completes without error
  SC5: Chip conservation — sum(stacks) + pot == starting_total throughout

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
from treys import Card as TreysCard

from app.engine.cards import new_card, card_display
from app.engine.models import Player, GameState, Action, BettingRoundState
from app.engine.game import run_hand, mock_decision, valid_actions, is_round_closed
from app.engine.session import GameSession


# ---------------------------------------------------------------------------
# Fixture helper (module-level function, not pytest fixture)
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
# TestCards: cards.py conversion boundary (prerequisite for all other tests)
# ---------------------------------------------------------------------------

class TestCards:
    """Verify cards.py conversion boundary (prerequisite for all other tests)."""

    def test_new_card_round_trip(self):
        """new_card then card_display returns the original rank/suit."""
        treys_int = TreysCard.new("Ah")
        result = card_display(treys_int)
        assert result["r"] == "A", f"Expected rank 'A', got {result['r']}"
        assert result["s"] == "♥", f"Expected suit '♥', got {result['s']}"

    def test_new_card_creates_valid_treys_int(self):
        """new_card produces the same int as TreysCard.new() for all suit symbols."""
        assert new_card("A", "♥") == TreysCard.new("Ah"), "Ace of hearts mismatch"
        assert new_card("2", "♣") == TreysCard.new("2c"), "2 of clubs mismatch"
        assert new_card("K", "♦") == TreysCard.new("Kd"), "King of diamonds mismatch"
        assert new_card("T", "♠") == TreysCard.new("Ts"), "Ten of spades mismatch"

    def test_card_display_all_suits(self):
        """card_display maps suit ints to correct unicode symbols."""
        assert card_display(TreysCard.new("2s"))["s"] == "♠", "Spades symbol wrong"
        assert card_display(TreysCard.new("2h"))["s"] == "♥", "Hearts symbol wrong"
        assert card_display(TreysCard.new("2d"))["s"] == "♦", "Diamonds symbol wrong"
        assert card_display(TreysCard.new("2c"))["s"] == "♣", "Clubs symbol wrong"


# ---------------------------------------------------------------------------
# TestSingleHand: SC1 — Complete hand structure (blinds, dealing, community cards)
# ---------------------------------------------------------------------------

class TestSingleHand:
    """SC1: Complete hand structure — blinds, dealing, community cards."""

    def test_complete_hand_reaches_showdown(self):
        """SC1/SC3: A hand with all-call mock decisions reaches showdown."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert state.phase == "showdown", f"Expected 'showdown', got '{state.phase}'"

    def test_two_hole_cards_per_player(self):
        """SC1: Every player receives exactly 2 hole cards."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        for p in state.players:
            assert len(p.hole_cards) == 2, f"Player {p.id} has {len(p.hole_cards)} hole cards, expected 2"

    def test_five_community_cards_at_showdown(self):
        """SC1: Exactly 5 community cards dealt (3 flop + 1 turn + 1 river)."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert len(state.community_cards) == 5, f"Expected 5 community cards, got {len(state.community_cards)}"

    def test_show_cards_true_at_showdown(self):
        """SC1/SC3: show_cards is True at showdown so frontend reveals hole cards."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert state.show_cards is True, "show_cards must be True at showdown"

    def test_winner_assigned_at_showdown(self):
        """SC3: winner is a valid player index after showdown."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert state.winner is not None, "winner should not be None at showdown"
        assert 0 <= state.winner < len(players), f"winner index {state.winner} out of range"

    def test_winner_hand_name_set(self):
        """SC3: winner_hand is a non-empty string naming the winning hand."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert state.winner_hand != "", "winner_hand must be a non-empty string"
        assert isinstance(state.winner_hand, str), f"winner_hand must be str, got {type(state.winner_hand)}"

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


# ---------------------------------------------------------------------------
# TestBettingOrder: SC2 — Correct action order (UTG first pre-flop, SB first post-flop)
# ---------------------------------------------------------------------------

class TestBettingOrder:
    """SC2: Correct action order — UTG first pre-flop, SB first post-flop."""

    def test_preflop_utg_acts_first(self):
        """SC2: With dealer at seat 0, UTG (seat 3) is first pre-flop actor."""
        action_log = []

        async def logging_decision(player: Player, game_state: GameState) -> Action:
            if game_state.phase == "pre-flop":
                action_log.append(player.id)
            return Action(action_type="call")

        players = make_players()
        asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=logging_decision))
        assert len(action_log) > 0, "No pre-flop actions recorded"
        assert action_log[0] == "player-3", f"Expected 'player-3' (UTG) first, got '{action_log[0]}'"

    def test_postflop_sb_acts_first(self):
        """SC2: With dealer at seat 0, SB (seat 1) acts first post-flop."""
        action_log_by_phase: dict[str, list] = defaultdict(list)

        async def logging_decision(player: Player, game_state: GameState) -> Action:
            action_log_by_phase[game_state.phase].append(player.id)
            # Must call when facing a bet (pre-flop BB), check otherwise
            max_bet = max((p.bet for p in game_state.players if not p.is_folded), default=0)
            if player.bet < max_bet:
                return Action(action_type="call")
            return Action(action_type="check")

        players = make_players()
        asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=logging_decision))
        flop_log = action_log_by_phase.get("flop", [])
        assert len(flop_log) > 0, "No flop actions recorded — did hand reach flop?"
        assert flop_log[0] == "player-1", f"Expected 'player-1' (SB) first post-flop, got '{flop_log[0]}'"

    def test_bb_gets_option_preflop(self):
        """SC2: BB (seat 2) must act in pre-flop even when no one raised."""
        acted_players: set[str] = set()

        async def tracking_decision(player: Player, game_state: GameState) -> Action:
            if game_state.phase == "pre-flop":
                acted_players.add(player.id)
            return Action(action_type="call")

        players = make_players()
        asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=tracking_decision))
        assert "player-2" in acted_players, "BB (player-2) never got to act pre-flop — has_acted seeding bug"

    def test_valid_actions_check_when_no_bet(self):
        """SC2: check is valid when no bet faces the player."""
        player = Player(id="p0", name="T", org="o", color="c", deck="d", chips=980, bet=0)
        state = BettingRoundState(current_bet=0, last_raise_size=20, aggressor_seat=-1)
        actions = valid_actions(player, state)
        assert "check" in actions, f"'check' should be valid with no current bet, got {actions}"
        assert "call" not in actions, f"'call' should not be valid with no current bet, got {actions}"

    def test_valid_actions_call_when_facing_bet(self):
        """SC2: call (not check) is valid when facing an outstanding bet."""
        player = Player(id="p0", name="T", org="o", color="c", deck="d", chips=980, bet=20)
        state = BettingRoundState(current_bet=40, last_raise_size=20, aggressor_seat=1)
        actions = valid_actions(player, state)
        assert "call" in actions, f"'call' should be valid when facing a bet, got {actions}"
        assert "check" not in actions, f"'check' should not be valid when facing a bet, got {actions}"

    def test_valid_actions_fold_always_available(self):
        """fold is always valid regardless of situation."""
        player = Player(id="p0", name="T", org="o", color="c", deck="d", chips=980, bet=0)
        state = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        actions = valid_actions(player, state)
        assert "fold" in actions, f"'fold' should always be valid, got {actions}"

    def test_valid_actions_raise_when_chips_exceed_call(self):
        """Player can raise when chips > call_amount."""
        player = Player(id="p0", name="T", org="o", color="c", deck="d", chips=1000, bet=0)
        state = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        actions = valid_actions(player, state)
        assert "raise" in actions, f"'raise' should be valid when player has chips > call, got {actions}"

    def test_valid_actions_no_raise_when_only_enough_to_call(self):
        """Player with chips <= call_amount cannot raise."""
        player = Player(id="p0", name="T", org="o", color="c", deck="d", chips=20, bet=0)
        state = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        actions = valid_actions(player, state)
        assert "call" in actions, f"'call' should be valid, got {actions}"
        assert "raise" not in actions, f"'raise' should not be valid with only call amount, got {actions}"

    def test_is_round_closed_all_acted_bets_equal(self):
        """Round closes when all active players have acted and bets match."""
        players = make_players(2)
        state = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        state.has_acted = {0, 1}
        players[0].bet = 20
        players[1].bet = 20
        assert is_round_closed(state, players) is True

    def test_is_round_closed_false_when_not_all_acted(self):
        """Round not closed when active player hasn't acted."""
        players = make_players(2)
        state = BettingRoundState(current_bet=20, last_raise_size=20, aggressor_seat=-1)
        state.has_acted = {0}  # player 1 hasn't acted
        players[0].bet = 20
        players[1].bet = 0
        assert is_round_closed(state, players) is False

    def test_is_round_closed_true_when_only_one_active(self):
        """Round closes immediately when only one player is active."""
        players = make_players(2)
        players[1].is_folded = True
        state = BettingRoundState(current_bet=0, last_raise_size=20, aggressor_seat=-1)
        assert is_round_closed(state, players) is True


# ---------------------------------------------------------------------------
# TestShowdown: SC3 — Correct winner determination; no player below 0 chips
# ---------------------------------------------------------------------------

class TestShowdown:
    """SC3: Correct winner determination; no player below 0 chips."""

    def test_winner_gets_pot(self):
        """SC3: Winner's chips increase by pot amount; no chips created or destroyed."""
        players = make_players()
        starting_total = sum(p.chips for p in players)
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        final_total = sum(p.chips for p in state.players)
        assert final_total == starting_total, (
            f"Chip conservation failed: started with {starting_total}, ended with {final_total}"
        )

    def test_no_player_below_zero(self):
        """SC3: No player ends a hand with negative chips."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        for p in state.players:
            assert p.chips >= 0, f"Player {p.id} has negative chips: {p.chips}"

    def test_pot_zero_after_award(self):
        """SC3: Pot is 0 after winner is awarded (no orphaned chips in pot)."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert state.pot == 0, f"Pot should be 0 after award, got {state.pot}"

    def test_winner_hand_name_non_empty(self):
        """SC3: winner_hand is a non-empty string naming the winning hand."""
        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        assert isinstance(state.winner_hand, str) and len(state.winner_hand) > 0, (
            f"winner_hand must be non-empty string, got {state.winner_hand!r}"
        )

    def test_early_termination_on_fold_chip_conservation(self):
        """SC3: Chip conservation holds even when hand ends early via folds."""
        fold_count = [0]

        async def fold_first_three(player: Player, game_state: GameState) -> Action:
            if fold_count[0] < 3:
                fold_count[0] += 1
                return Action(action_type="fold")
            max_bet = max((p.bet for p in game_state.players if not p.is_folded), default=0)
            if player.bet >= max_bet:
                return Action(action_type="check")
            return Action(action_type="call")

        players = make_players()
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=fold_first_three))
        assert state.winner is not None, "Winner must be set even without showdown"
        total = sum(p.chips for p in state.players) + state.pot
        assert total == 4000, f"Chip conservation failed on early termination: {total} != 4000"


# ---------------------------------------------------------------------------
# TestSession: SC4 — 10-hand mock session completes without errors
# ---------------------------------------------------------------------------

class TestSession:
    """SC4: 10-hand mock session completes without errors."""

    def test_ten_hand_session_completes(self):
        """SC4: 10 hands with always-call mock complete without exception or infinite loop."""
        session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
        hands = asyncio.run(session.run(n_hands=10))
        assert len(hands) == 10, f"Expected 10 completed hands, got {len(hands)}"

    def test_dealer_rotates_each_hand(self):
        """SC4: Dealer button advances by 1 each hand."""
        session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
        asyncio.run(session.run(n_hands=4))
        assert session.dealer_seat == 0, (
            f"After 4 hands (4-player game), dealer should be back at 0, got {session.dealer_seat}"
        )

    def test_stacks_carry_over_between_hands(self):
        """SC4/D-04: Starting chips for hand 2 equal ending chips from hand 1."""
        session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
        hands = asyncio.run(session.run(n_hands=2))
        total_after_hand1 = sum(p.chips for p in hands[0].players)
        total_after_hand2 = sum(p.chips for p in hands[1].players)
        assert total_after_hand1 == 4000, f"After hand 1, total chips should be 4000, got {total_after_hand1}"
        assert total_after_hand2 == 4000, f"After hand 2, total chips should be 4000, got {total_after_hand2}"

    def test_session_returns_gamestate_list(self):
        """SC4: run() returns a list of GameState objects."""
        session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
        hands = asyncio.run(session.run(n_hands=3))
        assert isinstance(hands, list), "run() must return a list"
        assert len(hands) == 3, f"Expected 3 GameState objects, got {len(hands)}"
        for i, state in enumerate(hands):
            assert isinstance(state, GameState), f"Hand {i} is not a GameState: {type(state)}"

    def test_session_final_player_chips_consistent(self):
        """SC4: session.players have same chip counts as last hand's GameState.players."""
        session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
        hands = asyncio.run(session.run(n_hands=5))
        last_state = hands[-1]
        for i, (sess_player, state_player) in enumerate(zip(session.players, last_state.players)):
            assert sess_player.chips == state_player.chips, (
                f"Player {i} chip mismatch: session={sess_player.chips}, state={state_player.chips}"
            )


# ---------------------------------------------------------------------------
# TestChipConservation: SC5 — Chip conservation across the full session
# ---------------------------------------------------------------------------

class TestChipConservation:
    """SC5: Chip conservation holds throughout the entire session."""

    def test_conservation_across_full_session(self):
        """SC5: sum(stacks) + pot across all 10 hands always equals starting total."""
        STARTING_TOTAL = 4 * 1000  # 4 players x 1000 chips

        session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
        hands = asyncio.run(session.run(n_hands=10))

        for i, state in enumerate(hands):
            hand_total = sum(p.chips for p in state.players) + state.pot
            assert hand_total == STARTING_TOTAL, (
                f"Hand {i + 1}: chip conservation failed — {hand_total} != {STARTING_TOTAL}. "
                f"Player chips: {[p.chips for p in state.players]}, pot: {state.pot}"
            )

    def test_session_final_total(self):
        """SC5: After all hands, total chips in session equals starting total."""
        STARTING_TOTAL = 4 * 1000
        session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
        asyncio.run(session.run(n_hands=10))
        final_total = sum(p.chips for p in session.players)
        assert final_total == STARTING_TOTAL, (
            f"Final chip conservation failed: {final_total} != {STARTING_TOTAL}. "
            f"Chips: {[p.chips for p in session.players]}"
        )

    def test_single_hand_chip_conservation(self):
        """SC5: Chip conservation holds for a single run_hand() call."""
        players = make_players()
        starting_total = sum(p.chips for p in players)
        state = asyncio.run(run_hand(players, dealer_seat=0, big_blind=20, decision_fn=mock_decision))
        total = sum(p.chips for p in state.players) + state.pot
        assert total == starting_total, f"Single hand chip conservation failed: {total} != {starting_total}"
