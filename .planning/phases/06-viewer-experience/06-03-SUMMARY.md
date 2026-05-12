---
phase: 06-viewer-experience
plan: "03"
subsystem: ui
tags: [react, typescript, localStorage, prediction-widget, balatro, vite]

# Dependency graph
requires:
  - phase: 06-02
    provides: IdleScreen, PokerApp routing on gameRunning tri-state, GameStatus type
  - phase: 05-frontend-wiring
    provides: useGameStream hook, Game.tsx, StakeChip, GoldCrownChip, ConfettiBurst components

provides:
  - PredictionWidget.tsx — floating overlay with States A (pick), B (predicted), C (result reveal)
  - StakeChip onClick prop — optional click handler with cursor:pointer when provided
  - Game.tsx PREDICTION_PHASES module-level Set — phase gate for widget render
  - localStorage poker_prediction persistence with per-hand reset on winner→null transition

affects: [future-phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - localStorage prediction record pattern — { handId, prediction (playerId), result ('correct'|'wrong'|null) }
    - prevWinnerRef transition detection — useRef tracks previous winner value for null-transition reset
    - PREDICTION_PHASES Set at module level in Game.tsx — phase gate for conditional component mount
    - State machine in single component — State A/B/C with guards (phase=WINNER + result not null → C, prediction set → B, else → A)

key-files:
  created:
    - frontend/src/components/PredictionWidget.tsx
  modified:
    - frontend/src/components/StakeChip.tsx
    - frontend/src/components/Game.tsx
    - frontend/tsconfig.node.json

key-decisions:
  - "PREDICTION_PHASES defined in both PredictionWidget (for internal use) and Game.tsx (for conditional mount) — they are independent; Game.tsx does not import PredictionWidget's internal const"
  - "State C render guard uses prediction?.result !== null && prediction?.result !== undefined — handles the case where result is explicitly null (no result yet) vs undefined (no prediction)"
  - "player.name.split(' ')[0] in State A chip labels — truncates to first word (e.g. 'GPT-5 Nano' → 'GPT-5') to prevent overflow in 4-chip row; full name used in State B and C sub-label"
  - "skipLibCheck: true added to tsconfig.node.json — fixes pre-existing tsc -b failure on babel-plugin-react-compiler missing @types/babel__core; unblocks npm run build"

patterns-established:
  - "Floating overlay widget: position:absolute, bottom:16, right:16, zIndex:30 relative to position:relative table area — reusable pattern for future HUD elements"
  - "Per-hand reset via winner→null transition: prevWinnerRef.current !== null && gameState.winner === null — detects hand boundary without requiring explicit hand ID from backend"

requirements-completed: [VIEWER-03]

# Metrics
duration: 20min
completed: 2026-05-12
---

# Phase 6 Plan 03: PredictionWidget Summary

**Anonymous prediction widget with 3-state localStorage-persisted UX — click a player chip to predict the hand winner, see CORRECT!/WRONG at showdown, auto-resets on new hand**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-12T14:10:00Z
- **Completed:** 2026-05-12T14:30:00Z
- **Tasks:** 2
- **Files modified:** 4 (3 modified, 1 created)

## Accomplishments

- `StakeChip.tsx` extended with optional `onClick` prop: cursor:pointer when handler provided, userSelect:none to prevent text selection
- `PredictionWidget.tsx` created: State A (4 player chips, "WHO WINS THIS HAND?"), State B ("PREDICTED:" + chosen chip), State C (GoldCrownChip "CORRECT!" with ConfettiBurst or red StakeChip "WRONG", plus "You picked {name}" sub-label); slideIn animation on mount
- localStorage persistence (`poker_prediction` key) with per-hand reset via winner→null transition detection using `useRef`
- `Game.tsx` wired: `PREDICTION_PHASES` module-level Set, conditional `<PredictionWidget>` render inside `position:relative` table area at `bottom:16, right:16, zIndex:30`
- TypeScript compiles clean (`npx tsc --noEmit` exits 0); full production build passes (`npm run build` exits 0, 238ms)

## Task Commits

Each task was committed atomically:

1. **Task 1: StakeChip onClick extension + PredictionWidget.tsx** - `da847e3` (feat)
2. **Task 2: Wire PredictionWidget into Game.tsx + fix build** - `4731632` (feat)

## Files Created/Modified

- `frontend/src/components/PredictionWidget.tsx` — New: floating prediction overlay, 3-state machine, localStorage persistence, per-hand reset, slideIn animation
- `frontend/src/components/StakeChip.tsx` — Added `onClick?: () => void` prop, cursor:pointer conditional, userSelect:none
- `frontend/src/components/Game.tsx` — Import PredictionWidget, add `PREDICTION_PHASES` Set at module level, conditional render in table area
- `frontend/tsconfig.node.json` — Added `skipLibCheck: true` (Rule 3 auto-fix — unblocks npm run build)

## Decisions Made

- `PREDICTION_PHASES` is defined in both PredictionWidget (for internal state logic) and Game.tsx (for conditional mount gate). They are independent — Game.tsx does not import PredictionWidget's internal const.
- State C render guard checks `prediction?.result !== null && prediction?.result !== undefined` to distinguish "no prediction yet" (null result field) from "result available" (correct/wrong).
- Player name in State A uses `player.name.split(' ')[0]` (first word) to prevent chip overflow in 4-chip row. Full name used in State B and C sub-label.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added skipLibCheck to tsconfig.node.json**
- **Found during:** Task 2 (npm run build verification)
- **Issue:** `tsc -b` (run by `npm run build`) was failing with 4 errors from `babel-plugin-react-compiler`'s declaration file missing `@types/babel__core` and `@types/babel__traverse`. This was a pre-existing issue in the repo (identical failure in main repo's frontend). The `tsc -b` flag includes tsconfig.node.json references which lacked `skipLibCheck: true`.
- **Fix:** Added `"skipLibCheck": true` to `frontend/tsconfig.node.json`
- **Files modified:** `frontend/tsconfig.node.json`
- **Verification:** `npm run build` exits 0, built in 238ms
- **Committed in:** `4731632` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 3 blocking)
**Impact on plan:** Pre-existing build infrastructure issue, not related to prediction widget code. Fix is minimal and correct — skipLibCheck is already present in the main tsconfig.json.

## Issues Encountered

- Worktree was missing Wave 1 and Wave 2 commits (06-01, 06-02) — fast-forward merged `465b610` at execution start to bring in all prior Phase 6 work before implementing plan 03.
- Worktree `frontend/` had no `node_modules/` — ran `npm install` to enable local TypeScript and build verification.

## User Setup Required

None - no external service configuration required. All changes are purely frontend TypeScript/React.

## Next Phase Readiness

- Phase 6 viewer experience is fully implemented: demand gate (06-01), idle screen + PokerApp routing (06-02), prediction widget (06-03)
- `PredictionWidget` is mounted/unmounted cleanly by `PREDICTION_PHASES` phase gate — no side effects during DEALING/SHOWDOWN phases
- State C (WINNER phase result reveal) runs independently from the main winner overlay (zIndex 30 vs 50) — both are visible simultaneously
- localStorage `poker_prediction` key is self-contained; safe to extend in future phases

## Known Stubs

None — PredictionWidget is fully wired. State machine responds to live SSE gameState (phase, winner, players). localStorage persistence is real. No placeholder text in render paths.

## Threat Flags

No new threat surface beyond plan's threat model. T-06-13 mitigation applied: `winnerPlayer?.id` uses optional chaining for safe out-of-bounds winner index handling.

## Self-Check

- `frontend/src/components/PredictionWidget.tsx` — created in da847e3 ✓
- `frontend/src/components/StakeChip.tsx` — modified in da847e3 ✓
- `frontend/src/components/Game.tsx` — modified in 4731632 ✓
- `frontend/tsconfig.node.json` — modified in 4731632 ✓

---
*Phase: 06-viewer-experience*
*Completed: 2026-05-12*
