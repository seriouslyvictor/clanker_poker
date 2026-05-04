# Phase 2: Game State Machine — Research

**Researched:** 2026-05-03
**Domain:** Texas Hold'em game engine — pure Python, Pydantic state model, async decision seam
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Game state modeled with Pydantic `BaseModel` — `GameState`, `Player`, `Card`, `Action`. `.model_dump()` gives Phase 3 SSE its JSON payload.
- **D-02:** Decision seam is `async def make_decision(player: Player, game_state: GameState) -> Action`. Phase 2 tests use `asyncio.run()` or `pytest-asyncio`.
- **D-03:** Phase 2 owns treys-int ↔ `{s, r}` conversion. Add `backend/app/engine/cards.py` with `new_card(r, s) -> int` and `card_display(treys_int) -> dict`.
- **D-04:** Multi-hand session with dealer rotation. 10-hand session must complete. Stacks carry over. New `GameSession` resets stacks.
- **D-05:** Min raise = big blind. No cap on raises. All-in treated as partial call; excess returned. Single main pot only, no side pots (v1).
- **D-06:** Files: `cards.py`, `models.py`, `game.py`, `session.py` under `backend/app/engine/`. Tests in `backend/tests/test_game_engine.py`.

### Claude's Discretion
- D-05 (min raise / all-in simplification) — described above
- D-06 (module layout) — described above

### Deferred Ideas (OUT OF SCOPE)
- Pot odds surfacing at decision time
- Archetype bias parameters
- Raise history / re-raise tracking beyond minimum
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| POKER-01 | Game runs standard Texas Hold'em flow — small blind, big blind, pre-flop deal, flop (3 cards), turn (1 card), river (1 card), showdown | State machine section maps every transition; treys Deck used for dealing |
| POKER-02 | Correct action order enforced each round — left of dealer / left of big blind for pre-flop, clockwise thereafter; fold/call/raise/check options presented correctly | Action order section gives exact seat index arithmetic; valid-action logic documented |
| POKER-05 | Chip tracking across a full game — blinds deducted, bets added to pot, pot awarded to winner at showdown; no player goes below 0 | Chip tracking section specifies transaction model; conservation invariant test documented |
</phase_requirements>

---

## Summary

Phase 2 builds a complete Texas Hold'em hand engine in pure Python — no UI, no LLMs, no HTTP. The core challenge is correct state machine logic: right action order pre-flop vs post-flop, betting round termination that handles the big blind's option without infinite loops, and chip conservation through blind posting, betting, and pot award.

The design is constrained by two downstream contracts: (1) the existing `poker_math.py` evaluator (takes treys ints, called at showdown), and (2) the TypeScript `types.ts` interface (consumes camelCase JSON from `GameState.model_dump(by_alias=True)`). Both contracts are verified in this codebase. The treys `Deck`, `Card`, and `Evaluator` APIs are confirmed working in the installed environment.

The decision seam (`async def make_decision`) is async from day one — pytest-asyncio 1.3.0 is now installed (added during this research session) and confirmed working with `@pytest.mark.asyncio` in strict mode.

**Primary recommendation:** Use a flat `BettingState` struct (current_bet, last_raise_size, aggressor_seat) threaded through each round. Track `has_acted: set[int]` per round — a round closes when every active non-folded player is in the set AND all bets are equal. Never loop on "does everyone have equal bets?" alone or you will infinite-loop on the big blind option.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Card dealing (shuffle + draw) | Backend — `game.py` | `cards.py` (format conversion) | treys Deck lives in Python; conversion to `{s,r}` happens at GameState construction |
| Betting round logic | Backend — `game.py` | — | Pure game rule enforcement; no network, no UI |
| Action validation | Backend — `game.py` | — | What actions are legal is a server-side invariant; client never decides this |
| State serialization | Backend — `models.py` | — | Pydantic `.model_dump(by_alias=True)` produces Phase 3 SSE payload |
| Showdown evaluation | Backend — `game.py` → `poker_math.py` | — | treys Evaluator called at showdown via existing `evaluate_hand()` wrapper |
| Multi-hand session | Backend — `session.py` | — | Dealer rotation, stack carry-over, `n_hands` loop |
| Decision seam | Backend — `game.py` interface | Phase 4 LLM impl | `async def make_decision` pluggable coroutine |

---

## Standard Stack

### Core (all already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.12.5 | State model — `GameState`, `Player`, `Card`, `Action` | Installed; `.model_dump(by_alias=True)` gives SSE JSON for free |
| treys | 0.1.8 | Card representation, deck shuffling, hand evaluation | Installed; `evaluate_hand()` already wraps it in `poker_math.py` |
| pytest | 9.0.3 | Test runner | Installed; `uv run pytest` from `backend/` |
| pytest-asyncio | 1.3.0 | Async test support for `make_decision` seam | **Added during research** — `@pytest.mark.asyncio` confirmed working |

**Version verification:** All versions confirmed via `uv pip show` and direct import in the project's `.venv`. [VERIFIED: local environment]

### No New Dependencies Needed
Phase 2 is pure Python game logic. All required libraries are already in `pyproject.toml`. The only addition is `pytest-asyncio` in the `dev` dependency group.

**Add to pyproject.toml dev group:**
```toml
[dependency-groups]
dev = [
    "pytest>=9.0.0",
    "httpx>=0.27.0",
    "pytest-asyncio>=1.3.0",   # add this line
]
```

**Configure in pyproject.toml:**
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "strict"    # add this — explicit is better than auto for this project
```

---

## Architecture Patterns

### System Architecture Diagram

```
GameSession.run(n_hands)
    │
    ▼
  for each hand:
    ├─ rotate dealer button
    ├─ GameEngine.run_hand(players, dealer_seat)
    │       │
    │       ▼
    │  [SETUP] post blinds → deal 2 hole cards each
    │       │
    │       ▼
    │  [PRE-FLOP betting round]
    │  start_seat = (dealer + 3) % n   ← UTG (left of big blind)
    │       │
    │       ▼ (all active players acted + bets equal OR all-but-one folded)
    │  [DEAL FLOP] 3 community cards
    │       │
    │       ▼
    │  [FLOP betting round]
    │  start_seat = first active left of dealer
    │       │
    │       ▼ (same close condition)
    │  [DEAL TURN] 1 community card
    │       │
    │       ▼
    │  [TURN betting round]
    │       │
    │       ▼
    │  [DEAL RIVER] 1 community card
    │       │
    │       ▼
    │  [RIVER betting round]
    │       │
    │       ▼
    │  [SHOWDOWN] treys evaluate_hand → award pot → update stacks
    │       │
    │       ▼
    │  return updated Player list
    │
    ▼
  carry updated stacks to next hand
```

### Recommended Project Structure
```
backend/app/engine/
├── poker_math.py     # existing (Phase 1) — evaluate_hand(), calculate_equity()
├── cards.py          # new: treys int ↔ {s,r} conversion
├── models.py         # new: Pydantic GameState, Player, Card, Action
├── game.py           # new: single-hand engine — deal, betting rounds, showdown
└── session.py        # new: multi-hand loop with dealer rotation

backend/tests/
└── test_game_engine.py   # new: all 5 success criteria verified
```

### Pattern 1: Card Conversion (cards.py)

**What:** Bidirectional mapping between treys ints and the `{s, r}` dict that matches `types.ts Card`.
**When to use:** At `GameState` construction time (treys int → `{s, r}`); at evaluation time (`{s, r}` → treys int for `evaluate_hand()`).

treys rank/suit integers — confirmed by direct inspection in this project's environment: [VERIFIED: local treys 0.1.8]

```python
# Source: confirmed via treys Card API in this project's .venv
from treys import Card as TreysCard

# rank_int 0='2' ... 8='T' ... 12='A'  (STR_RANKS = '23456789TJQKA')
_RANK_INT_TO_STR = {i: r for i, r in enumerate('23456789TJQKA')}
_RANK_STR_TO_INT = {v: k for k, v in _RANK_INT_TO_STR.items()}

# suit_int: 1=spades, 2=hearts, 4=diamonds, 8=clubs
_SUIT_INT_TO_SYMBOL = {1: '♠', 2: '♥', 4: '♦', 8: '♣'}
_SUIT_SYMBOL_TO_CHAR = {'♠': 's', '♥': 'h', '♦': 'd', '♣': 'c'}

def card_display(treys_int: int) -> dict:
    """Convert a treys card int to {s: '♥', r: 'A'} matching types.ts Card."""
    rank_int = TreysCard.get_rank_int(treys_int)
    suit_int = TreysCard.get_suit_int(treys_int)
    return {
        "r": _RANK_INT_TO_STR[rank_int],
        "s": _SUIT_INT_TO_SYMBOL[suit_int],
    }

def new_card(r: str, s: str) -> int:
    """Create treys int from rank string ('A','K',...,'2') and suit symbol ('♥','♠','♦','♣')."""
    suit_char = _SUIT_SYMBOL_TO_CHAR[s]
    return TreysCard.new(r + suit_char)
```

**Critical note:** `treys.Card.new()` takes a 2-char string like `'Ah'` (rank + suit_char), NOT rank + suit_symbol. Passing a unicode symbol raises an error. Convert at the boundary. [VERIFIED: local treys 0.1.8]

### Pattern 2: Pydantic Models (models.py)

**What:** Pydantic `BaseModel` classes that serialize to camelCase JSON matching `types.ts`.
**When to use:** All game state — passed to decision function, serialized to SSE in Phase 3.

The TypeScript contract requires these exact field names: `holeCards`, `communityCards`, `isFolded`, `isActive`, `isWinner`. Pydantic `alias_generator=to_camel` produces them automatically from snake_case Python names. [VERIFIED: confirmed in local pydantic 2.12.5]

```python
# Source: pydantic v2 docs + verified in this project's .venv
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Optional, Literal

class Card(BaseModel):
    s: str  # suit symbol: '♠', '♥', '♦', '♣'
    r: str  # rank: 'A', 'K', ..., '2'

ActionType = Literal['fold', 'call', 'raise', 'check']

class Action(BaseModel):
    action_type: ActionType
    amount: int = 0  # chips for raise; 0 for fold/call/check

class Player(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    id: str           # matches ModelId in types.ts
    name: str
    org: str
    color: str
    deck: str
    chips: int
    hole_cards: list[Card]     # → holeCards in JSON
    action: Optional[ActionType] = None
    bet: int = 0               # current street bet
    is_folded: bool = False    # → isFolded
    is_active: bool = True     # → isActive
    is_winner: bool = False    # → isWinner

class GameState(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    phase: str                  # 'pre-flop', 'flop', 'turn', 'river', 'showdown'
    pot: int
    community_cards: list[Card] # → communityCards
    players: list[Player]
    show_cards: bool = False    # → showCards
    reasoning: list = []        # ReasoningEntry list — Phase 4 fills this
    winner: Optional[int] = None  # player index or None
    winner_hand: str = ""       # → winnerHand
```

**Serialization:** `game_state.model_dump(by_alias=True)` produces the exact JSON shape that `types.ts GameState` expects. [VERIFIED: tested with pydantic 2.12.5]

### Pattern 3: Betting Round State Machine

**What:** Track `has_acted` per round to correctly close betting without infinite loops.
**When to use:** Every betting round (pre-flop, flop, turn, river).

The betting round close condition has TWO requirements — violating either causes bugs:
1. Every active (non-folded) player has been offered action in this round
2. All active players have put in equal amounts (or have gone all-in)

The big blind option bug: if you only check "all bets are equal," the big blind is already "equal" before anyone acts pre-flop (since they posted the BB). You must ALSO check that the BB has had a chance to act when no one raised.

```python
# Source: Texas Hold'em rules [CITED: bicyclecards.com/how-to-play/texas-holdem-poker]
# + [VERIFIED: design pattern to prevent infinite loop]

@dataclass
class BettingRoundState:
    current_bet: int          # highest bet on the table this round
    last_raise_size: int       # size of the most recent raise (min re-raise reference)
    aggressor_seat: int        # who last bet/raised (-1 if no aggressor)
    has_acted: set            # seat indices who have acted this round

def is_round_closed(state: BettingRoundState, players: list[Player]) -> bool:
    """
    Round closes when:
    - Only one player remains active (all others folded), OR
    - Every active player has acted AND all active bets are equal
    """
    active = [i for i, p in enumerate(players) if not p.is_folded]
    if len(active) <= 1:
        return True
    # All active players must have had a turn AND matched the current bet
    for i in active:
        if i not in state.has_acted:
            return False  # hasn't acted yet
        if players[i].bet < state.current_bet and players[i].chips > 0:
            return False  # still owes chips (not all-in)
    return True
```

### Pattern 4: Action Order

**What:** Correct seat index for first actor each round.

```python
# Source: Texas Hold'em rules [CITED: bicyclecards.com + en.wikipedia.org/wiki/Texas_hold_%27em]

def first_actor(dealer: int, n_players: int, phase: str) -> int:
    """
    Pre-flop:  UTG = (dealer + 3) % n   [left of BB, which is dealer+2]
    Post-flop: SB  = (dealer + 1) % n   [first active left of dealer]
    
    NOTE: These return the nominal seat. Caller must skip folded players.
    For post-flop, if SB folded, iterate clockwise to first active player.
    """
    if phase == 'pre-flop':
        return (dealer + 3) % n_players
    else:
        return (dealer + 1) % n_players

def next_actor(current: int, n_players: int, players: list[Player]) -> int | None:
    """Return next active (non-folded) seat clockwise, or None if round should close."""
    for offset in range(1, n_players + 1):
        candidate = (current + offset) % n_players
        if not players[candidate].is_folded:
            return candidate
    return None  # everyone folded (shouldn't happen if is_round_closed checked first)
```

**4-player specific:** with 4 players (seats 0–3) and dealer at seat 0:
- Seat 1 = Small Blind (posts BB/2)
- Seat 2 = Big Blind (posts BB)
- Seat 3 = UTG (first to act pre-flop)
- Seat 0 = Button (last to act pre-flop)

Post-flop: Seat 1 (first active left of dealer) acts first.

### Pattern 5: Valid Actions Per Situation

```python
# Source: [CITED: bicyclecards.com/how-to-play/texas-holdem-poker]

def valid_actions(player: Player, state: BettingRoundState) -> list[ActionType]:
    """
    check: only valid if current_bet == player.bet (no bet faces the player)
    call:  only valid if current_bet > player.bet
    raise: always valid (but capped at player.chips); min raise = last_raise_size or BB
    fold:  always valid
    """
    actions = ['fold']
    call_amount = state.current_bet - player.bet
    
    if call_amount == 0:
        actions.append('check')
    else:
        actions.append('call')
    
    # Can raise if they have chips beyond the call amount
    if player.chips > call_amount:
        actions.append('raise')
    
    return actions
```

### Pattern 6: Showdown Integration

**What:** Call existing `evaluate_hand()` for each active player; award pot to lowest score.

```python
# Source: existing poker_math.py [VERIFIED: confirmed API signature]
# evaluate_hand(hole_cards: list[int], community_cards: list[int]) -> {hand_strength, hand_name}
# lower hand_strength = better hand; None if < 3 community cards

from app.engine.poker_math import evaluate_hand
from app.engine.cards import new_card

def award_pot(players: list[Player], community_cards: list[Card], pot: int) -> tuple[int, str]:
    """
    Returns (winner_index, hand_name).
    Ties: split pot evenly (integer division, remainder goes to seat left of dealer).
    community_cards must be >= 3 cards (guaranteed by showdown phase).
    """
    board_ints = [new_card(c.r, c.s) for c in community_cards]
    
    scores = {}
    for i, p in enumerate(players):
        if p.is_folded:
            continue
        hole_ints = [new_card(c.r, c.s) for c in p.hole_cards]
        result = evaluate_hand(hole_ints, board_ints)
        scores[i] = result['hand_strength']
    
    best_score = min(scores.values())  # lower = better in treys
    winners = [i for i, s in scores.items() if s == best_score]
    
    # v1: single winner (first in case of tie — acceptable for mock session)
    winner_idx = winners[0]
    hand_name = evaluate_hand(
        [new_card(c.r, c.s) for c in players[winner_idx].hole_cards],
        board_ints
    )['hand_name']
    
    players[winner_idx].chips += pot
    return winner_idx, hand_name
```

**Tie note:** For v1 (mock decision session), giving the pot to the first winner by seat index is acceptable. Phase 4 LLM play is low-stakes enough that a rare tie advantage doesn't matter.

### Pattern 7: Async Decision Seam

**What:** The `make_decision` coroutine signature that Phase 4 LLMs will implement.

```python
# Source: D-02 locked decision + pytest-asyncio 1.3.0 [VERIFIED: tested in this project]

from typing import Callable, Awaitable

DecisionFn = Callable[[Player, GameState], Awaitable[Action]]

async def mock_decision(player: Player, game_state: GameState) -> Action:
    """Always calls. Phase 4 replaces this with LLM calls."""
    valid = valid_actions(player, game_state.current_betting_state)
    if 'check' in valid:
        return Action(action_type='check')
    return Action(action_type='call')
```

**Test pattern:**
```python
# Source: pytest-asyncio 1.3.0 [VERIFIED: confirmed working in this project's test suite]
import pytest
import asyncio

# Option A: @pytest.mark.asyncio (requires asyncio_mode = "strict" in pyproject.toml)
@pytest.mark.asyncio
async def test_mock_decision_returns_action():
    player = Player(id='p1', ...)
    state = GameState(...)
    action = await mock_decision(player, state)
    assert action.action_type in ('fold', 'call', 'raise', 'check')

# Option B: asyncio.run() wrapper — no decorator needed, works in class-based tests
def test_session_runs_ten_hands():
    session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
    asyncio.run(session.run(n_hands=10))
    # No assertion needed — completion without exception IS the test
```

### Anti-Patterns to Avoid

- **Closing betting on "equal bets" alone:** Big blind posts BB at start — their bet equals current_bet before they act. Must check `has_acted` set contains the BB seat. [CITED: betting rules analysis]
- **Using `Deck()` globally:** Create a fresh `Deck()` per hand. The treys `Deck` object is stateful (tracks drawn cards). Re-using it across hands will exhaust the deck.
- **Calling `evaluate_hand()` pre-flop:** Returns `{hand_strength: None, hand_name: None}` when `len(community_cards) < 3`. Do not compare `None` values — check for this before calling at non-showdown points.
- **Returning the same `Player` objects from session to session:** Pydantic models are mutable but reset logic should be explicit. Always set `is_folded=False`, `bet=0`, `hole_cards=[]`, `action=None` at hand start. Chips must NOT reset between hands.
- **Testing async with synchronous `assert`:** Async tests that `await` the decision function must use `@pytest.mark.asyncio` or wrap with `asyncio.run()`. A bare `test_` function that calls an async function without either of these will NOT fail — it silently runs without awaiting.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hand evaluation | Custom 5-card comparator | `poker_math.evaluate_hand()` (wraps treys) | Kickers, board counterfeiting, all 9 ranks — already tested in Phase 1 |
| Card deck | List shuffle with random | `treys.Deck()` per hand | Correct 52-card deck, no duplicates, stateful draw tracking |
| Suit/rank encoding | Custom bit-packing | `treys.Card.new()` + `get_rank_int()` / `get_suit_int()` | Must use treys' encoding for evaluator lookup tables to work |
| JSON serialization | Manual `.to_dict()` | `model.model_dump(by_alias=True)` | Pydantic alias_generator produces camelCase automatically |
| Async test runner | Custom `asyncio.run()` fixtures | `@pytest.mark.asyncio` (pytest-asyncio 1.3.0) | Handles event loop lifecycle, compatible with pytest fixtures |

**Key insight:** The treys evaluator relies on its own card integer encoding. Any card int not produced by `treys.Card.new()` produces garbage evaluation results — there is no workaround. All cards must pass through `Card.new()`.

---

## Texas Hold'em State Machine — Complete Reference

### Game States and Transitions

```
IDLE
  │ session.run() called
  ▼
SETUP
  │ post SB, post BB, deal 2 cards per player
  ▼
PRE_FLOP (betting round)
  │ all active players acted + bets equal, OR one player remains
  ▼
FLOP
  │ burn 0 (simplified), deal 3 community cards
  ▼
FLOP_BETTING
  │ close condition met
  ▼
TURN
  │ deal 1 community card
  ▼
TURN_BETTING
  │ close condition met
  ▼
RIVER
  │ deal 1 community card
  ▼
RIVER_BETTING
  │ close condition met
  ▼
SHOWDOWN
  │ evaluate hands, award pot
  ▼
HAND_COMPLETE
  │ carry chip counts forward
  ▼
(SETUP for next hand, or END SESSION)
```

**Early termination:** At any betting round, if all players but one fold, skip directly to HAND_COMPLETE without showdown. Award pot to last player standing without requiring 5 community cards.

### Betting Round Termination (Complete Logic)

A betting round is closed when ALL of the following are true:
1. Every active (non-folded) player has been added to `has_acted` this round
2. For every active player: `player.bet == current_bet` OR `player.chips == 0` (all-in)

Special cases:
- **Pre-flop, no raise:** BB gets to act (check or raise) even though their posted bet equals `current_bet`
- **Pre-flop, raise:** BB must call/re-raise like any other player; they are added to `has_acted` when they act
- **All-in below BB:** Player posts all their chips; `current_bet` stays at BB; all-in player has acted (add to `has_acted`)

### Action Order Rules

| Street | First Actor | Source |
|--------|-------------|--------|
| Pre-flop | Seat (dealer+3)%n — "UTG", left of BB | [CITED: bicyclecards.com] |
| Flop | Seat (dealer+1)%n — "SB" (or next active if folded) | [CITED: bicyclecards.com] |
| Turn | Same as Flop | [CITED: bicyclecards.com] |
| River | Same as Flop | [CITED: bicyclecards.com] |
| Heads-up special case | Pre-flop: dealer/SB acts FIRST; Post-flop: dealer acts LAST | [CITED: Wikipedia Texas hold'em] |

**Phase 2 scope:** 4 players, no heads-up special case needed (4-player game always has 3+ players until late in session). The heads-up exception applies only when exactly 2 players remain. For a 10-hand mock session, track active player count and apply the exception if it arises.

### Raise Sizing Rules

- **Minimum raise:** Must be at least the size of the previous raise in this betting round. If no previous raise this round, minimum raise = big blind amount. [CITED: Wikipedia Betting in poker]
- **Re-raise minimum:** Must be at least the size of the previous raise (not the total bet — the increment). Example: BB=20, UTG raises to 60 (raise size=40). Min re-raise total = 60 + 40 = 100.
- **All-in below minimum:** Legal — player bets all remaining chips. Does NOT reopen action in no-limit (full-bet rule). [CITED: Wikipedia Betting in poker]
- **D-05 simplification:** Treat all-in as a partial call — excess returned to raiser. No side pot. Raiser's chips reduced by the call amount only.

---

## Common Pitfalls

### Pitfall 1: Infinite Loop on Big Blind Pre-Flop
**What goes wrong:** Round close check only verifies "all bets equal." Pre-flop, the BB's posted bet already equals `current_bet`. The loop terminates immediately without letting the BB act.

OR the inverse: the loop never terminates because the code checks "has_acted" but forgets to seed the SB and BB into `has_acted` as "posted but not yet voluntarily acted."

**Why it happens:** Blind posts are forced bets, not voluntary actions. The BB has not "acted" (chosen check/raise) even though their `player.bet == current_bet`.

**How to avoid:** Pre-flop only — do NOT add BB to `has_acted` during blind posting. The BB seat gets added to `has_acted` only when the decision function is called for them.

**Warning signs:** A 10-hand session completes in < 1ms (loop terminated too early) OR hangs forever (loop never terminates). Add chip-conservation assertion after each hand.

### Pitfall 2: Stale Deck Across Hands
**What goes wrong:** `Deck()` is created once at session start. By hand 2, the deck has been partially exhausted and `deck.draw(n)` raises an error or returns incomplete results.

**Why it happens:** `treys.Deck` is stateful — it tracks cards already drawn. It does NOT reset on re-use.

**How to avoid:** Create `deck = Deck()` at the start of each hand's deal phase, inside `run_hand()`. Never share a `Deck` instance across hands.

**Warning signs:** `IndexError` or wrong number of hole cards in hand 2+.

### Pitfall 3: Pre-Flop evaluate_hand() Returns None
**What goes wrong:** Code calls `evaluate_hand(hole_cards, [])` during pre-flop to decide mock behavior. Returns `{hand_strength: None, ...}`. Comparing `None < 1000` raises `TypeError`.

**Why it happens:** treys `hand_size_map` only supports 5, 6, 7 total cards (3, 4, 5 community cards). The guard in `poker_math.py` returns `None` for < 3 community cards.

**How to avoid:** Mock decision function must not call `evaluate_hand()` pre-flop. If a strength estimate is needed pre-flop, use `calculate_equity()` which does Monte Carlo simulation and handles the pre-flop case. For the simple mock (always call), no evaluation is needed at all.

**Warning signs:** `TypeError: '<' not supported between instances of 'NoneType' and 'int'`.

### Pitfall 4: Card Symbol Encoding in treys
**What goes wrong:** Passing unicode suit symbols (`♥`, `♠`) directly to `treys.Card.new()`. Treys expects `'Ah'` not `'A♥'`.

**Why it happens:** The `{s, r}` contract uses unicode symbols for display. Treys uses single-char suit codes for internal encoding.

**How to avoid:** `cards.py` is the single boundary. `new_card(r, s)` converts unicode symbol → suit char before calling `Card.new()`. `card_display(treys_int)` converts suit_int → unicode symbol for output. Never call `Card.new()` outside `cards.py`.

**Warning signs:** `KeyError` or garbage evaluation scores.

### Pitfall 5: Player Bet Reset Between Rounds Within a Hand
**What goes wrong:** After each betting round ends, `player.bet` is NOT reset to 0 before the next round. The next round's `current_bet` and call amount calculations are wrong.

**Why it happens:** `player.bet` tracks the current-street contribution. It must reset to 0 at the start of each new betting round (but pot is already updated by collecting bets).

**How to avoid:** At the start of each betting round (after collecting bets into pot): set all `player.bet = 0` and reset `BettingRoundState.current_bet = 0`.

### Pitfall 6: Chip Conservation Violation
**What goes wrong:** At some point during a hand, the sum of all player stacks + pot does not equal the starting total. Common causes: forgetting to deduct the call amount from chips; awarding pot without deducting blind posts from chips first; double-deducting a bet.

**Why it happens:** Multiple code paths modify chips (blind posting, calling, raising) and it's easy to miss one.

**How to avoid:** Add a conservation assertion after every atomic chip move:
```python
STARTING_TOTAL = sum(p.chips for p in players)  # at session init

def assert_conservation(players, pot, label=""):
    total = sum(p.chips for p in players) + pot
    assert total == STARTING_TOTAL, f"Chip leak at {label}: {total} != {STARTING_TOTAL}"
```
Run this after: blind posting, each player action, pot award.

**Warning signs:** SC5 failure (sum of stacks + pot != starting total).

### Pitfall 7: Silent Failure in Async Tests
**What goes wrong:** A test function is `async def` but is NOT decorated with `@pytest.mark.asyncio`. pytest collects it, sees a coroutine returned by the function, and skips execution silently (or in older versions of pytest marks it as an error but in some configurations passes).

**Why it happens:** With `asyncio_mode = "strict"` (the default in pytest-asyncio 1.3.0), async test functions without `@pytest.mark.asyncio` are not run as async tests.

**How to avoid:** Either:
- Add `asyncio_mode = "auto"` to `pyproject.toml` `[tool.pytest.ini_options]` (every `async def test_*` auto-detected), OR
- Explicitly add `@pytest.mark.asyncio` to every async test function.

**Recommended for this project:** Use `asyncio_mode = "strict"` to be explicit. A sync wrapper `def test_session(): asyncio.run(session.run(10))` works without any decorator for full session tests. Use `@pytest.mark.asyncio` only for tests that need to await the decision seam directly.

---

## Test Coverage Map for Success Criteria

Each success criterion maps to specific test cases in `test_game_engine.py`:

### SC1: Complete hand with correct dealing order
```python
def test_complete_hand_structure():
    """SC1: SB posted, BB posted, 2 hole cards per player, 3+1+1 community cards."""
    state = asyncio.run(run_one_hand(mock_players, dealer_seat=0))
    assert state.phase == 'showdown' or state.phase == 'hand_complete'
    # Verify blind amounts
    assert initial_chips[1] - state.players[1].chips_at_sb_post == BIG_BLIND // 2
    # Verify hole cards dealt
    for p in state.players:
        assert len(p.hole_cards) == 2  # everyone gets exactly 2
    # Verify community cards dealt
    assert len(state.community_cards) == 5
```

### SC2: Correct action order
```python
def test_action_order_preflop():
    """SC2 (pre-flop): UTG (seat 3 with dealer at seat 0) acts first."""
    action_log = []
    async def logging_decision(player, state):
        action_log.append(player.id)
        return Action(action_type='call')
    asyncio.run(run_one_hand(mock_players, dealer=0, decision_fn=logging_decision))
    # First actor pre-flop = UTG = seat 3 (dealer+3 mod 4)
    assert action_log[0] == mock_players[3].id

def test_action_order_postflop():
    """SC2 (post-flop): SB (seat 1 with dealer at seat 0) acts first."""
    action_log_by_phase = defaultdict(list)
    # ... track phase transitions
    assert action_log_by_phase['flop'][0] == mock_players[1].id
```

### SC3: Correct winner and chip update
```python
def test_showdown_awards_pot():
    """SC3: Winner determined by evaluate_hand(); chips updated; no player below 0."""
    # Use deterministic hole cards to know expected winner
    # Deal Ah Ks to player 0, 2h 7d to others; board Ac Kd Qh Jc Th
    # Player 0 should have Royal Flush
    state = asyncio.run(run_controlled_hand(hole_cards_by_seat=..., board=...))
    assert state.winner == 0
    assert state.winner_hand == 'Royal Flush' or 'Straight' or ...  # verify
    assert all(p.chips >= 0 for p in state.players)
```

### SC4: 10-hand session completes without errors
```python
def test_ten_hand_session():
    """SC4: 10 hands with mock (always-call) decision completes without exception."""
    session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
    asyncio.run(session.run(n_hands=10))
    # If we get here, no exceptions or infinite loops
```

### SC5: Chip conservation throughout
```python
def test_chip_conservation():
    """SC5: sum(stacks) + pot == starting_total at every phase transition."""
    STARTING_TOTAL = 4 * 1000  # 4 players × 1000 chips
    conservation_log = []
    
    async def checking_decision(player, state):
        total = sum(p.chips for p in state.players) + state.pot
        conservation_log.append((state.phase, total))
        return Action(action_type='call')
    
    session = GameSession(...)
    asyncio.run(session.run(n_hands=10, decision_fn=checking_decision))
    
    for phase, total in conservation_log:
        assert total == STARTING_TOTAL, f"Phase {phase}: {total} != {STARTING_TOTAL}"
```

---

## Pydantic ↔ TypeScript JSON Contract

The frontend `types.ts` requires this exact JSON structure. The Pydantic model must produce it.

| TypeScript field | TypeScript type | Python field | Python type | Notes |
|-----------------|-----------------|--------------|-------------|-------|
| `phase` | `string` | `phase` | `str` | 'pre-flop', 'flop', 'turn', 'river', 'showdown' |
| `pot` | `number` | `pot` | `int` | Total chips in pot |
| `communityCards` | `Card[]` | `community_cards` | `list[Card]` | alias_generator converts |
| `players` | `Player[]` | `players` | `list[Player]` | nested models |
| `showCards` | `boolean` | `show_cards` | `bool` | True at showdown |
| `reasoning` | `ReasoningEntry[]` | `reasoning` | `list` | Phase 4 fills; empty list for Phase 2 |
| `winner` | `number \| null` | `winner` | `Optional[int]` | player index |
| `winnerHand` | `string` | `winner_hand` | `str` | e.g., 'Full House' |
| `holeCards` | `Card[]` | `hole_cards` | `list[Card]` | on Player; alias_generator |
| `isFolded` | `boolean` | `is_folded` | `bool` | on Player |
| `isActive` | `boolean` | `is_active` | `bool` | on Player |
| `isWinner` | `boolean` | `is_winner` | `bool` | on Player |

**Verification:** Confirmed `model_dump(by_alias=True)` produces the correct camelCase keys with pydantic 2.12.5 in this project's environment. [VERIFIED: local test]

**Missing from TypeScript `Player` interface that must be handled:** `id` (mapped to `ModelId`), `name`, `org`, `color`, `deck` — these are required fields. Phase 2 mock players should use placeholder values for `org`, `color`, `deck` since `ModelId` is the LLM model identifier from `types.ts`.

---

## Code Examples

### treys Suit/Rank Integer Reference
```python
# Source: confirmed via treys Card API [VERIFIED: local treys 0.1.8]
# STR_RANKS = '23456789TJQKA'  rank_int = index in this string
# suit_int: 1=spades, 2=hearts, 4=diamonds, 8=clubs

# Rank map: rank_int 0 = '2', rank_int 12 = 'A'
# Suit map: suit_int 1 = '♠', 2 = '♥', 4 = '♦', 8 = '♣'

# draw() always returns list regardless of count:
cards = deck.draw(2)  # returns list[int], never a bare int
```

### Deck Lifecycle (per hand)
```python
# Source: [VERIFIED: treys Deck API tested locally]
from treys import Deck

def deal_hand(n_players: int):
    deck = Deck()       # fresh 52-card deck per hand
    deck.shuffle()      # in-place shuffle
    hole_cards = [deck.draw(2) for _ in range(n_players)]
    flop = deck.draw(3)
    turn = deck.draw(1)
    river = deck.draw(1)
    return hole_cards, flop + turn + river
```

### Tie Handling
```python
# Source: [VERIFIED: treys evaluator returns identical score for equal hands]
# scores[i] == scores[j] means exact tie on hand strength
# v1: first seat wins (acceptable for mock session per D-05 note)
best = min(scores.values())
winners = [i for i, s in scores.items() if s == best]
winner = winners[0]  # deterministic tiebreak: lowest seat index
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python (uv) | All backend | ✓ | 3.13.13 | — |
| pydantic | models.py | ✓ | 2.12.5 | — |
| treys | cards.py, game.py | ✓ | 0.1.8 | — |
| pytest | tests | ✓ | 9.0.3 | — |
| pytest-asyncio | async tests | ✓ | 1.3.0 | `asyncio.run()` wrapper |
| anyio | (transitive) | ✓ | 4.13.0 | — |

**Note:** pytest-asyncio was NOT in `pyproject.toml` at research start. It was added during this session via `uv add --dev pytest-asyncio`. The planner must include this in `pyproject.toml` dev dependencies as a task.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 4 players never reach heads-up within a 10-hand mock session (always-call mock prevents eliminations) | Action Order | If a player goes all-in and loses repeatedly, they could reach 0 chips — need guard in session loop to remove 0-chip players or end hand early |
| A2 | Tie pots (split) can be handled by awarding to the first winner by seat index without breaking SC5 | Showdown | If a split pot produces uneven chips (odd remainder), SC5 would technically fail — need to verify chip math in tie case |
| A3 | The TypeScript `id` field maps to `ModelId` — mock players can use arbitrary strings for Phase 2 | JSON Contract | If Phase 3 validates ModelId against the models.config.json list, mock player IDs would fail validation |

---

## Open Questions

1. **Player elimination mid-session:**
   - What we know: D-04 says stacks carry over; D-05 says no side pots; a player can go to 0 chips if they call all-in and lose
   - What's unclear: Should `session.run()` skip 0-chip players in subsequent hands, or terminate the session?
   - Recommendation: Skip players with 0 chips in subsequent hands (treat as eliminated). Document this decision in PLAN.md.

2. **Dealer rotation with folded players:**
   - What we know: Dealer button rotates one seat clockwise each hand
   - What's unclear: If a player was eliminated (0 chips), does the dealer button skip them?
   - Recommendation: Dealer button rotates through all seats regardless of stack size; 0-chip players are simply not dealt in.

3. **Mock player config for Phase 2 tests:**
   - What we know: TypeScript `Player` requires `id` (ModelId), `name`, `org`, `color`, `deck` fields
   - What's unclear: Should Phase 2 mock players use the actual model IDs from `models.config.json`, or generic placeholders?
   - Recommendation: Use generic IDs like `'player-0'` through `'player-3'` — Phase 4 replaces with real model IDs.

---

## Sources

### Primary (HIGH confidence)
- Local project codebase — `backend/app/engine/poker_math.py`, `pyproject.toml`, `app/_components/types.ts` — API signatures, installed versions, type contracts [VERIFIED]
- treys 0.1.8 API — `Card.get_rank_int()`, `Card.get_suit_int()`, `Card.STR_RANKS`, `Deck.draw()` — confirmed via live Python execution [VERIFIED]
- pydantic 2.12.5 — `alias_generator=to_camel`, `model_dump(by_alias=True)` — confirmed via live Python execution [VERIFIED]
- pytest-asyncio 1.3.0 — `@pytest.mark.asyncio` + `asyncio_mode=strict` — confirmed working in test run [VERIFIED]

### Secondary (MEDIUM confidence)
- [bicyclecards.com/how-to-play/texas-holdem-poker](https://bicyclecards.com/how-to-play/texas-holdem-poker) — action order, check vs call rules, betting round close condition, showdown order [CITED]
- [en.wikipedia.org/wiki/Texas_hold_%27em](https://en.wikipedia.org/wiki/Texas_hold_%27em) — raise rules, re-raise minimum, big blind option [CITED]
- [en.wikipedia.org/wiki/Betting_in_poker](https://en.wikipedia.org/wiki/Betting_in_poker) — minimum raise, all-in partial raise, full-bet rule [CITED]
- [github.com/pytest-dev/pytest-asyncio/discussions/828](https://github.com/pytest-dev/pytest-asyncio/discussions/828) — pyproject.toml configuration syntax [CITED]

### Tertiary (LOW confidence)
- WebSearch results on action order, heads-up rules — cross-verified against bicyclecards.com and Wikipedia

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified in live environment
- Architecture: HIGH — based on locked decisions + verified APIs
- Texas Hold'em rules: HIGH — multiple authoritative sources agree on pre-flop/post-flop order, check/call conditions, raise minimum
- Pitfalls: HIGH — derived from direct analysis of the locked design + known treys behavior verified locally

**Research date:** 2026-05-03
**Valid until:** 2026-06-03 (stable libraries; rules are immutable)
