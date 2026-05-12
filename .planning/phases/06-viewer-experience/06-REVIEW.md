---
phase: 06-viewer-experience
reviewed: 2026-05-12T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - backend/app/api/game.py
  - backend/app/broadcast/broker.py
  - backend/app/broadcast/publisher.py
  - backend/app/game_loop.py
  - backend/app/main.py
  - backend/app/api/stream.py
  - frontend/src/components/IdleScreen.tsx
  - frontend/src/components/types.ts
  - frontend/src/hooks/useGameStream.ts
  - frontend/src/components/PokerApp.tsx
  - frontend/src/components/PredictionWidget.tsx
  - frontend/src/components/StakeChip.tsx
  - frontend/src/components/Game.tsx
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-05-12
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Reviewed the full Phase 6 viewer-experience stack: demand-gate backend (game.py, game_loop.py, main.py), the SSE pipeline (broker.py, publisher.py, stream.py), and the new frontend components (IdleScreen, PokerApp routing, PredictionWidget, StakeChip, Game). The architecture is sound and the late-joiner snapshot pattern is correctly ordered. One critical unchecked array access in Game.tsx can crash the winner overlay. Several warnings cover: a non-throwing fetch in PokerApp that silently swallows HTTP errors, prediction logic that mis-fires on backend phase string casing, a game-loop exception handler that leaves `game_running=True` until the `except` block resets it, and a `start_event` that is not cleared before `game_running` is reset on error, which could let a second game start on a zombie loop. Three info-level items cover dead code, duplicated logic, and a magic string.

---

## Critical Issues

### CR-01: Unchecked array access on `players[winner]` crashes winner overlay

**File:** `frontend/src/components/Game.tsx:149`
**Issue:** `winner` comes from `gameState.winner` which is typed as `number | null`. The outer check `winner !== null` guards for null, but does not guard against `winner` being an out-of-range index into the `players` array. If the backend ever sends a `winner` index equal to or greater than `players.length` (e.g., a stale state snapshot arrives with 3 players but `winner: 3`), `players[winner]` is `undefined`, and the subsequent `.color`, `.name`, and `.org` property accesses throw a runtime TypeError that crashes the React render tree.

The identical unguarded access also exists at line 164 (`players[winner].org`) and line 69 in `PredictionWidget.tsx` (`gameState.players[gameState.winner]`) — the latter already has a `?.` optional chain guard and is safe.

**Fix:**
```tsx
// Game.tsx — guard the whole winner overlay block
{phase === 'WINNER' && winner !== null && players[winner] != null && (
  // ... existing overlay JSX unchanged
)}
```
Or add a local variable before the return:
```tsx
const winnerPlayer = winner !== null ? players[winner] ?? null : null;

// Then use winnerPlayer throughout the overlay, guarded:
{phase === 'WINNER' && winnerPlayer !== null && (
  <div ...>
    <div style={{ color: winnerPlayer.color }}>{winnerPlayer.name}</div>
    <div>{winnerPlayer.org}</div>
    ...
  </div>
)}
```

---

## Warnings

### WR-01: `handleStart` in PokerApp does not check HTTP error status — 409/503 silently swallowed

**File:** `frontend/src/components/PokerApp.tsx:21-29`
**Issue:** `fetch` only rejects on network failure; it resolves with a non-2xx `Response` without throwing. If the backend returns 409 (game already running) or 503 (no viewers), the `await fetch(...)` call succeeds without error. The `catch` block is never reached, so `isStarting` is never reset to `false` in `IdleScreen`. The button stays permanently disabled ("STARTING...") until the user reloads.

**Fix:**
```tsx
const handleStart = async (): Promise<void> => {
  const _base = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
  const url = new URL('/api/game/start', _base).toString();
  const res = await fetch(url, { method: 'POST' });
  if (!res.ok) {
    throw new Error(`Start failed: ${res.status}`);
  }
  // On success: game_status { running: true } arrives via SSE
};
```
The `try/catch` already lives in `IdleScreen.handleStart`, so throwing here correctly resets the button.

---

### WR-02: PredictionWidget phase check uses `'WINNER'` but `publisher.py` emits `'pre-flop'`/`'flop'` lowercase — phase string casing mismatch risk

**File:** `frontend/src/components/PredictionWidget.tsx:55`
**Issue:** The result-reveal effect checks `gameState.phase === 'WINNER'`. `Game.tsx` defines `PHASE_DISPLAY` with an uppercase `'WINNER'` key, implying the backend sends `'WINNER'` as the phase string. However, `publisher.py` serializes from `GameState.phase` directly, and the game engine's phase strings may differ in casing. If the backend ever sends `'winner'` (lowercase — as suggested by the `PHASE_DISPLAY` fallback `?? phase`), the result-reveal never fires. The same check in `Game.tsx:131` is subject to the same mismatch.

There is no bug today if the backend consistently sends `'WINNER'`, but the lack of a shared constant makes this fragile.

**Fix:** Define a shared constant or enum for phase strings (e.g., in `types.ts`) and use it in both the effect and `PHASE_DISPLAY`:
```ts
// types.ts
export const PHASES = {
  WINNER: 'WINNER',
  PRE_FLOP: 'PRE-FLOP',
  // ...
} as const;
```
Then use `PHASES.WINNER` in both `Game.tsx` and `PredictionWidget.tsx`.

---

### WR-03: `game_running` flag set to `False` AFTER the exception branch, leaving a window where it is `True` with no game

**File:** `backend/app/game_loop.py:121-124`
**Issue:** When `session.run()` throws an unhandled exception, the `except Exception` handler resets `app_state.game_running = False` at line 123. Between the exception being raised (during `session.run()` at line 91) and line 123 executing, `game_running` is `True` but no session is running. Any call to `POST /api/game/start` during this window gets a 409 "Game already running" error even though the game loop crashed.

This is a brief window (asyncio is single-threaded, so the handler runs immediately), but it is visible: the SSE `game_status` broadcast at line 115 is never reached, so clients continue to see `running: True` indefinitely until the next trigger. A viewer refreshing will receive the stale snapshot with `running: True` and be stuck on the game screen with no game progressing.

**Fix:** Reset the flag and broadcast the status update inside the `except` block:
```python
except Exception as exc:
    logger.error("Game loop error (will retry on next trigger): %s", exc, exc_info=True)
    app_state.game_running = False
    await publish_game_status(broker, redis_client, running=False)  # ADD THIS
    await asyncio.sleep(1)
```

---

### WR-04: `start_event` not cleared on exception path — second trigger can start a game immediately after a crash

**File:** `backend/app/game_loop.py:117-124`
**Issue:** The `start_event.clear()` call is at line 63, immediately after `await start_event.wait()`. If `session.run()` crashes after the event has been cleared (normal path), there is no double-fire. However, if `start_event.set()` is called by `POST /api/game/start` while the loop is sleeping in the 1-second `asyncio.sleep(1)` after an exception, the event stays set and the loop re-enters the game immediately on the next `while True` iteration without waiting. This is actually the intended restart behavior — but after the fix in WR-03 adds `publish_game_status(running=False)`, the sequence `running=False` broadcast → `sleep(1)` → immediate game start (because event is already set) → `running=True` broadcast could confuse clients. Consider clearing the event explicitly in the `except` block to force a viewer to re-trigger:

```python
except Exception as exc:
    logger.error("Game loop error (will retry on next trigger): %s", exc, exc_info=True)
    app_state.game_running = False
    start_event.clear()  # require explicit re-trigger after a crash
    await publish_game_status(broker, redis_client, running=False)
    await asyncio.sleep(1)
```

---

### WR-05: `useGameStream` `reasoning` state not cleared when `gameRunning` flips to `False`

**File:** `frontend/src/hooks/useGameStream.ts:70-77`
**Issue:** Reasoning entries are cleared when `game_state` arrives with `winner` transitioning from non-null to null (new hand start). However, if a viewer connects during the idle screen and the previous session's reasoning is still in `reasoning` state (from a `reasoning_snapshot`), that stale reasoning will be rendered immediately when `gameRunning` flips to `true` and `Game.tsx` is mounted — before the first `game_state` event of the new session arrives. The `game_state` event arrival will clear it, but there is a brief flash of stale reasoning from the previous session in the `ReasoningPanel`.

**Fix:** Clear reasoning when `game_status { running: true }` arrives:
```ts
es.addEventListener('game_status', (e: MessageEvent) => {
  try {
    const status: GameStatus = JSON.parse(e.data as string)
    setGameRunning(status.running)
    if (status.running) {
      setReasoning([])  // clear stale reasoning when a new game starts
    }
    if (!status.running && status.lastWinner !== undefined) {
      setLastWinner(status.lastWinner ?? null)
    }
  } catch (err) { ... }
})
```

---

## Info

### IN-01: Duplicate `lastWinner` resolution logic between `stream.py` and `publisher.py`

**File:** `backend/app/api/stream.py:77-92` and `backend/app/broadcast/publisher.py:101-113`
**Issue:** Both `sse_stream` (snapshot path for late joiners) and `publish_game_status` (live broadcast path) contain identical code to read `GAME_LAST_RESULT_KEY` from Redis and build the `last_winner` dict. If the key schema changes (e.g., `winnerName` → `winner_name`), it must be updated in two places.

**Fix:** Extract to a helper in `publisher.py`:
```python
async def _get_last_winner(redis_client: redis.Redis) -> dict | None:
    raw = await redis_client.get(GAME_LAST_RESULT_KEY)
    if not raw:
        return None
    data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    return {"name": data["winnerName"], "org": data["winnerOrg"], "hand": data["winnerHand"]}
```
Then call it from both sites.

---

### IN-02: `PredictionWidget` `handId` state is never used in `PredictionRecord`

**File:** `frontend/src/components/PredictionWidget.tsx:35`
**Issue:** `const [handId] = useState(() => Date.now().toString())` is initialized but `handId` is only written into `PredictionRecord.handId` (line 74) and never read back for any comparison or display. The `loadPrediction()` / `savePrediction()` functions do not validate whether the stored `handId` matches the current hand, so a prediction persisted from a previous page load for a different hand is silently treated as valid for the current hand. Either the `handId` matching logic should be implemented, or the field should be removed.

**Fix (minimal):** If cross-session prediction recovery is not intended, compare on load:
```ts
const [prediction, setPrediction] = useState<PredictionRecord | null>(() => {
  const stored = loadPrediction()
  // Discard if stored for a different session — handId won't match
  // (requires a stable handId source; currently Date.now() is not stable across remounts)
  return stored
})
```
A more complete fix would derive `handId` from `gameState` (e.g., hand sequence number) so it can be compared against the stored value.

---

### IN-03: Magic string `'pre-flop'` phase check in `publisher.py` for reasoning snapshot reset

**File:** `backend/app/broadcast/publisher.py:44`
**Issue:** `if state.phase == "pre-flop":` uses a bare string literal. The game engine's phase string for pre-flop is referenced in at least three places (`publisher.py`, `Game.tsx` `PHASE_DISPLAY`, `PredictionWidget.tsx`). A phase name change or casing inconsistency will silently break the reasoning snapshot reset.

**Fix:** Define a constant in the engine models or a shared config:
```python
# app/engine/models.py (or a constants module)
PHASE_PRE_FLOP = "pre-flop"
```
Then import and use it in `publisher.py` and any other backend consumers.

---

_Reviewed: 2026-05-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
