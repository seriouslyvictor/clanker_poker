"""
Tests for backend/app/engine/poker_math.py

Covers POKER-03 (all 9 hand ranks, kicker tiebreakers, board counterfeiting)
and POKER-04 (equity calculator speed and correctness).
"""
import time
import pytest
from treys import Card
from app.engine.poker_math import evaluate_hand, calculate_equity


class TestEvaluateHand:
    def test_returns_none_preflop(self):
        hole = [Card.new("Ah"), Card.new("Kd")]
        result = evaluate_hand(hole, [])
        assert result["hand_strength"] is None
        assert result["hand_name"] is None

    def test_returns_none_with_two_community_cards(self):
        hole = [Card.new("Ah"), Card.new("Kd")]
        board = [Card.new("Qh"), Card.new("Jc")]
        result = evaluate_hand(hole, board)
        assert result["hand_strength"] is None

    def test_royal_flush_scores_lowest(self):
        hole = [Card.new("Ah"), Card.new("Kh")]
        board = [Card.new("Qh"), Card.new("Jh"), Card.new("Th")]
        result = evaluate_hand(hole, board)
        assert result["hand_strength"] == 1, f"Expected 1 (Royal Flush), got {result['hand_strength']}"
        assert result["hand_name"] == "Royal Flush"

    def test_board_counterfeiting(self):
        # Player has KK; board has AA AA — player's best hand is KK + AA (Two Pair)
        # treys evaluates best 5 of 7 combinatorially
        hole = [Card.new("Kh"), Card.new("Kd")]
        board = [Card.new("Ah"), Card.new("As"), Card.new("2c"), Card.new("Jd"), Card.new("8s")]
        result = evaluate_hand(hole, board)
        assert result["hand_name"] == "Two Pair", f"Expected 'Two Pair', got '{result['hand_name']}'"

    def test_turn_evaluation(self):
        hole = [Card.new("Ah"), Card.new("Kd")]
        board = [Card.new("Qh"), Card.new("Jc"), Card.new("Th"), Card.new("2s")]
        result = evaluate_hand(hole, board)
        assert result["hand_strength"] is not None
        assert 1 <= result["hand_strength"] <= 7462

    def test_high_card_scores_highest(self):
        # 2h 7d vs Qs Jc 9h — no pair, no draw, pure high card
        hole = [Card.new("2h"), Card.new("7d")]
        board = [Card.new("Qs"), Card.new("Jc"), Card.new("9h")]
        result = evaluate_hand(hole, board)
        assert result["hand_strength"] is not None
        assert result["hand_strength"] > 6000, (
            f"Expected high card hand > 6000, got {result['hand_strength']}"
        )

    def test_kicker_tiebreaker(self):
        # Both players have a pair of aces — K kicker beats Q kicker
        board = [Card.new("As"), Card.new("2c"), Card.new("7h")]
        # Player A: pair of aces + K kicker
        hole_a = [Card.new("Ah"), Card.new("Kd")]
        result_a = evaluate_hand(hole_a, board)
        # Player B: pair of aces + Q kicker
        hole_b = [Card.new("Ah"), Card.new("Qd")]
        result_b = evaluate_hand(hole_b, board)
        assert result_a["hand_strength"] != result_b["hand_strength"], (
            "K kicker and Q kicker should produce different scores"
        )
        assert result_a["hand_strength"] < result_b["hand_strength"], (
            f"K kicker ({result_a['hand_strength']}) should beat Q kicker ({result_b['hand_strength']}) "
            "(lower score = better hand in treys)"
        )

    def test_straight_flush(self):
        hole = [Card.new("9h"), Card.new("8h")]
        board = [Card.new("7h"), Card.new("6h"), Card.new("5h")]
        result = evaluate_hand(hole, board)
        assert result["hand_name"] == "Straight Flush", f"Expected 'Straight Flush', got '{result['hand_name']}'"

    def test_four_of_a_kind(self):
        hole = [Card.new("Ah"), Card.new("As")]
        board = [Card.new("Ad"), Card.new("Ac"), Card.new("2h")]
        result = evaluate_hand(hole, board)
        assert result["hand_name"] == "Four of a Kind", f"Expected 'Four of a Kind', got '{result['hand_name']}'"

    def test_full_house(self):
        hole = [Card.new("Ah"), Card.new("As")]
        board = [Card.new("Ad"), Card.new("Kh"), Card.new("Ks")]
        result = evaluate_hand(hole, board)
        assert result["hand_name"] == "Full House", f"Expected 'Full House', got '{result['hand_name']}'"

    def test_flush(self):
        hole = [Card.new("Ah"), Card.new("Kh")]
        board = [Card.new("2h"), Card.new("7h"), Card.new("9h")]
        result = evaluate_hand(hole, board)
        assert result["hand_name"] == "Flush", f"Expected 'Flush', got '{result['hand_name']}'"

    def test_straight(self):
        # Use offsuit board to avoid Royal Flush
        hole = [Card.new("Ah"), Card.new("Kd")]
        board = [Card.new("Qh"), Card.new("Jc"), Card.new("Ts")]
        result = evaluate_hand(hole, board)
        assert result["hand_name"] == "Straight", f"Expected 'Straight', got '{result['hand_name']}'"

    def test_three_of_a_kind(self):
        hole = [Card.new("Ah"), Card.new("As")]
        board = [Card.new("Ad"), Card.new("2h"), Card.new("7d")]
        result = evaluate_hand(hole, board)
        assert result["hand_name"] == "Three of a Kind", f"Expected 'Three of a Kind', got '{result['hand_name']}'"

    def test_two_pair(self):
        hole = [Card.new("Ah"), Card.new("Kh")]
        board = [Card.new("Ad"), Card.new("Kd"), Card.new("2c")]
        result = evaluate_hand(hole, board)
        assert result["hand_name"] == "Two Pair", f"Expected 'Two Pair', got '{result['hand_name']}'"

    def test_one_pair(self):
        hole = [Card.new("Ah"), Card.new("As")]
        board = [Card.new("2h"), Card.new("7d"), Card.new("9c")]
        result = evaluate_hand(hole, board)
        assert result["hand_name"] == "Pair", f"Expected 'Pair', got '{result['hand_name']}'"


class TestCalculateEquity:
    def test_returns_valid_probability(self):
        hole = [Card.new("Ah"), Card.new("As")]
        board = [Card.new("Kh"), Card.new("Qd"), Card.new("Jc")]
        result = calculate_equity(hole, board)
        assert 0.0 <= result["win_probability"] <= 1.0

    def test_strong_hand_high_equity(self):
        # Pocket aces on neutral flop should win > 50% of the time
        hole = [Card.new("Ah"), Card.new("As")]
        board = [Card.new("2h"), Card.new("7d"), Card.new("Tc")]
        result = calculate_equity(hole, board, n_simulations=500)
        assert result["win_probability"] > 0.5, (
            f"Pocket aces on neutral flop expected > 0.5 win rate, got {result['win_probability']}"
        )

    def test_pot_odds_is_none(self):
        # pot_odds is caller responsibility — must be None from this function
        hole = [Card.new("Ah"), Card.new("Kd")]
        board = [Card.new("Qh"), Card.new("Jc"), Card.new("Th")]
        result = calculate_equity(hole, board)
        assert result["pot_odds"] is None

    def test_preflop_hand_strength_is_none(self):
        hole = [Card.new("Ah"), Card.new("Kd")]
        result = calculate_equity(hole, [], n_simulations=100)
        assert result["hand_strength"] is None
        assert 0.0 <= result["win_probability"] <= 1.0

    def test_completes_in_under_100ms(self):
        hole = [Card.new("Ah"), Card.new("As")]
        board = [Card.new("Kh"), Card.new("Qd"), Card.new("Jc")]
        start = time.perf_counter()
        result = calculate_equity(hole, board, n_simulations=1000)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1, f"Equity took {elapsed:.3f}s, expected < 0.1s"

    def test_multiway_equity(self):
        # 3 opponents — should return valid probability without crashing
        hole = [Card.new("Ah"), Card.new("As")]
        board = [Card.new("Kh"), Card.new("Qd"), Card.new("Jc")]
        result = calculate_equity(hole, board, num_opponents=3, n_simulations=200)
        assert 0.0 <= result["win_probability"] <= 1.0
