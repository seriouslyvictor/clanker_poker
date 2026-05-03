"""
poker_math.py — thin wrapper around treys for hand evaluation and equity calculation.

treys card integer format: Card.new('Ah') returns a specific 32-bit int.
Never construct card ints manually — they must come from Card.new() to match
the treys lookup tables. Any int not from Card.new() produces garbage results.

evaluator.evaluate() argument order note:
  - Source signature: evaluate(self, hand, board)  (hand first)
  - README examples:  evaluate(board, hand)         (board first)
  Both orderings produce identical scores because the method concatenates both
  lists before scoring — order of the labels is irrelevant. This module follows
  the README convention (board first) for consistency with community examples.
  See RESEARCH.md Pitfall 1 for full explanation.

Pre-flop guard rationale:
  treys hand_size_map only supports 5, 6, 7 total cards (flop/turn/river).
  Calling evaluate() with 2 total cards (pre-flop) raises KeyError: 2.
  Guard: if len(community_cards) < 3: return hand_strength=None.
"""
import random
from treys import Card, Deck, Evaluator


_evaluator = Evaluator()  # single instance — lookup tables loaded once at import


def evaluate_hand(hole_cards: list[int], community_cards: list[int]) -> dict:
    """
    Evaluate hand strength for a given board state.

    Args:
        hole_cards: list of 2 treys card ints (from Card.new())
        community_cards: list of 3, 4, or 5 treys card ints

    Returns:
        dict with:
          - hand_strength: int (1-7462, lower=better) — None if community_cards < 3
          - hand_name: str (e.g. "Royal Flush", "Pair") — None if community_cards < 3

    Note: treys evaluates the best 5-card combination from all available cards,
    so board counterfeiting and kicker tiebreakers are handled automatically.
    """
    if len(community_cards) < 3:
        # Pre-flop guard: treys hand_size_map only supports 5, 6, 7 total cards.
        # Calling evaluate() with 2 + 0 = 2 total cards raises KeyError: 2.
        return {"hand_strength": None, "hand_name": None}

    score = _evaluator.evaluate(community_cards, hole_cards)  # README convention: board first
    rank_class = _evaluator.get_rank_class(score)
    hand_name = _evaluator.class_to_string(rank_class)
    return {"hand_strength": score, "hand_name": hand_name}


def calculate_equity(
    hole_cards: list[int],
    community_cards: list[int],
    num_opponents: int = 1,
    n_simulations: int = 1000,
) -> dict:
    """
    Monte Carlo equity calculator. Simulates random runouts to estimate win probability.

    Args:
        hole_cards: list of 2 treys card ints (from Card.new())
        community_cards: list of 0-5 treys card ints
        num_opponents: number of opponents to simulate against (default 1)
        n_simulations: number of Monte Carlo iterations (default 1000, ~10-40ms)

    Returns:
        dict with:
          - hand_strength: int | None  — treys score 1-7462 (lower=better); None if pre-flop
          - win_probability: float     — 0.0 to 1.0 inclusive
          - pot_odds: None             — caller computes: call_amount / (pot + call_amount)

    Monte Carlo algorithm:
      1. Remove seen cards (hole + community) from the full deck
      2. For each simulation: shuffle remaining deck, deal runout board + opponent holes
      3. Count wins where our hand score < ALL opponents' scores (lower = stronger)
      4. Ties count as a loss (conservative equity estimate)
    """
    wins = 0

    # Remove cards already in play from the deck
    seen = set(hole_cards + community_cards)
    remaining_deck = [c for c in Deck().cards if c not in seen]

    # How many community cards still need to be dealt to complete a 5-card board
    cards_to_deal = 5 - len(community_cards)

    for _ in range(n_simulations):
        random.shuffle(remaining_deck)
        runout_board = community_cards + remaining_deck[:cards_to_deal]

        # Evaluate our hand on the completed board (always 5+2 = 7 total cards)
        my_score = _evaluator.evaluate(runout_board, hole_cards)

        beat_all = True
        opp_start = cards_to_deal  # opponent cards start after the runout board cards
        for i in range(num_opponents):
            opp_hole = remaining_deck[opp_start + i * 2 : opp_start + i * 2 + 2]
            opp_score = _evaluator.evaluate(runout_board, opp_hole)
            if opp_score <= my_score:
                # lower score = stronger hand; ties count as a loss (conservative)
                beat_all = False
                break

        if beat_all:
            wins += 1

    # Current hand strength from the actual (non-runout) community cards
    hand_eval = evaluate_hand(hole_cards, community_cards)

    return {
        "hand_strength": hand_eval["hand_strength"],   # None if pre-flop (< 3 community cards)
        "win_probability": wins / n_simulations,
        "pot_odds": None,  # caller computes: call_amount / (pot + call_amount)
    }
