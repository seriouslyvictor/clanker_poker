"""
test_cards.py — tests for the cards.py treys-int conversion boundary.

Verifies:
  - new_card(r, s) -> int produces the same treys int as TreysCard.new(rank + ascii_suit)
  - card_display(treys_int) -> dict returns {r: str, s: unicode_symbol} matching types.ts Card
  - Round-trip: new_card(**card_display(x)) == x for any valid treys int
  - Invalid suit symbol raises KeyError (fail loud at boundary)
"""
import pytest
from treys import Card as TreysCard

from app.engine.cards import card_display, new_card


class TestNewCard:
    """Tests for new_card(r, s) -> int."""

    def test_ace_of_hearts(self):
        """new_card('A', '♥') must equal TreysCard.new('Ah')."""
        assert new_card('A', '♥') == TreysCard.new('Ah')

    def test_two_of_clubs(self):
        """new_card('2', '♣') must equal TreysCard.new('2c')."""
        assert new_card('2', '♣') == TreysCard.new('2c')

    def test_ten_of_diamonds(self):
        """new_card('T', '♦') must equal TreysCard.new('Td')."""
        assert new_card('T', '♦') == TreysCard.new('Td')

    def test_king_of_spades(self):
        """new_card('K', '♠') must equal TreysCard.new('Ks')."""
        assert new_card('K', '♠') == TreysCard.new('Ks')

    def test_all_suits_ace(self):
        """Verify all four suit symbols produce correct treys ints for Ace."""
        assert new_card('A', '♠') == TreysCard.new('As')
        assert new_card('A', '♥') == TreysCard.new('Ah')
        assert new_card('A', '♦') == TreysCard.new('Ad')
        assert new_card('A', '♣') == TreysCard.new('Ac')

    def test_invalid_suit_raises_key_error(self):
        """Invalid suit symbol must raise KeyError — fail loud at boundary."""
        with pytest.raises(KeyError):
            new_card('A', 'h')  # ASCII char passed instead of unicode symbol

    def test_invalid_suit_unicode_wrong_raises_key_error(self):
        """Wrong unicode character raises KeyError."""
        with pytest.raises(KeyError):
            new_card('A', '♡')  # hollow heart — not a valid suit symbol


class TestCardDisplay:
    """Tests for card_display(treys_int) -> dict."""

    def test_ace_of_hearts(self):
        """card_display of Ah treys int returns {'r': 'A', 's': '♥'}."""
        assert card_display(TreysCard.new('Ah')) == {'r': 'A', 's': '♥'}

    def test_two_of_clubs(self):
        """card_display of 2c treys int returns {'r': '2', 's': '♣'}."""
        assert card_display(TreysCard.new('2c')) == {'r': '2', 's': '♣'}

    def test_king_of_diamonds(self):
        """card_display of Kd treys int returns {'r': 'K', 's': '♦'}."""
        assert card_display(TreysCard.new('Kd')) == {'r': 'K', 's': '♦'}

    def test_ten_of_spades(self):
        """card_display of Ts treys int returns {'r': 'T', 's': '♠'}."""
        assert card_display(TreysCard.new('Ts')) == {'r': 'T', 's': '♠'}

    def test_output_keys_match_types_ts_card_shape(self):
        """Output dict must have exactly keys 'r' and 's' — matching types.ts Card."""
        result = card_display(TreysCard.new('Ah'))
        assert set(result.keys()) == {'r', 's'}

    def test_suit_values_are_unicode_symbols(self):
        """Suit values must be unicode symbols, not ASCII chars."""
        for treys_str, expected_symbol in [('Ah', '♥'), ('As', '♠'), ('Ad', '♦'), ('Ac', '♣')]:
            result = card_display(TreysCard.new(treys_str))
            assert result['s'] == expected_symbol, f"Expected '{expected_symbol}' for '{treys_str}'"


class TestRoundTrip:
    """Round-trip: new_card(**card_display(x)) == x for any valid treys int."""

    def test_round_trip_ace_of_hearts(self):
        original = TreysCard.new('Ah')
        assert new_card(**card_display(original)) == original

    def test_round_trip_two_of_clubs(self):
        original = TreysCard.new('2c')
        assert new_card(**card_display(original)) == original

    def test_round_trip_king_of_diamonds(self):
        original = TreysCard.new('Kd')
        assert new_card(**card_display(original)) == original

    def test_round_trip_ten_of_spades(self):
        original = TreysCard.new('Ts')
        assert new_card(**card_display(original)) == original

    def test_round_trip_all_ranks_hearts(self):
        """All 13 ranks round-trip correctly for hearts."""
        ranks = '23456789TJQKA'
        for r in ranks:
            original = TreysCard.new(f'{r}h')
            assert new_card(**card_display(original)) == original, f"Round-trip failed for {r}h"

    def test_round_trip_all_suits_ace(self):
        """Ace round-trips correctly for all 4 suits."""
        for suit_char, suit_symbol in [('s', '♠'), ('h', '♥'), ('d', '♦'), ('c', '♣')]:
            original = TreysCard.new(f'A{suit_char}')
            result = new_card(**card_display(original))
            assert result == original, f"Round-trip failed for A{suit_char}"
