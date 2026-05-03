"""
cards.py — treys int ↔ {s, r} conversion boundary.

This module is the ONLY place in the codebase that calls TreysCard.new().
All other modules obtain treys card ints through new_card() and convert
back to display format through card_display().

Encoding contract:
  - TreysCard.new() requires 2-char ASCII string: rank_char + suit_char
    suit chars: 'h' (hearts), 's' (spades), 'd' (diamonds), 'c' (clubs)
  - The frontend types.ts Card uses unicode suit symbols: '♥', '♠', '♦', '♣'
  - This module bridges the two representations at the boundary.

NEVER pass unicode suit symbols directly to TreysCard.new() — it raises an error.
NEVER call TreysCard.new() outside this module.
"""
from treys import Card as TreysCard

# rank_int 0 = '2', rank_int 12 = 'A'  (index in '23456789TJQKA')
_RANK_INT_TO_STR: dict[int, str] = {i: r for i, r in enumerate('23456789TJQKA')}

# suit_int: 1=spades, 2=hearts, 4=diamonds, 8=clubs  (treys bit encoding)
_SUIT_INT_TO_SYMBOL: dict[int, str] = {1: '♠', 2: '♥', 4: '♦', 8: '♣'}

# unicode symbol → ASCII char required by TreysCard.new()
_SUIT_SYMBOL_TO_CHAR: dict[str, str] = {'♠': 's', '♥': 'h', '♦': 'd', '♣': 'c'}


def card_display(treys_int: int) -> dict:
    """
    Convert a treys card int to {r: str, s: str} matching types.ts Card.

    Returns:
        dict with keys 'r' (rank string e.g. 'A', 'K', 'T', '2') and
        's' (suit unicode symbol: '♠', '♥', '♦', '♣')
    """
    rank_int = TreysCard.get_rank_int(treys_int)
    suit_int = TreysCard.get_suit_int(treys_int)
    return {
        'r': _RANK_INT_TO_STR[rank_int],
        's': _SUIT_INT_TO_SYMBOL[suit_int],
    }


def new_card(r: str, s: str) -> int:
    """
    Create a treys card int from rank string and suit unicode symbol.

    Args:
        r: rank string — one of 'A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'
        s: suit unicode symbol — one of '♠', '♥', '♦', '♣'

    Returns:
        treys card int (32-bit int from TreysCard.new())

    Raises:
        KeyError: if s is not a valid suit symbol (catches encoding bugs early)
    """
    suit_char = _SUIT_SYMBOL_TO_CHAR[s]  # KeyError if invalid symbol — fail loud
    return TreysCard.new(r + suit_char)
