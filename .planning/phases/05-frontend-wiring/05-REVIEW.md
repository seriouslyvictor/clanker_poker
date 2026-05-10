---
phase: 05-frontend-wiring
reviewed: 2026-05-10T00:00:00Z
depth: standard
files_reviewed: 25
files_reviewed_list:
  - frontend/vite.config.ts
  - frontend/tsconfig.json
  - frontend/tsconfig.node.json
  - frontend/index.html
  - frontend/src/main.tsx
  - frontend/src/index.css
  - frontend/src/App.tsx
  - frontend/src/vite-env.d.ts
  - frontend/src/lib/constants.ts
  - frontend/src/components/types.ts
  - frontend/src/components/Game.tsx
  - frontend/src/components/PokerApp.tsx
  - frontend/src/components/ReasoningPanel.tsx
  - frontend/src/components/PlayerSeat.tsx
  - frontend/src/components/Card.tsx
  - frontend/src/components/TweaksPanel.tsx
  - frontend/src/components/ActionStamp.tsx
  - frontend/src/components/StakeChip.tsx
  - frontend/src/components/GoldCrownChip.tsx
  - frontend/src/components/ConfettiBurst.tsx
  - frontend/src/components/HistoryPopover.tsx
  - frontend/src/hooks/useGameStream.ts
  - backend/app/config.py
  - backend/.env.example
  - backend/app/api/stream.py
  - backend/app/broadcast/publisher.py
findings:
  critical: 0
  warning: 5
  info: 5
  total: 10
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-05-10
**Depth:** standard
**Files Reviewed:** 25
**Status:** issues_found

## Summary

The Phase 5 frontend wiring is well-structured overall. The SSE hook, type system, and component hierarchy are clean and show careful design. The backend publish/stream pipeline correctly handles late-joiner ordering (subscribe before snapshot read) and has sensible error handling throughout.

Five warnings require attention before this phase ships: the most important is an array bounds crash in `Game.tsx` that will throw if the server ever sends fewer than four players, and a reasoning snapshot race condition in `publisher.py` that drops reasoning for late joiners mid-hand. The remaining issues are logic bugs or API confusions that will cause real but subtler problems.

---

## Warnings

### WR-01: Unchecked player array indexing crashes on malformed server state

**File:** `frontend/src/components/Game.tsx:71,74,100,103`

**Issue:** Players are accessed by hardcoded index (`players[0]` through `players[3]`) with no guard on `players.length`. If the backend ever sends a `GameState` with fewer than four players (e.g. after a bust-out, mid-initialization, or a serialization bug), React will receive `undefined` as the `player` prop and `PlayerSeat` will throw a runtime error, crashing the entire UI tree.

**Fix:**
```tsx
// Add a guard before the grid render:
if (players.length < 4) {
  return (
    <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', background: theme.tableBg, color: 'rgba(255,255,255,0.4)' }}>
      Waiting for players...
    </div>
  );
}
```
Alternatively, use optional chaining in the `PlayerSeat` props and update `PlayerSeat` to accept `player?: Player`.

---

### WR-02: Out-of-bounds winner index crashes the winner overlay

**File:** `frontend/src/components/Game.tsx:126-129`

**Issue:** The winner overlay renders `players[winner]` after confirming `winner !== null`, but `winner` is an unchecked integer from the server. A backend bug or malformed payload sending `winner: 99` passes the null check and then throws `TypeError: Cannot read properties of undefined` at `players[winner].color`, `players[winner].name`, and `players[winner].org`.

**Fix:**
```tsx
// Replace the outer conditional:
{phase === 'WINNER' && winner !== null && winner >= 0 && winner < players.length && (
  // ... winner overlay
)}
```

---

### WR-03: Reasoning snapshot cleared on every phase transition, dropping reasoning for late joiners mid-hand

**File:** `backend/app/broadcast/publisher.py:36-37`

**Issue:** `publish()` calls `await redis_client.delete(REASONING_SNAPSHOT_KEY)` at the start of every phase transition (pre-flop → flop → turn → river → showdown). A client who connects during the FLOP reasoning phase receives a `reasoning_snapshot` with zero entries — the snapshot was wiped when the FLOP `game_state` was published — even though multiple players have already streamed reasoning deltas for the current hand. The design comment says "new phase, fresh accumulation", but phases transition multiple times per hand, so this effectively guarantees late joiners miss reasoning.

The fix depends on intended semantics. Two options:

**Option A — Clear only at hand start** (keep all reasoning for the hand visible):
```python
async def publish(redis_client: redis.Redis, state: GameState) -> None:
    payload = state.model_dump_json(by_alias=True)
    # Only clear reasoning when a new hand begins (phase resets to pre-flop/dealing)
    if state.phase.upper() in ("DEALING", "PRE-FLOP"):
        await redis_client.delete(REASONING_SNAPSHOT_KEY)
    await redis_client.set(SNAPSHOT_KEY, payload, ex=SNAPSHOT_TTL)
    await redis_client.publish(CHANNEL, payload)
```

**Option B — Keep current behavior, document it** if per-phase isolation is intentional.

---

### WR-04: TweaksPanel `onClose` callback inversion is a fragile API

**File:** `frontend/src/components/PokerApp.tsx:46` and `frontend/src/components/TweaksPanel.tsx:88`

**Issue:** `TweaksPanel` calls `onClose(true)` to signal "I am closing myself". `PokerApp` wires `onClose={hidden => setTweaksVisible(!hidden)}`, which inverts the boolean back to `false` (panel hidden). The logic is accidentally correct, but the API naming is semantically backwards: the prop is named `onClose` and receives `hidden: boolean`, but callers have to know that `true` means hidden and they need to invert it. If someone refactors TweaksPanel to call `onClose(false)` thinking "false = not closing", the panel gets stuck visible.

**Fix:** Simplify the API — `onClose` should take no arguments and mean "the panel wants to close":
```tsx
// TweaksPanel.tsx
interface TweaksPanelProps {
  // ...
  onClose: () => void;  // remove the boolean parameter
}
// In the close button:
<button onClick={onClose} ...>✕</button>

// PokerApp.tsx
<TweaksPanel
  onClose={() => setTweaksVisible(false)}
  // ...
/>
```

---

### WR-05: `models.config.json` import path requires non-obvious Vite `fs.allow` configuration

**File:** `frontend/src/lib/constants.ts:1` and `frontend/vite.config.ts:13`

**Issue:** `constants.ts` imports `'../../../models.config.json'` — three levels above the file, which resolves to the repo root from `frontend/src/lib/`. The `vite.config.ts` allows filesystem access with `fs.allow: ['..']`, which is relative to the Vite root (the `frontend/` directory). This means Vite allows access to `clanker_poker/` (one level up), which does cover `models.config.json` at `clanker_poker/models.config.json`. So it works — but it is fragile: if the frontend directory is ever renamed or moved, the `allow` path silently breaks module resolution in a way that only manifests at dev-server startup or build time.

A more robust approach documents this coupling explicitly:
```ts
// vite.config.ts — document why '../' is needed:
server: {
  fs: {
    // Required: constants.ts imports models.config.json from repo root (3 levels up from src/lib/).
    // '../' = clanker_poker/ relative to frontend/ (the Vite root).
    allow: ['..'],
  },
},
```
The existing comment already partially does this but does not show the resolved path. Consider also copying or symlinking `models.config.json` into the frontend tree at build time to eliminate the cross-package import.

---

## Info

### IN-01: `actionColor` helper function is duplicated

**File:** `frontend/src/components/ReasoningPanel.tsx:12-13` and `frontend/src/components/HistoryPopover.tsx:12-13`

**Issue:** The `actionColor` function is defined identically in both files. Any change to action color logic must be updated in two places.

**Fix:** Extract to `@/lib/constants.ts` or a new `@/lib/colors.ts` and import from there.

---

### IN-02: Non-null assertion on `getElementById('root')` gives no diagnostic on failure

**File:** `frontend/src/main.tsx:9`

**Issue:** `document.getElementById('root')!` will throw a cryptic `Cannot read properties of null` if the `#root` div is ever absent — which can happen if `index.html` is accidentally modified. The `!` suppresses the TypeScript safety check with no runtime fallback.

**Fix:**
```tsx
const rootEl = document.getElementById('root');
if (!rootEl) throw new Error('[main.tsx] #root element not found — check index.html');
createRoot(rootEl).render(<App />);
```

---

### IN-03: `Card.tsx` uses non-null assertion with an implicit invariant

**File:** `frontend/src/components/Card.tsx:37,52,53,58,63`

**Issue:** After the `if (!card && !faceDown)` early return on line 11, and the `if (faceDown)` branch on line 21, the code reaches line 37 with the invariant that `card` is defined. However, `card!.s` and `card!.r` non-null assertions are used five times rather than a single narrowing. This is safe today but will silently break if the branching logic above is ever reordered.

**Fix:** Add a runtime guard before the assertions to make the invariant explicit:
```tsx
// After the faceDown branch:
if (!card) return null; // unreachable with current callers, but explicit
const isRed = card.s === '♥' || card.s === '♦';
```

---

### IN-04: Disconnect detection has up to 1-second latency

**File:** `backend/app/api/stream.py:79`

**Issue:** The event loop polls `request.is_disconnected()` only after `asyncio.wait_for(queue.get(), timeout=1.0)` times out. A disconnected client therefore occupies the broker subscription queue for up to one second. This is functionally fine but means memory is not released promptly during high-churn connection periods.

**Fix (optional):** Use `asyncio.wait` with two awaitables — `queue.get()` and `request.is_disconnected()` — to react to disconnects immediately. Only worth addressing if broker queue memory becomes a concern at scale.

---

### IN-05: Stale `localhost:3000` CORS origin in default config

**File:** `backend/app/config.py:22` and `backend/.env.example:22`

**Issue:** The default `cors_origins` includes `http://localhost:3000` (the old Next.js dev port). The project has migrated to Vite on port 5173. The stale entry is harmless at runtime but creates confusion about which frontend is authoritative.

**Fix:** Remove `http://localhost:3000` from the default `cors_origins` list once the Next.js frontend is fully decommissioned. Keep it in `.env.example` with a comment explaining it is a legacy entry.

---

_Reviewed: 2026-05-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
