"""
game.py — single-hand Texas Hold'em engine.

Implements POKER-01 (full Hold'em flow), POKER-02 (action order), POKER-05 (chip tracking).

The decision seam is DecisionFn: async def make_decision(player, game_state) -> Action.
Phase 2 uses mock_decision (always call/check). Phase 4 replaces with LLM calls — zero refactor.

Action order rules:
  Pre-flop:  UTG = (dealer + 3) % n  — left of big blind
  Post-flop: SB  = (dealer + 1) % n  — first active left of dealer

Betting round close condition (BOTH must be true — see Pitfall 1 in RESEARCH.md):
  1. Every active (non-folded) player is in has_acted (voluntarily acted)
  2. All active non-all-in players have bet == current_bet

BB is NOT added to has_acted during blind posting. The BB gets added only when the
decision function is called for that seat. This prevents the infinite-loop / early-
termination bugs documented in RESEARCH.md Pitfall 1.
"""
import copy
from typing import Awaitable, Callable, Optional

from treys import Deck

from app.engine.cards import new_card, card_display
from app.engine.models import (
    Card, Action, ActionType, Player, GameState, BettingRoundState, DecisionFn
)
from app.engine.poker_math import evaluate_hand


# ---------------------------------------------------------------------------
# Type definitions
# ---------------------------------------------------------------------------

BroadcastFn = Callable[["GameState"], Awaitable[None]]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def valid_actions(player: Player, state: BettingRoundState) -> list[ActionType]:
    """
    Return the list of valid actions for a player given the current betting state.

    Rules:
      - fold:  always valid
      - check: only when call_amount == 0 (player.bet == state.current_bet)
      - call:  only when call_amount > 0
      - raise: only when player.chips > call_amount (must have chips beyond the call)
    """
    call_amount = state.current_bet - player.bet
    actions: list[ActionType] = ["fold"]

    if call_amount == 0:
        actions.append("check")
    else:
        actions.append("call")

    # Can raise only if the player has chips beyond what a call would cost
    if player.chips > call_amount:
        actions.append("raise")

    return actions


def is_round_closed(state: BettingRoundState, players: list[Player]) -> bool:
    """
    Return True when the betting round is complete.

    A round closes when ALL of the following are true:
      1. Only one active (non-folded) player remains, OR
      2. Every active player is in has_acted AND all active non-all-in players
         have bet == current_bet

    The BB gets to act even when current_bet == BB amount (Pitfall 1 guard):
    we require has_acted containment, not just bet equality.
    """
    active = [i for i, p in enumerate(players) if not p.is_folded]

    # One player standing — round over immediately
    if len(active) <= 1:
        return True

    for i in active:
        # Player hasn't had a turn yet
        if i not in state.has_acted:
            return False
        # Player owes chips and is not all-in
        if players[i].bet < state.current_bet and players[i].chips > 0:
            return False

    return True


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _next_active_seat(current: int, n_players: int, players: list[Player]) -> Optional[int]:
    """
    Return the next non-folded seat clockwise from current (exclusive).
    Returns None if no active player found (shouldn't happen when called correctly).
    """
    for offset in range(1, n_players + 1):
        candidate = (current + offset) % n_players
        if not players[candidate].is_folded:
            return candidate
    return None


def _first_active_from(start: int, n_players: int, players: list[Player]) -> Optional[int]:
    """
    Return the first non-folded seat starting from start (inclusive), scanning clockwise.
    Returns None if no active player found.
    """
    for offset in range(n_players):
        candidate = (start + offset) % n_players
        if not players[candidate].is_folded:
            return candidate
    return None


def _collect_bets_to_pot(players: list[Player], pot: int) -> int:
    """
    Collect all player bets into the pot.
    Resets each player.bet to 0 after collection.
    Returns the new pot value.
    """
    new_pot = pot + sum(p.bet for p in players)
    for p in players:
        p.bet = 0
    return new_pot


def _active_count(players: list[Player]) -> int:
    """Return the number of non-folded players."""
    return sum(1 for p in players if not p.is_folded)


# ---------------------------------------------------------------------------
# Betting round engine
# ---------------------------------------------------------------------------

async def run_betting_round(
    game_state: GameState,
    players: list[Player],
    dealer_seat: int,
    is_preflop: bool,
    big_blind: int,
    decision_fn: DecisionFn,
    broadcast_fn: Optional[BroadcastFn] = None,
) -> tuple[GameState, list[Player]]:
    """
    Run a single betting round (pre-flop, flop, turn, or river).

    Mutates players in-place (chips, bet, is_folded, action).
    Returns (game_state, players) for chaining.

    Action order:
      Pre-flop: UTG = (dealer + 3) % n
      Post-flop: first active seat starting from (dealer + 1) % n

    Phase 4 additions (D-03):
      - game_state.current_bet synced from betting_state.current_bet so
        decision.py reconstruct_valid_actions() sees the correct value
      - broadcast_fn called after each individual player action (D-03)
    """
    n = len(players)

    # Initialise betting state
    betting_state = BettingRoundState(
        current_bet=big_blind if is_preflop else 0,
        last_raise_size=big_blind,
        aggressor_seat=-1,
    )
    # Sync current_bet to GameState so DecisionFn can reconstruct valid actions (D-03)
    game_state.current_bet = betting_state.current_bet
    # has_acted starts empty — neither SB nor BB are added during blind posting

    # Determine first actor
    if is_preflop:
        nominal_first = (dealer_seat + 3) % n
        current_seat = _first_active_from(nominal_first, n, players)
    else:
        nominal_first = (dealer_seat + 1) % n
        current_seat = _first_active_from(nominal_first, n, players)

    if current_seat is None:
        # No active players — collect what's there and return
        game_state.pot = _collect_bets_to_pot(players, game_state.pot)
        return game_state, players

    # Betting loop
    while not is_round_closed(betting_state, players):
        # Skip folded players (shouldn't normally happen due to is_round_closed, but guard)
        if players[current_seat].is_folded:
            current_seat = _next_active_seat(current_seat, n, players)
            if current_seat is None:
                break
            continue

        # Request decision
        action = await decision_fn(players[current_seat], game_state)
        betting_state.has_acted.add(current_seat)

        # Process action
        action_type = action.action_type

        if action_type == "fold":
            players[current_seat].is_folded = True
            players[current_seat].action = "fold"

        elif action_type == "call":
            call_amount = betting_state.current_bet - players[current_seat].bet
            # All-in handling: cannot pay more than available chips
            actual_call = min(call_amount, players[current_seat].chips)
            players[current_seat].chips -= actual_call
            players[current_seat].bet += actual_call
            players[current_seat].action = "call"

        elif action_type == "raise":
            # Minimum raise: current_bet + last_raise_size
            min_raise_total = betting_state.current_bet + betting_state.last_raise_size
            # Use requested amount if provided and valid, otherwise fall back to minimum
            requested = action.amount if action.amount >= min_raise_total else min_raise_total
            # Cannot raise more than available chips (all-in)
            max_can_bet = players[current_seat].bet + players[current_seat].chips
            raise_to = min(requested, max_can_bet)
            # Compute raise size for future min-raise tracking
            raise_size = raise_to - betting_state.current_bet
            # Deduct from chips
            chips_to_add = raise_to - players[current_seat].bet
            players[current_seat].chips -= chips_to_add
            players[current_seat].bet = raise_to
            betting_state.last_raise_size = max(raise_size, betting_state.last_raise_size)
            betting_state.current_bet = raise_to
            betting_state.aggressor_seat = current_seat
            players[current_seat].action = "raise"

        elif action_type == "check":
            # No chips change — player passes
            players[current_seat].action = "check"

        # Update GameState players so decision_fn sees current state
        game_state.players = players
        # Sync current_bet after raise may have updated it (D-03)
        game_state.current_bet = betting_state.current_bet
        # Broadcast after each individual player action within a betting round (D-03)
        if broadcast_fn is not None:
            await broadcast_fn(game_state)

        # Early termination — only one player left
        if _active_count(players) == 1:
            break

        # Advance to next active seat
        next_seat = _next_active_seat(current_seat, n, players)
        if next_seat is None:
            break
        current_seat = next_seat

    # Collect all bets into pot after round closes
    game_state.pot = _collect_bets_to_pot(players, game_state.pot)

    # Reset player.bet for next round (Pitfall 5)
    for p in players:
        p.bet = 0

    game_state.players = players
    return game_state, players


# ---------------------------------------------------------------------------
# Private: broadcast helper
# ---------------------------------------------------------------------------

async def _maybe_broadcast(state: GameState, fn: Optional[BroadcastFn]) -> None:
    """Call broadcast_fn if provided. No-op when fn is None (Phase 2 tests unaffected)."""
    if fn is not None:
        await fn(state)


# ---------------------------------------------------------------------------
# Main hand engine
# ---------------------------------------------------------------------------

async def run_hand(
    players: list[Player],
    dealer_seat: int,
    big_blind: int,
    decision_fn: DecisionFn,
    broadcast_fn: Optional[BroadcastFn] = None,
) -> GameState:
    """
    Run a single complete Texas Hold'em hand.

    Args:
        players:      list of Player models (caller's list is NOT mutated — deep copy made)
        dealer_seat:  index of the dealer button
        big_blind:    big blind amount in chips
        decision_fn:  async callable matching DecisionFn signature
        broadcast_fn: Optional async callable receiving GameState at each phase transition.
                      Defaults to None — safe for Phase 2 tests. Phase 3 passes publish().

    Returns:
        Final GameState with phase='showdown' (or earlier if all-but-one fold).

    Hand lifecycle:
      1. Deep copy players
      2. Reset hand-start state
      3. Post blinds (SB = BB//2, BB = BB)
      4. Deal 2 hole cards per active player
      5. Pre-flop betting round
      6. Flop deal + betting
      7. Turn deal + betting
      8. River deal + betting
      9. Showdown: evaluate_hand() → award pot → set winner

    Critical: Deck() is created FRESH inside this function every call (Pitfall 2).
    """
    n = len(players)

    # Step 1: Deep copy so caller's list is not mutated
    players = copy.deepcopy(players)

    # Step 2: Reset hand-start state
    for p in players:
        p.is_folded = False
        p.bet = 0
        p.action = None
        p.is_winner = False
        p.hole_cards = []

    # Step 3: Post blinds — do NOT add SB/BB to has_acted (Pitfall 1)
    sb_seat = (dealer_seat + 1) % n
    bb_seat = (dealer_seat + 2) % n
    sb_amount = big_blind // 2

    players[sb_seat].chips -= sb_amount
    players[sb_seat].bet = sb_amount

    players[bb_seat].chips -= big_blind
    players[bb_seat].bet = big_blind

    # Step 4: Deal 2 hole cards to each player from a FRESH deck (Pitfall 2)
    deck = Deck()
    deck.shuffle()

    for p in players:
        cards_drawn = deck.draw(2)
        p.hole_cards = [Card(**card_display(c)) for c in cards_drawn]

    # Step 5: Build initial GameState (pot=0, bets tracked in player.bet)
    # Blinds are tracked via player.bet; pot starts at 0 and bets are collected
    # at the end of the pre-flop betting round
    game_state = GameState(
        phase="pre-flop",
        pot=0,
        community_cards=[],
        players=players,
        show_cards=False,
    )

    # Broadcast pre-flop state
    await _maybe_broadcast(game_state, broadcast_fn)

    # -------------------------------------------------------------------------
    # Pre-flop betting round
    # -------------------------------------------------------------------------
    game_state, players = await run_betting_round(
        game_state, players, dealer_seat, is_preflop=True,
        big_blind=big_blind, decision_fn=decision_fn, broadcast_fn=broadcast_fn,
    )

    # Early termination check
    if _active_count(players) == 1:
        final = _award_to_last_standing(game_state, players)
        await _maybe_broadcast(final, broadcast_fn)
        return final

    # -------------------------------------------------------------------------
    # Flop: deal 3 community cards
    # -------------------------------------------------------------------------
    flop_ints = deck.draw(3)
    flop_cards = [Card(**card_display(c)) for c in flop_ints]
    game_state.community_cards = flop_cards
    game_state.phase = "flop"
    game_state.players = players

    # Broadcast flop state
    await _maybe_broadcast(game_state, broadcast_fn)

    game_state, players = await run_betting_round(
        game_state, players, dealer_seat, is_preflop=False,
        big_blind=big_blind, decision_fn=decision_fn, broadcast_fn=broadcast_fn,
    )

    if _active_count(players) == 1:
        final = _award_to_last_standing(game_state, players)
        await _maybe_broadcast(final, broadcast_fn)
        return final

    # -------------------------------------------------------------------------
    # Turn: deal 1 community card
    # -------------------------------------------------------------------------
    turn_int = deck.draw(1)[0]
    turn_card = Card(**card_display(turn_int))
    game_state.community_cards = game_state.community_cards + [turn_card]
    game_state.phase = "turn"
    game_state.players = players

    # Broadcast turn state
    await _maybe_broadcast(game_state, broadcast_fn)

    game_state, players = await run_betting_round(
        game_state, players, dealer_seat, is_preflop=False,
        big_blind=big_blind, decision_fn=decision_fn, broadcast_fn=broadcast_fn,
    )

    if _active_count(players) == 1:
        final = _award_to_last_standing(game_state, players)
        await _maybe_broadcast(final, broadcast_fn)
        return final

    # -------------------------------------------------------------------------
    # River: deal 1 community card
    # -------------------------------------------------------------------------
    river_int = deck.draw(1)[0]
    river_card = Card(**card_display(river_int))
    game_state.community_cards = game_state.community_cards + [river_card]
    game_state.phase = "river"
    game_state.players = players

    # Broadcast river state
    await _maybe_broadcast(game_state, broadcast_fn)

    game_state, players = await run_betting_round(
        game_state, players, dealer_seat, is_preflop=False,
        big_blind=big_blind, decision_fn=decision_fn, broadcast_fn=broadcast_fn,
    )

    if _active_count(players) == 1:
        final = _award_to_last_standing(game_state, players)
        await _maybe_broadcast(final, broadcast_fn)
        return final

    # -------------------------------------------------------------------------
    # Showdown: evaluate hands, award pot (Pitfall 3: only called with 5 community cards)
    # -------------------------------------------------------------------------
    game_state.phase = "showdown"
    game_state.show_cards = True

    board_ints = [new_card(c.r, c.s) for c in game_state.community_cards]

    scores: dict[int, int] = {}
    for i, p in enumerate(players):
        if p.is_folded:
            continue
        hole_ints = [new_card(c.r, c.s) for c in p.hole_cards]
        result = evaluate_hand(hole_ints, board_ints)
        if result["hand_strength"] is not None:
            scores[i] = result["hand_strength"]

    # Lower score = stronger hand (treys convention)
    best_score = min(scores.values())
    winner_idx = next(i for i, s in sorted(scores.items()) if s == best_score)

    # Re-evaluate to get the hand name
    winner_hole_ints = [new_card(c.r, c.s) for c in players[winner_idx].hole_cards]
    winner_result = evaluate_hand(winner_hole_ints, board_ints)

    # Award pot to winner
    players[winner_idx].chips += game_state.pot
    players[winner_idx].is_winner = True
    game_state.pot = 0
    game_state.winner = winner_idx
    game_state.winner_hand = winner_result.get("hand_name") or ""
    game_state.players = players

    # Broadcast showdown state
    await _maybe_broadcast(game_state, broadcast_fn)

    return game_state


# ---------------------------------------------------------------------------
# Private: award pot when all-but-one fold
# ---------------------------------------------------------------------------

def _award_to_last_standing(game_state: GameState, players: list[Player]) -> GameState:
    """
    Award the pot to the last non-folded player.
    Called when all other players fold — no showdown needed.
    """
    winner_idx = next(i for i, p in enumerate(players) if not p.is_folded)
    players[winner_idx].chips += game_state.pot
    players[winner_idx].is_winner = True
    game_state.pot = 0
    game_state.winner = winner_idx
    # No hand_name since there's no showdown evaluation
    game_state.players = players
    return game_state


# ---------------------------------------------------------------------------
# Mock decision function (Phase 2 — replaced by LLM in Phase 4)
# ---------------------------------------------------------------------------

async def mock_decision(player: Player, game_state: GameState) -> Action:
    """
    Mock DecisionFn: always checks if possible, otherwise calls.
    Phase 4 replaces this with actual LLM decision calls — zero refactor needed.

    Heuristic: check if player.bet >= max bet among active players, else call.
    game.py internal BettingRoundState is not stored in GameState, so we
    reconstruct the intent by comparing bets.
    """
    max_bet = max(
        (p.bet for p in game_state.players if not p.is_folded),
        default=0
    )
    if player.bet >= max_bet:
        return Action(action_type="check")
    return Action(action_type="call")
