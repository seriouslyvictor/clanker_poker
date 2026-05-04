---
phase: 02-game-state-machine
plan: 05
subsystem: testing
tags: [pytest, asyncio, poker-engine, game-state, chip-conservation, betting-order]

# Dependency graph
requires:
  - phase: 02-game-state-machine
    provides: game.py (run_hand, mock_decision, valid_actions, is_round_closed), session.py (GameSession), cards.py, models.py
provides:
  - backend/tests/test_game_engine.py with 35 tests covering all 5 ROADMAP Phase 2 success criteria
  - test_bb_gets_option_preflop — critical regression guard for has_acted seeding bug
  - TestSession class proving 10-hand sessions complete without error
  - TestChipConservation class proving sum(stacks)+pot == starting_total across full session
affects:
  - 03-sse-broadcast (confidence that game engine is correct before wiring SSE)
  - 04-llm-integration (confirms mock_decision seam works; LLM drop-in needs same behavior)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio.run() wrappers in sync test methods — avoids @pytest.mark.asyncio requirement with asyncio_mode=strict"
    - "Closure-based logging_decision for action-order verification without modifying production code"
    - "Module-level make_players() helper — not pytest fixture, reusable in all test classes"

key-files:
  created: []
  modified:
    - backend/tests/test_game_engine.py

key-decisions:
  - "Rewrote test file to match plan's 6 required class names (TestCards, TestSingleHand, TestBettingOrder, TestShowdown, TestSession, TestChipConservation) while retaining all prior test logic"
  - "Fixed test_postflop_sb_acts_first: logging_decision must call (not check) when facing pre-flop BB bet, otherwise is_round_closed never fires — caused infinite loop in prior Wave 2 test design"
  - "is_round_closed and valid_actions unit tests moved into TestBettingOrder per SC2 grouping"

patterns-established:
  - "Phase 2 test pattern: asyncio.run() wraps every async engine call in sync test method"
  - "Action-order tests use closure that captures list/set, then asserts on log content post-run"

requirements-completed:
  - POKER-01
  - POKER-02
  - POKER-05

# Metrics
duration: 15min
completed: 2026-05-04
---

# Phase 2 Plan 05: Game Engine Test Suite Summary

**35-test suite covering all 5 ROADMAP Phase 2 success criteria: card conversion, hand structure, betting order (including BB option regression guard), showdown correctness, 10-hand session completion, and chip conservation across full session**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-05-04T00:20:00Z
- **Completed:** 2026-05-04T00:38:29Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- 35 tests pass across 6 classes covering SC1-SC5; full suite 136 passed, 1 skipped — zero regressions
- `test_bb_gets_option_preflop` confirms the has_acted seeding bug (RESEARCH.md Pitfall 1) is not present
- `TestSession::test_ten_hand_session_completes` and `TestChipConservation::test_conservation_across_full_session` are the definitive SC4/SC5 integration proofs
- `TestCards` validates the treys int <-> {s,r} round-trip required by the frontend type contract

## Task Commits

1. **Task 1: Create test_game_engine.py — all 5 success criteria** - `a516e92` (test)

## Files Created/Modified

- `backend/tests/test_game_engine.py` — 35 tests across 6 classes covering all Phase 2 ROADMAP success criteria

## Decisions Made

- Rewrote file to match plan's required 6 class names while retaining all proven prior test logic from Wave 2
- Fixed infinite-loop bug in test_postflop_sb_acts_first: the logging closure must call (not check) when facing an outstanding bet; checking pre-flop against a BB bet keeps betting round open forever

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed infinite loop in test_postflop_sb_acts_first logging_decision**
- **Found during:** Task 1 (test execution — test hung at TestBettingOrder::test_postflop_sb_acts_first)
- **Issue:** The logging_decision closure returned `Action(action_type="check")` unconditionally. Pre-flop the BB posts 20 chips; other players' bets are 0, so current_bet=20 and player.bet=0 means they owe chips. is_round_closed() requires player.bet == current_bet for a closed round. Players checking (no chip movement) meant the condition was never satisfied — infinite loop.
- **Fix:** Added bet comparison in the logging closure: if player.bet < max_bet, return call; otherwise check. This matches the same heuristic used by mock_decision.
- **Files modified:** backend/tests/test_game_engine.py
- **Verification:** Test passes in 0.34s (was hanging indefinitely)
- **Committed in:** a516e92 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test logic causing infinite loop)
**Impact on plan:** Required fix was within the test file itself. No production code changes. No scope creep.

## Issues Encountered

- RTK hook redirected `uv run pytest` to system Python 3.14 (no treys) instead of the venv. Resolved by calling `.venv/Scripts/python.exe -m pytest` directly.

## Known Stubs

None — test file contains no stubs, placeholders, or TODO markers.

## Next Phase Readiness

- Phase 2 is fully verified: all 5 ROADMAP success criteria have passing test coverage
- Phase 3 (SSE Broadcast) can wire game.py/session.py with confidence the engine is correct
- The DecisionFn seam is confirmed async-compatible; Phase 4 LLM drop-in requires no refactoring

---

## Self-Check: PASSED

- `backend/tests/test_game_engine.py` exists: FOUND
- Task commit a516e92 exists: FOUND (git log confirms)
- 35 tests collected and passed: CONFIRMED
- test_bb_gets_option_preflop exists and passes: CONFIRMED
- Full suite 136 passed, 1 skipped: CONFIRMED

---
*Phase: 02-game-state-machine*
*Completed: 2026-05-04*
