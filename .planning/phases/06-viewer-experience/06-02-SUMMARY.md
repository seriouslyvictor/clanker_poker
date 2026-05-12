---
phase: 06-viewer-experience
plan: "02"
subsystem: ui
tags: [react, typescript, sse, idle-screen, demand-gate, balatro]

# Dependency graph
requires:
  - phase: 06-01
    provides: game_status SSE event on connect and session transitions, POST /api/game/start endpoint
  - phase: 05-frontend-wiring
    provides: useGameStream hook, PokerApp.tsx routing shell, types.ts interfaces

provides:
  - GameStatus interface exported from types.ts
  - useGameStream returns gameRunning (boolean | null) and lastWinner state
  - IdleScreen.tsx — full Balatro-styled idle screen with branding, last-result callout, START A GAME button
  - PokerApp routing: null → CONNECTING..., false → IdleScreen, true → Game

affects: [06-03-prediction-widget, future-phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - gameRunning boolean | null routing in PokerApp — null is the connecting state before first game_status event
    - IdleScreen onStart callback pattern — component resets isStarting on error; PokerApp unmounts on gameRunning flip
    - try/catch around JSON.parse for all SSE event types in useGameStream (mitigates T-06-07)
    - Felt texture overlay reused from Game.tsx — repeating-linear-gradient on absolute inset div

key-files:
  created:
    - frontend/src/components/IdleScreen.tsx
  modified:
    - frontend/src/components/types.ts
    - frontend/src/hooks/useGameStream.ts
    - frontend/src/components/PokerApp.tsx

key-decisions:
  - "IdleScreen receives onStart as () => Promise<void> prop — PokerApp owns the fetch logic and error propagation; IdleScreen only owns isStarting UI state"
  - "gameRunning === null is the initial state before any game_status event arrives — used for CONNECTING... screen, not a false/idle state"
  - "isStarting stays true after successful POST — PokerApp unmounts IdleScreen when gameRunning flips to true via SSE; no explicit reset needed on success path"

patterns-established:
  - "Routing on tri-state boolean: null → loading, false → idle, true → active — clean guards with early returns before main JSX"
  - "SSE event listener with try/catch error containment — malformed events logged but do not crash the hook"

requirements-completed: [VIEWER-01, VIEWER-02]

# Metrics
duration: 8min
completed: 2026-05-12
---

# Phase 6 Plan 02: IdleScreen + PokerApp Routing Summary

**Frontend idle-game cycle: useGameStream extended with game_status SSE parsing, IdleScreen.tsx with Balatro branding/last-result callout/START button, PokerApp routes on gameRunning tri-state**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-12T13:45:00Z
- **Completed:** 2026-05-12T13:53:16Z
- **Tasks:** 2
- **Files modified:** 4 (3 modified, 1 created)

## Accomplishments

- `GameStatus` interface added to types.ts; `useGameStream` now parses `game_status` SSE events and exposes `gameRunning` (boolean | null) and `lastWinner`
- `IdleScreen.tsx` created: full Balatro aesthetic with felt texture, Press Start 2P title, last-result callout (gold border, two-line winner copy), orange START A GAME button with STARTING... disabled state, cold-start hint
- `PokerApp.tsx` routes cleanly on tri-state: null → CONNECTING..., false → IdleScreen, true → Game; `handleStart` async function POSTs to `/api/game/start`
- TypeScript compiles clean with zero errors after all changes

## Task Commits

Each task was committed atomically:

1. **Task 1: GameStatus type + useGameStream gameRunning/lastWinner extension** - `d0994e2` (feat)
2. **Task 2: IdleScreen.tsx + PokerApp routing on gameRunning state** - `ebda845` (feat)

## Files Created/Modified

- `frontend/src/components/types.ts` - Added `GameStatus` interface (`running: boolean`, `lastWinner?` optional field)
- `frontend/src/hooks/useGameStream.ts` - Import GameStatus; extend `GameStream` interface; add `gameRunning`/`lastWinner` state; add `game_status` addEventListener with try/catch; extend return
- `frontend/src/components/IdleScreen.tsx` - New file: full idle screen with Balatro UI spec (branding, texture overlay, last-result callout, START A GAME button, cold-start hint)
- `frontend/src/components/PokerApp.tsx` - Import IdleScreen; destructure gameRunning/lastWinner; add handleStart with fetch to /api/game/start; add null/false routing guards before main return

## Decisions Made

- `onStart` is `() => Promise<void>` on IdleScreen — PokerApp owns the fetch and error propagation; IdleScreen only manages `isStarting` UI state. Error from fetch propagates back to IdleScreen to reset the button.
- `gameRunning === null` initial state correctly models the "connecting, no game_status received yet" scenario — distinct from `false` (idle) and `true` (running).
- `isStarting` stays `true` after a successful POST — there is no success-reset path in IdleScreen because PokerApp will unmount IdleScreen when `gameRunning` flips to `true` via the SSE `game_status` event.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. All changes are purely frontend TypeScript.

## Next Phase Readiness

- Frontend idle → game → idle cycle is fully wired via SSE
- `gameRunning` and `lastWinner` are available in PokerApp scope for any future use
- `IdleScreen` is mounted/unmounted cleanly by PokerApp routing — no side effects
- Plan 06-03 (PredictionWidget) can proceed: `gameState` and `players` remain available in the `gameRunning === true` branch of PokerApp

## Known Stubs

None — all data flows are live SSE-driven. `lastWinner` comes from backend Redis via `game_status` SSE event (wired in Plan 06-01). No placeholder text in render paths.

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model. `game_status` JSON.parse is wrapped in try/catch (T-06-07 mitigation applied). `handleStart` fetch to `/api/game/start` follows existing CORS + VITE_API_URL env var pattern (T-06-10 accepted).

## Self-Check

- `frontend/src/components/types.ts` — modified in d0994e2
- `frontend/src/hooks/useGameStream.ts` — modified in d0994e2
- `frontend/src/components/IdleScreen.tsx` — created in ebda845
- `frontend/src/components/PokerApp.tsx` — modified in ebda845

---
*Phase: 06-viewer-experience*
*Completed: 2026-05-12*
