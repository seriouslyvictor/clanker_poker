---
phase: 02-game-state-machine
plan: "04"
subsystem: backend/engine
tags: [game-session, texas-holdem, dealer-rotation, chip-conservation, tdd, async]
dependency_graph:
  requires:
    - backend/app/engine/game.py (run_hand, mock_decision — Plan 02-03)
    - backend/app/engine/models.py (Player, GameState, DecisionFn — Plan 02-02)
  provides:
    - backend/app/engine/session.py (GameSession — multi-hand session with dealer rotation)
  affects:
    - backend/app/engine/game_loop.py (Phase 3 imports GameSession to drive SSE broadcast)
tech_stack:
  added: []
  patterns:
    - "GameSession.players is single source of truth for chip state between hands"
    - "run_hand() deep copies players internally — session reads back chips from final_state.players"
    - "Dealer button rotates through ALL n_players seats regardless of elimination"
    - "active_players < 2 guard terminates session early if chips consolidate"
    - "decision_fn defaults to mock_decision; Phase 4 drops in LLM function with zero refactor"
key_files:
  created:
    - backend/app/engine/session.py
    - backend/tests/test_session.py
  modified: []
key_decisions:
  - "Session owns chip carry-over by reading final_state.players[i].chips after each run_hand() call"
  - "Dealer rotation always increments through all n_players seats — elimination does not skip seat indices"
  - "Two-player minimum check terminates session cleanly instead of passing insufficient players to run_hand"
requirements-completed:
  - POKER-01
  - POKER-05

# Metrics
duration: 2m 5s
completed: 2026-05-03
---

# Phase 02 Plan 04: Multi-Hand GameSession with Dealer Rotation — Summary

**GameSession wrapper driving 10-hand Texas Hold'em sessions with clockwise dealer rotation, chip stack carry-over, and mock decision seam for Phase 4 LLM replacement.**

## Performance

- **Duration:** 2m 5s
- **Started:** 2026-05-03T23:51:12Z
- **Completed:** 2026-05-03T23:53:17Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files created:** 2

## Accomplishments

- `GameSession(n_players=4, starting_chips=1000, big_blind=20)` initialises a 4-player roster with correct ids, names, org, color, deck fields
- `run(n_hands=10)` completes 10 hands without exception — ROADMAP SC4 satisfied
- Chip conservation holds at 4000 total after 10 hands — ROADMAP SC5 satisfied
- Dealer button rotates correctly: `dealer_seat == 10 % 4 == 2` after 10 hands
- 28 TDD tests added across 9 test classes; 128 total tests pass (1 skipped)

## Task Commits

Each task committed atomically (TDD pattern):

1. **RED — Failing tests for GameSession** - `c606850` (test)
   - 28 tests across 9 classes; all fail with `ModuleNotFoundError: No module named 'app.engine.session'`

2. **GREEN — Implement backend/app/engine/session.py** - `bb62045` (feat)
   - 28/28 session tests pass; 128/128 total tests pass; inline verification prints "session.py OK"

## Files Created/Modified

- `backend/app/engine/session.py` — 109 lines; `GameSession` class with `run()` coroutine, `_make_players()` helper, chip carry-over logic, dealer rotation
- `backend/tests/test_session.py` — 253 lines; 28 tests covering init, run(), chip conservation, dealer rotation, hand phases, return count, decision_fn parameter, chip carry-over

## Decisions Made

- **Chip carry-over pattern:** session.py passes `self.players` to `run_hand()` which deep copies internally. After each hand, session reads back `final_state.players[i].chips` and updates `self.players[i].chips`. This makes `session.players` the single source of truth without aliasing bugs (threat T-02-10 mitigated).
- **Dealer rotation through all seats:** `self.dealer_seat = (self.dealer_seat + 1) % self.n_players` always advances regardless of player chip counts. Matches CONTEXT.md D-04 and RESEARCH.md open question resolution.
- **Minimum players guard:** `len(active_players) < 2` before each hand cleanly terminates the session when chips consolidate — prevents passing insufficient players to `run_hand()` (threat T-02-11 mitigated).

## Deviations from Plan

None — plan executed exactly as written.

The implementation precisely matches the plan's `<action>` code block. No deviations, auto-fixes, or scope additions were required.

## TDD Gate Compliance

- RED commit `c606850`: `test(02-04)` — 28 tests collected, 1 collection error (`ModuleNotFoundError: No module named 'app.engine.session'`)
- GREEN commit `bb62045`: `feat(02-04)` — 28/28 session tests pass; 128/128 total suite passes; inline verification prints "session.py OK"
- REFACTOR: not needed — implementation clean on first pass

## Verification Results

```
session.py OK                           <- inline verification from plan
28 passed in 0.27s                      <- test_session.py
128 passed, 1 skipped in 4.32s          <- full engine test suite
```

**Acceptance criteria checklist:**
- [x] `backend/app/engine/session.py` exists (109 lines)
- [x] Contains `class GameSession:`
- [x] Contains `async def run(`
- [x] Contains `from app.engine.game import run_hand, mock_decision`
- [x] Contains `self.dealer_seat = (self.dealer_seat + 1) % self.n_players`
- [x] Inline verification exits 0 and prints "session.py OK"
- [x] `len(hands) == 10` after `run(n_hands=10)`
- [x] `sum(p.chips for p in session.players) == 4000` (chip conservation)
- [x] `all(p.chips >= 0 for p in session.players)`
- [x] `session.dealer_seat == 10 % 4 == 2` after 10 hands
- [x] Each hand `state.phase in ('showdown', 'hand_complete')` — verified

## Known Stubs

None — `GameSession` is a complete, functional implementation:
- `mock_decision` passed through to `run_hand()` as documented — Phase 4 replaces via `decision_fn` parameter
- No placeholder text, no hardcoded empty values, no UI-facing stubs
- The `decision_fn` default is intentionally `mock_decision` per Phase 2 plan; Phase 4 passes the LLM function

## Threat Flags

No new security surface beyond the plan's threat model.

- **T-02-10 (mitigated):** Chip carry-over correctness — `self.players[i].chips = returned_player.chips` after each hand; no aliasing (run_hand deep copies). Chip conservation test passes across 10 hands.
- **T-02-11 (mitigated):** DoS prevention — `len(active_players) < 2` guard breaks loop cleanly. Session terminates without hanging.

## Self-Check: PASSED

- [x] `backend/app/engine/session.py` EXISTS (109 lines)
- [x] `backend/tests/test_session.py` EXISTS (28 tests)
- [x] RED commit `c606850` EXISTS
- [x] GREEN commit `bb62045` EXISTS
- [x] Inline verification: PASSED (prints "session.py OK")
- [x] 28/28 tests pass in `test_session.py`
- [x] 128/128 tests pass in full engine suite
- [x] `dealer_seat == 2` after 10 hands — confirmed
- [x] Chip conservation 4000 — confirmed
