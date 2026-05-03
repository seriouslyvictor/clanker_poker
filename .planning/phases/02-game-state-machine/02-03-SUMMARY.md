---
phase: 02-game-state-machine
plan: "03"
subsystem: backend/engine
tags: [game-engine, texas-holdem, betting, tdd, chip-conservation, async]
dependency_graph:
  requires:
    - backend/app/engine/cards.py (new_card, card_display — Plan 02-01)
    - backend/app/engine/models.py (Player, GameState, BettingRoundState, DecisionFn — Plan 02-02)
    - backend/app/engine/poker_math.py (evaluate_hand — Phase 1)
  provides:
    - backend/app/engine/game.py (run_hand, mock_decision, valid_actions, is_round_closed)
  affects:
    - backend/app/engine/session.py (Wave 3, plan 02-04 — imports run_hand, mock_decision)
tech_stack:
  added: []
  patterns:
    - "BettingRoundState.has_acted set-tracking prevents BB infinite-loop bug (Pitfall 1)"
    - "Deck() created fresh inside run_hand() per hand — never shared (Pitfall 2)"
    - "evaluate_hand() called only at showdown with 5 community cards (Pitfall 3)"
    - "player.bet reset to 0 after each betting round via _collect_bets_to_pot (Pitfall 5)"
    - "Deep copy of players list in run_hand() — caller's list never mutated"
    - "TDD: RED (ModuleNotFoundError) → GREEN (27/27 pass)"
key_files:
  created:
    - backend/app/engine/game.py
    - backend/tests/test_game_engine.py
  modified: []
decisions:
  - "BB not added to has_acted during blind posting — only added when decision_fn is called for that seat (Pitfall 1 guard)"
  - "mock_decision reconstructs check-vs-call intent from player.bet vs max bet — BettingRoundState not stored in GameState"
  - "Early termination without showdown when all-but-one fold — _award_to_last_standing() with no hand evaluation"
  - "All-in handled as min(call_amount, player.chips) — no side pots per D-05"
  - "Tie-breaking: lowest seat index wins — deterministic, acceptable for mock sessions per D-05"
metrics:
  duration: "3m 48s"
  completed: "2026-05-03"
  tasks_total: 1
  tasks_completed: 1
  files_created: 2
  files_modified: 0
  tests_added: 27
  tests_passing: 27
---

# Phase 02 Plan 03: Single-Hand Texas Hold'em Engine — Summary

**One-liner:** Async single-hand Texas Hold'em engine (game.py) with TDD — correct pre-flop UTG action order, BB option via has_acted tracking, chip conservation, and mock decision seam for Phase 4 LLM replacement.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED  | Failing tests for game.py | 03bfecd | backend/tests/test_game_engine.py |
| GREEN | Implement backend/app/engine/game.py | a12896c | backend/app/engine/game.py |

## What Was Built

`backend/app/engine/game.py` — 243 lines, 4 public exports + 3 private helpers:

**Public API:**
- `run_hand(players, dealer_seat, big_blind, decision_fn) -> GameState` — Full hand lifecycle: deep copy, reset, blind posting, deal 2 hole cards per player, pre-flop/flop/turn/river betting rounds, showdown. Returns final GameState. Creates a fresh `Deck()` every call.
- `run_betting_round(game_state, players, dealer_seat, is_preflop, big_blind, decision_fn) -> tuple` — Async betting loop. Initializes `BettingRoundState` with empty `has_acted`. Advances seats, awaits `decision_fn`, processes fold/call/raise/check, collects bets to pot at round end, resets `player.bet = 0` for next round.
- `valid_actions(player, state) -> list[ActionType]` — Returns `['fold','check','raise']` when `call_amount==0` and chips>0, `['fold','call','raise']` when `call_amount>0` and `chips>call_amount`, `['fold','call']` when all-in only.
- `is_round_closed(state, players) -> bool` — Two-condition check: (1) all active players in `has_acted`, AND (2) all active non-all-in players have `bet == current_bet`. Returns `True` immediately when only 1 active player remains.
- `mock_decision(player, game_state) -> Action` — Checks if `player.bet >= max(all bets)`, else calls. Phase 4 drop-in replacement for LLM decision functions.

**Private helpers:**
- `_next_active_seat()` — Clockwise scan for next non-folded seat
- `_first_active_from()` — First non-folded seat starting from given index (inclusive)
- `_collect_bets_to_pot()` — Sums all player bets into pot, resets bets to 0
- `_active_count()` — Count of non-folded players
- `_award_to_last_standing()` — Award pot to last player when all others fold; no showdown evaluation

**Test coverage (27 tests):**
- `TestValidActions` (7 tests) — all combinations: check/call/raise/fold per chips and bet state
- `TestIsRoundClosed` (5 tests) — open when not all acted; open when bets unequal; closed when both conditions met; closed on single active; closed for all-in player with lower bet
- `TestRunHand` (10 tests) — showdown phase, winner, show_cards, 5 community cards, 2 hole cards per player, chip conservation (4000 total), no negative chips, caller list not mutated, winner marked, winner_hand set
- `TestBBOption` (2 tests) — BB gets to act pre-flop; UTG = seat 3 is first actor with dealer=0
- `TestMockDecision` (2 tests) — check when no outstanding bet; call when current_bet > player.bet
- `TestEarlyTermination` (1 test) — pot awarded without showdown; chip conservation holds

## Verification Results

```
game.py OK                          <- inline verification from plan
27 passed in 0.40s                  <- test_game_engine.py
79 passed in 0.39s                  <- full engine test suite (cards + models + game)
```

**Acceptance criteria checklist:**
- [x] `backend/app/engine/game.py` exists
- [x] Contains `async def run_hand(`
- [x] Contains `async def mock_decision(`
- [x] Contains `def valid_actions(`
- [x] Contains `def is_round_closed(`
- [x] Contains `from app.engine.cards import`
- [x] Contains `from app.engine.models import`
- [x] Contains `from app.engine.poker_math import evaluate_hand`
- [x] Contains `from treys import Deck`
- [x] Does NOT contain `TreysCard.new(` — uses `new_card()` from cards.py
- [x] `Deck()` appears only inside `run_hand()` function (not at module level)
- [x] Inline verification exits 0 and prints "game.py OK"
- [x] `state.phase == 'showdown'` after run_hand with mock decisions
- [x] `state.winner is not None` after showdown
- [x] `state.show_cards == True` at showdown
- [x] `len(state.community_cards) == 5` at showdown
- [x] `sum(p.chips for p in state.players) + state.pot == 4000` (chip conservation)
- [x] `all(p.chips >= 0 for p in state.players)`

## Deviations from Plan

None — plan executed exactly as written.

The implementation precisely followed the plan's action section:
- `valid_actions()` logic matches Plan section exactly (fold always, check/call based on call_amount, raise based on chips > call_amount)
- `is_round_closed()` implements the two-condition check from RESEARCH.md Pattern 3
- `run_betting_round()` initialises `BettingRoundState.has_acted` as empty set — neither SB nor BB seeded during blind posting
- `run_hand()` creates `Deck()` inside the function, never at module level
- `mock_decision()` uses the exact heuristic from the plan's code snippet

## TDD Gate Compliance

- RED commit `03bfecd`: `test(02-03)` — 27 tests collected, 1 collection error (`ModuleNotFoundError: No module named 'app.engine.game'`)
- GREEN commit `a12896c`: `feat(02-03)` — 27/27 tests pass, inline verification prints "game.py OK"
- REFACTOR: not needed — implementation is clean on first pass

## Known Stubs

None — game.py is a complete, functional implementation:
- `run_hand()` runs a real Texas Hold'em hand with real card evaluation
- `mock_decision()` is intentionally simple (Phase 2 placeholder) — documented as "Phase 4 replaces this"
- No placeholder text, no hardcoded empty values flowing to UI
- The mock_decision stub is by design; Phase 4 LLM plan replaces it via the DecisionFn seam

## Threat Flags

No new security surface beyond plan's threat model.

**T-02-06 (mitigate):** Action validation — `valid_actions()` implemented correctly. Phase 2 mock always returns valid actions; Phase 4 LLM fallback validation is deferred to that plan as specified.

**T-02-07 (mitigate):** Infinite loop prevention — `is_round_closed()` two-condition check implemented; BB `has_acted` bug explicitly avoided per RESEARCH.md Pitfall 1. 27 test runs confirm no hangs.

**T-02-08 (mitigate):** Chip conservation — `_award_to_last_standing()` and showdown path both reset `game_state.pot = 0` and add exactly `pot` to winner's chips. Chip conservation test passes (sum == 4000).

**T-02-09 (mitigate):** Stale deck — `Deck()` created inside `run_hand()` on line 316. Module-level `Deck()` usage confirmed absent via grep.

## Self-Check: PASSED

- [x] `backend/app/engine/game.py` EXISTS (243 lines)
- [x] `backend/tests/test_game_engine.py` EXISTS (27 tests)
- [x] RED commit `03bfecd` EXISTS
- [x] GREEN commit `a12896c` EXISTS
- [x] Inline verification: PASSED (prints "game.py OK")
- [x] 27/27 tests pass in `test_game_engine.py`
- [x] 79/79 tests pass in full engine suite (cards + models + game)
- [x] `Deck()` appears only inside `run_hand()` — confirmed via grep
- [x] `TreysCard.new` has 0 matches in game.py — confirmed via grep
