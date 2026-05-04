---
phase: 02-game-state-machine
reviewed: 2026-05-03T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - backend/app/engine/cards.py
  - backend/app/engine/models.py
  - backend/app/engine/game.py
  - backend/app/engine/session.py
  - backend/tests/test_cards.py
  - backend/tests/test_models.py
  - backend/tests/test_session.py
  - backend/tests/test_game_engine.py
findings:
  critical: 0
  warning: 5
  info: 4
  total: 9
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed the full game engine layer (cards, models, game, session) and all associated tests. The architecture is clean and well-documented. The boundary contract between treys ints and display dicts is correctly enforced. The betting round loop correctly avoids the BB has_acted seeding bug documented in RESEARCH.md. No critical (security, data-loss, crash) issues were found.

Five warnings were identified — all are correctness risks that could cause incorrect game behavior or silent failures in production. Four info items flag dead code or minor quality issues.

---

## Warnings

### WR-01: Double bet-reset in `run_betting_round` zeros bets that were already zeroed

**File:** `backend/app/engine/game.py:246-250`

**Issue:** `_collect_bets_to_pot` (line 125-128) already resets every `player.bet` to 0 as part of collection. The explicit loop at lines 249-250 resets them a second time. This is harmless today but is a latent bug magnet: if `_collect_bets_to_pot` is ever changed to not reset bets (e.g., to support partial collection for side pots in v2), the second reset will silently mask missing collection instead of raising an error. The loop also creates a false impression that bets survive `_collect_bets_to_pot`.

**Fix:** Remove the redundant reset loop (lines 249-250). If the intent is defensive belt-and-suspenders, add an assertion instead:

```python
# After collect:
game_state.pot = _collect_bets_to_pot(players, game_state.pot)
assert all(p.bet == 0 for p in players)  # _collect_bets_to_pot guarantees this
```

---

### WR-02: `run_betting_round` does not validate that actions returned by `decision_fn` are legal

**File:** `backend/app/engine/game.py:191-231`

**Issue:** `decision_fn` is called at line 191 and its returned `action_type` is consumed directly. No check is made against `valid_actions()`. If a decision function (including a future LLM-backed one) returns `"check"` when the player owes chips, the check branch (line 228) silently accepts it — the player pays nothing and the round eventually closes with an unequal bet, breaking chip conservation. Similarly, `"call"` when `call_amount == 0` is harmlessly accepted but incorrect.

`valid_actions()` already exists specifically to compute the legal set. It is only used in tests, never inside the engine itself.

**Fix:** After receiving the action, clamp to legal options:

```python
action = await decision_fn(players[current_seat], game_state)
legal = valid_actions(players[current_seat], betting_state)
if action.action_type not in legal:
    # Fallback: choose the safest legal action
    action = Action(action_type="call" if "call" in legal else "check")
```

---

### WR-03: `calculate_equity` can run off the end of `remaining_deck` with multiple opponents

**File:** `backend/app/engine/poker_math.py:91-108`

**Issue:** `remaining_deck` has `len(full_deck) - len(seen)` cards. For each simulation, the code slices `remaining_deck[:cards_to_deal]` for the runout board and then `remaining_deck[opp_start + i*2 : opp_start + i*2 + 2]` for each opponent's hole cards. With enough opponents and community cards already dealt, the slice may silently return fewer than 2 cards (Python slice never raises `IndexError`). An opponent dealt 0 or 1 cards causes `_evaluator.evaluate()` to raise an uncaught exception or — worse — compute a garbage score that silently distorts equity.

With 4 opponents and 0 community cards: cards needed = 5 (board) + 8 (holes) = 13. A shuffled 52-card deck minus 2 (hole cards) = 50 cards, so the common case is fine. But with 3 opponents and a nearly-complete board (4 community cards), cards needed = 1 + 6 = 7, still fine. The risk materialises with degenerate inputs (e.g., `num_opponents=20`), but there is no guard.

**Fix:** Add a guard before the simulation loop:

```python
cards_needed = cards_to_deal + num_opponents * 2
if len(remaining_deck) < cards_needed:
    raise ValueError(
        f"Not enough cards: need {cards_needed}, have {len(remaining_deck)}. "
        f"Reduce num_opponents or check community_cards."
    )
```

---

### WR-04: `session.run()` chip sync uses index-based access that silently misaligns if `GameState.players` order diverges from `self.players`

**File:** `backend/app/engine/session.py:101-102`

**Issue:** Chip carry-over is written as:

```python
for i, returned_player in enumerate(final_state.players):
    self.players[i].chips = returned_player.chips
```

`run_hand` deep-copies `self.players` and passes them as the `players` list. The returned `GameState.players` is set to the same deep-copied list (mutated in place). The order is therefore guaranteed to be the same today. However, the assumption is load-bearing and completely invisible — no assertion, no id cross-check. If `run_hand` is ever changed to sort, filter, or reorder players (e.g., to skip eliminated players), the index-based sync will silently corrupt chip stacks.

**Fix:** Sync by player id, which is already available on every `Player`:

```python
chip_map = {p.id: p.chips for p in final_state.players}
for p in self.players:
    if p.id in chip_map:
        p.chips = chip_map[p.id]
```

---

### WR-05: `mock_decision` reconstructs betting state from `game_state` but `player.bet` is always 0 mid-round

**File:** `backend/app/engine/game.py:463-471`

**Issue:** `mock_decision` detects whether to check or call by comparing `player.bet` with `max(p.bet for p in game_state.players)`. But `run_betting_round` updates `game_state.players = players` (line 233) after each action, so `player.bet` values in `game_state` are live mid-round. The logic appears correct for the mock case.

The real risk is subtler: `player` passed into `decision_fn` is `players[current_seat]` — a direct reference to the mutable list element — while `game_state.players` is set to that same list. So `player` in `mock_decision` and `game_state.players[current_seat]` are the same object. This works correctly today but means the decision function receives a mutable reference to engine-internal state. A buggy or adversarial decision function could mutate `player` directly (e.g., `player.chips = 99999`) and corrupt the engine's state, since it is the same object — not a copy.

**Fix:** Pass a copy of the player to the decision function:

```python
import copy
action = await decision_fn(copy.copy(players[current_seat]), game_state)
```

A shallow copy suffices since `hole_cards` is a list of `Card` (Pydantic models, treated as immutable values here). For full safety, use `players[current_seat].model_copy()`.

---

## Info

### IN-01: `_next_active_seat` and `_first_active_from` are near-identical and could be unified

**File:** `backend/app/engine/game.py:95-116`

**Issue:** Both functions iterate clockwise with `(start + offset) % n` and filter by `not p.is_folded`. The only difference is that `_next_active_from` starts at `current + 1` (exclusive) while `_first_active_from` starts at `start` (inclusive). This duplication means any future change to the fold-check condition (e.g., also skipping all-in players) must be applied in two places.

**Fix:** Unify with an `inclusive: bool` parameter, or make `_next_active_seat` call `_first_active_from(current + 1, ...)`.

---

### IN-02: `BettingRoundState.has_acted` field type annotation is `set` (bare), not `set[int]`

**File:** `backend/app/engine/models.py:100`

**Issue:** The dataclass field is declared `has_acted: set = field(default_factory=set)`. The bare `set` type hint provides no information about the element type. Since seat indices (integers) are stored, the correct annotation is `set[int]`.

**Fix:**
```python
has_acted: set[int] = field(default_factory=set)
```

---

### IN-03: `GameState.reasoning` field is typed as bare `list` with no element type

**File:** `backend/app/engine/models.py:82`

**Issue:** `reasoning: list = Field(default_factory=list)` uses a bare `list` type. The comment says "ReasoningEntry list — Phase 4 fills." Either define a stub `ReasoningEntry` type now or use `list[Any]` with an explicit import to communicate intent and allow future narrowing without a breaking change.

**Fix:**
```python
from typing import Any
reasoning: list[Any] = Field(default_factory=list)
```

Or define a typed stub:
```python
ReasoningEntry = dict[str, Any]
reasoning: list[ReasoningEntry] = Field(default_factory=list)
```

---

### IN-04: `test_session.py` SC6 comment acknowledges incomplete phase validation but leaves it unchecked

**File:** `backend/tests/test_session.py:192-195`

**Issue:** The SC6 test (`test_all_hands_reach_terminal_phase`) contains a comment that explicitly documents that `_award_to_last_standing` does NOT reset `phase` to a terminal value, so early-termination hands can end with `phase='pre-flop'`, `phase='flop'`, etc. The test then skips validating the phase at all (`assert len(hands) == 10`). This means the engine silently returns non-terminal phase values for folded-out hands, and this inconsistency is untested. Frontend consumers expecting `phase='showdown'` for all terminal states will receive stale phase strings.

**Fix:** Either (a) set `game_state.phase = 'complete'` in `_award_to_last_standing` and update the test to assert it, or (b) document the contract explicitly in `_award_to_last_standing`'s docstring and add a test that asserts the phase is NOT 'showdown' on early termination. Option (a) is cleaner for frontend consumers.

---

_Reviewed: 2026-05-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
