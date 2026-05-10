---
phase: "05-frontend-wiring"
plan: "03"
subsystem: "frontend"
tags: ["sse", "react-hook", "eventsource", "live-state", "mock-removal"]
dependency_graph:
  requires: ["05-01", "05-02"]
  provides: ["frontend/src/hooks/useGameStream", "frontend/live-game-rendering"]
  affects: ["06-viewer-experience"]
tech_stack:
  added:
    - "EventSource (native browser API) — SSE connection to /api/stream"
  patterns:
    - "useGameStream custom React hook with single-lifetime EventSource"
    - "Named SSE event listeners (addEventListener, not onmessage)"
    - "applyDelta helper: immutable accumulation of reasoning entries by (playerId, phase)"
    - "reasoning_snapshot replay: rebuild reasoning from scratch on reconnect"
    - "new URL('/api/stream', base) normalization against trailing-slash VITE_API_URL"
    - "es.onopen handler for accurate connectionState after reconnect"
    - "prevWinnerRef: detect new-hand transition (winner non-null -> null)"
key_files:
  created:
    - "frontend/src/hooks/useGameStream.ts"
  modified:
    - "frontend/src/components/Game.tsx"
    - "frontend/src/components/PokerApp.tsx"
    - "frontend/package-lock.json"
decisions:
  - "currentBet already present in types.ts (added by 05-01 deviation) — skipped re-add"
  - "npm install run in worktree frontend/ to generate node_modules for tsc — package-lock.json committed"
  - "reasoning_snapshot rebuilds from scratch (not merge with stale state) — snapshot is authoritative"
  - "es.close() only in useEffect cleanup (not in onerror) — preserves native auto-reconnect"
metrics:
  duration: "245 seconds (~4 minutes)"
  completed: "2026-05-10"
  tasks_completed: 2
  files_created: 1
  files_modified: 3
---

# Phase 05 Plan 03: SSE Wiring — useGameStream Hook + Live Game State Summary

**One-liner:** useGameStream EventSource hook with named event listeners, applyDelta accumulation, reasoning_snapshot replay on reconnect, and MOCK_STATE fully removed from Game.tsx.

## What Was Built

The frontend now connects to the FastAPI SSE endpoint and renders live game state. MOCK_STATE is gone. The `useGameStream` hook manages a single EventSource lifetime per component mount, accumulates streaming reasoning deltas by (playerId, phase), recovers reasoning state after network interruption via the `reasoning_snapshot` event, and accurately tracks connection state via `es.onopen`.

### Task 1: useGameStream hook

- `frontend/src/hooks/useGameStream.ts`: SSE hook returning `{ gameState, reasoning, connectionState }`
- `SSE_URL` built with `new URL('/api/stream', _base)` — safe against trailing slash in `VITE_API_URL`
- `es.onopen` sets `connectionState` to `'open'` on initial connect AND after every auto-reconnect
- `addEventListener('game_state', ...)` — named event listener (not `onmessage`)
- `addEventListener('reasoning', ...)` — accumulates deltas via `applyDelta`
- `addEventListener('reasoning_snapshot', ...)` — replays full delta list on reconnect
- `applyDelta` helper: finds existing entry by `(playerId, phase)`, concatenates delta text; creates new entry if not found
- `reasoning_snapshot` handler: rebuilds from empty array using all snapshot deltas (no stale merge)
- Winner null transition: clears reasoning when `winner` goes from non-null to null (new hand)
- `JSON.parse` wrapped in `try/catch` for all three event handlers — malformed data logs, does not crash
- `es.onerror`: sets `connectionState` to `'connecting'`; does NOT call `es.close()` — preserves auto-reconnect

### Task 2: Game.tsx + PokerApp.tsx wiring

- `Game.tsx`: `MOCK_STATE` const removed entirely
- `Game.tsx`: `GameProps` expanded with `gameState: GameState | null` and `reasoning: ReasoningEntry[]`
- `Game.tsx`: loading guard `if (!gameState)` renders "Connecting to game..." full-screen
- `Game.tsx`: destructures from `gameState` prop instead of `MOCK_STATE`
- `Game.tsx`: `reasoning` prop flows to `ReasoningPanel` and `PlayerSeat`
- `PokerApp.tsx`: imports `useGameStream` from `../hooks/useGameStream`
- `PokerApp.tsx`: calls `useGameStream()` and passes `gameState` + `reasoning` to `<Game>`

## Deviations from Plan

### Skipped steps

**1. currentBet already in types.ts — step skipped**
- **Plan action:** Add `currentBet?: number` to `GameState` interface
- **Reality:** 05-01 added this as a deviation (05-01-SUMMARY.md deviation #5). Field was present before plan execution.
- **Action:** Confirmed present, skipped re-add.

### Auto-fixed issues

**1. [Rule 3 - Blocking] frontend node_modules missing in worktree**
- **Found during:** Task 1 verification (`npx tsc --noEmit` reported `ignoreDeprecations` error from wrong TypeScript version)
- **Issue:** `npx tsc` resolved to global TypeScript (different version), not the locally installed one. `frontend/node_modules/` did not exist in worktree.
- **Fix:** Ran `npm install` inside `frontend/` to install local dependencies. Package-lock.json updated and committed.
- **Files modified:** `frontend/package-lock.json`
- **Commit:** b183f8c

## Three Review Fixes Applied

All three fixes from the plan objective were implemented:

| Fix | Implementation | Location |
|-----|---------------|----------|
| URL normalization | `new URL('/api/stream', _base).toString()` | `useGameStream.ts` line 22 |
| `es.onopen` handler | `es.onopen = () => setConnectionState('open')` | `useGameStream.ts` line 66 |
| `reasoning_snapshot` handler | `addEventListener('reasoning_snapshot', ...)` replays all deltas | `useGameStream.ts` line 103 |

## Verification Results

| Check | Result |
|-------|--------|
| `MOCK_STATE` absent from Game.tsx | PASS — grep returns 0 matches |
| No `use client` in frontend/src/ | PASS — grep returns 0 matches |
| `currentBet` in types.ts | PASS |
| `useGameStream` imported and called in PokerApp.tsx | PASS — 2 matches |
| URL normalization (`new URL`) | PASS |
| `es.onopen` handler present | PASS |
| `reasoning_snapshot` listener present | PASS |
| `es.close()` NOT in `onerror` | PASS |
| `try/catch` wraps all JSON.parse calls | PASS — 3 occurrences |
| `npx tsc --noEmit` | PASS — 0 errors |

## Known Stubs

None. `MOCK_STATE` has been fully removed. The component renders "Connecting to game..." when `gameState` is null — this is the correct loading state, not a stub.

## Threat Flags

No new threat surface beyond the plan's threat model. All T-05-03-* mitigations applied as designed (try/catch on all JSON.parse, no dangerouslySetInnerHTML, URL built from env var with localhost fallback, reasoning_snapshot rebuilds from scratch).

## Self-Check

### Files verified

- `frontend/src/hooks/useGameStream.ts` — exists, exports `useGameStream`
- `frontend/src/components/Game.tsx` — exists, no MOCK_STATE, contains `if (!gameState)`
- `frontend/src/components/PokerApp.tsx` — exists, contains `useGameStream` import and call

### Commits verified

- b183f8c — `feat(05-03): implement useGameStream SSE hook`
- c735265 — `feat(05-03): wire useGameStream into PokerApp, remove MOCK_STATE from Game`

## Self-Check: PASSED
