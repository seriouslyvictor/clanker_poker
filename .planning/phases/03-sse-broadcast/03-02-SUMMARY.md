---
phase: 03-sse-broadcast
plan: 02
subsystem: engine
tags: [broadcast, callback, async, phase-transitions]

# Dependency graph
requires:
  - phase: 02-game-state-machine
    provides: run_hand() async function and GameState models
provides:
  - BroadcastFn type alias for SSE broadcast callbacks
  - broadcast_fn parameter on run_hand() with calls at 5 phase transitions
  - broadcast_fn parameter passed through GameSession.run()
  - Seam for Phase 3 game loop to publish game state to Redis
affects:
  - 03-03 (game_loop.py uses this broadcast_fn callback)
  - 03-04 (SSE endpoint consumes broadcasted states)
  - Phase 4 (LLM integration can hook reasoning into same broadcast)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Optional async callback pattern for side effects (broadcast_fn)
    - _maybe_broadcast helper for no-op when callback is None
    - Phase transition points identified and instrumented

key-files:
  created: []
  modified:
    - backend/app/engine/game.py
    - backend/app/engine/session.py

key-decisions:
  - Implemented broadcast_fn as optional parameter, not event emitter, to maintain simplicity and Phase 2 test compatibility
  - Early termination paths (_award_to_last_standing) also trigger broadcast for consistency
  - Phase transitions broadcast BEFORE betting round, ensuring listeners see state changes before round progresses

requirements-completed:
  - STREAM-01

# Metrics
duration: 2min
completed: 2026-05-06
---

# Phase 3: SSE Broadcast — Plan 02 Summary

**BroadcastFn callback parameter added to run_hand() with calls at 5 phase transitions (pre-flop, flop, turn, river, showdown); callback wired through GameSession.run() for Phase 3 game loop integration**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-06T14:59:58Z
- **Completed:** 2026-05-06T15:01:59Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `BroadcastFn` type alias (`Callable[[GameState], Awaitable[None]]`) to game.py
- Added optional `broadcast_fn` parameter to `run_hand()` signature with default `None`
- Implemented `_maybe_broadcast()` helper function for zero-overhead callback invocation
- Inserted broadcast calls at 5 phase transition points:
  1. After pre-flop state is built (pre-deal)
  2. After flop cards dealt and phase set (pre-betting)
  3. After turn card dealt and phase set (pre-betting)
  4. After river card dealt and phase set (pre-betting)
  5. After showdown resolution (post-winner-determination)
- Early termination paths also broadcast final state before returning
- Wired broadcast_fn parameter through GameSession.run() to run_hand() call
- All Phase 2 tests pass without modification (136 passed, 1 skipped)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add BroadcastFn type and broadcast_fn parameter to run_hand()** - `d09686b` (feat)
2. **Task 2: Wire broadcast_fn through GameSession.run() in session.py** - `118ac6e` (feat)

## Files Created/Modified

- `backend/app/engine/game.py` - Added BroadcastFn type, _maybe_broadcast() helper, broadcast_fn parameter, 9 broadcast call sites
- `backend/app/engine/session.py` - Imported BroadcastFn, added broadcast_fn parameter, passed to run_hand()

## Decisions Made

- **Callback-based design:** Chose optional async callback over event emitter for simplicity and testability. Allows Phase 2 tests to run unmodified with `broadcast_fn=None`.
- **Phase transition timing:** Broadcast calls occur AFTER state is updated but BEFORE betting round begins, ensuring consistent ordering of published states.
- **Early termination handling:** Modified early-return paths to call _maybe_broadcast before returning, ensuring all hand outcomes are published.
- **Helper function:** _maybe_broadcast checks for None before calling, making the broadcast call sites clean and allowing Phase 3 to pass lambda or full functions without test impact.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation proceeded smoothly with all acceptance criteria met on first try.

## Next Phase Readiness

**Ready for Phase 3 — Plan 03:** The broadcast_fn callback seam is now open and tested. Phase 3 can now:
- Create game_loop.py background task
- Create publisher.py to call `publish(redis_client, state)` as the broadcast_fn
- Create broker.py and stream.py to distribute published states to SSE clients

The game loop will pass `lambda state: publish(redis_client, state)` as broadcast_fn, ensuring each phase transition publishes the state to Redis pub/sub.

---

*Phase: 03-sse-broadcast*
*Plan: 02*
*Completed: 2026-05-06*
