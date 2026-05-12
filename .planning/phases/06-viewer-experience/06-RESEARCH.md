# Phase 6: Viewer Experience - Research

**Researched:** 2026-05-12
**Domain:** FastAPI asyncio demand-gating, SSE event extension, React state routing, localStorage prediction, Redis last-result persistence
**Confidence:** HIGH — all findings verified against actual codebase files

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Idle State Signal**
- D-01: Backend sends `event: game_status` as a new SSE event type. Payload: `{ running: boolean, lastWinner: { name, org, hand } | null }`. When `running: false`, `lastWinner` contains the most recent session winner (or null if no game has ever run). When `running: true`, `lastWinner` is omitted.
- D-02: `game_status` fires in two situations: (a) on every SSE connect/reconnect — included in the snapshot sequence so late joiners know state immediately, and (b) on session transitions — when a session starts (`running: true`) and when a session ends (`running: false` with updated `lastWinner`).
- D-03: `useGameStream` hook gains a `gameRunning: boolean | null` state (null = unknown/still connecting). `PokerApp.tsx` routes on this: `gameRunning === null` → loading, `gameRunning === false` → idle screen, `gameRunning === true` → `<Game>` component.
- D-04: A second viewer who arrives while a game is in progress receives `game_status { running: true }` → lands directly in the live game view. No idle screen.
- D-05: New REST endpoint: `POST /api/game/start`. Backend checks: (a) no game currently running, (b) `broker.viewer_count >= 1`. If both conditions met, sets an `asyncio.Event` that the game loop is waiting on. Returns 400 if game already running or no viewers connected. (Note: CONTEXT.md specifics section refines: 409 if running, 503 if no viewers, 200 on success.)
- D-06: `game_loop.py` becomes demand-gated: after each session completes, it waits on the asyncio.Event. The Event is created in lifespan and stored on `app.state.start_event`. Game loop pattern: wait → clear event → run session → broadcast `game_status { running: false }` → wait again.
- D-07: `EventBroker` gains a `viewer_count` property returning the current number of active subscriber queues.
- D-08: `POST /api/game/start` broadcasts `event: game_status { running: true }` immediately when the game is triggered.

**Prediction Widget**
- D-09: Prediction widget is a floating overlay above the community card area. Appears on PRE-FLOP, FLOP, TURN, RIVER; disappears on SHOWDOWN, WINNER, DEALING.
- D-10: Per-hand predictions; resets when winner transitions from non-null to null (new hand started).
- D-11: localStorage key `poker_prediction` stores `{ handId: string, prediction: playerId, result: 'correct' | 'wrong' | null }`.
- D-12: Widget shows 4 player chips using existing `StakeChip` component. After pick, collapses to "Prediction: [player name]". At WINNER phase shows "Correct!" or "Wrong".

**Last Game Result**
- D-13: Backend stores last result in Redis under key `game:last_result` after each session ends. Payload: `{ winnerName, winnerOrg, winnerHand }`.
- D-14: `lastWinner` is piggybacked on the `game_status { running: false }` event. Backend reads from Redis.
- D-15: Idle screen displays `lastWinner` as: "{winnerOrg}'s {winnerName} won with {winnerHand}". Omit if null.

**Module Layout (D-16)**
```
backend/app/
├── api/
│   └── game.py              ← POST /api/game/start endpoint
├── broadcast/
│   └── publisher.py         ← extend with publish_game_status()
├── broadcast/
│   └── broker.py            ← add viewer_count property
└── game_loop.py             ← demand-gated loop (asyncio.Event wait)

frontend/src/
├── hooks/
│   └── useGameStream.ts     ← add gameRunning state, game_status listener
├── components/
│   ├── IdleScreen.tsx        ← new: idle UI with Start button + last result
│   ├── PredictionWidget.tsx  ← new: floating prediction overlay
│   └── PokerApp.tsx          ← routing logic (loading / idle / game)
```

**Exact API contracts (from CONTEXT.md specifics):**
- `POST /api/game/start`: 409 if game already running, 503 if no viewers, 200 on success
- `broker.viewer_count` = count of active asyncio.Queue entries (len of subscriber set)
- Prediction widget phases: PRE-FLOP, FLOP, TURN, RIVER (hidden on SHOWDOWN, WINNER, DEALING)
- localStorage key: `poker_prediction` with shape `{ handId: string, prediction: playerId, result: 'correct' | 'wrong' | null }`
- Idle screen callout: "{winnerOrg}'s {winnerName} won with {winnerHand}" (omit if lastWinner null)
- Redis key: `game:last_result` (JSON string `{ winnerName, winnerOrg, winnerHand }`)

### Claude's Discretion
- Idle screen visual design (branding layout, button styling — should match existing Balatro aesthetic)
- PredictionWidget animation (fade in/out timing)
- `handId` generation strategy (timestamp, UUID, or counter)
- `POST /api/game/start` response body (200 OK with `{ started: true }` or just 204)
- Exact asyncio.Event placement in app.state (attribute name, initialization)

### Deferred Ideas (OUT OF SCOPE)
- Live viewer count display (v2)
- Prediction streak tracking (v2)
- Pre-game lobby countdown (v2)
- Configurable hands per session (pending todo)
- Optional archetypes mode (pending todo)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VIEWER-01 | Idle screen displayed when no game is running — shows project branding, last game result (if any), and a "Start a Game" call-to-action button | D-01/D-02/D-03 demand-gate SSE signal; D-13/D-14/D-15 Redis last result; IdleScreen.tsx component design patterns below |
| VIEWER-02 | Any viewer can click "Start a Game" — game starts within 5s of click; button disabled once game in progress; no double-start | D-05/D-06/D-07/D-08 asyncio.Event demand gate; POST /api/game/start endpoint; broker.viewer_count check |
| VIEWER-03 | Anonymous winner prediction — before showdown viewer picks AI; result shown at showdown; stored in localStorage | D-09/D-10/D-11/D-12 PredictionWidget; localStorage pattern; phase-gating logic |
</phase_requirements>

---

## Summary

Phase 6 adds the complete viewer lifecycle — idle → game → winner → idle — by extending the existing SSE/FastAPI/React stack with three targeted changes: a new SSE event type (`game_status`), a demand-gated game loop via `asyncio.Event`, and two new frontend components (`IdleScreen.tsx`, `PredictionWidget.tsx`).

All foundations are in place. The EventBroker fan-out architecture (Phase 3), publisher/Redis pattern (Phase 3), useGameStream hook (Phase 5), and Balatro UI component system (Phase 5) are verified working. Phase 6 extends them rather than replacing them.

The highest-risk integration point is the `game_loop.py` refactor: the current loop is `while True: run_session(); sleep()`. Replacing `sleep()` with `asyncio.Event.wait()` must preserve the `CancelledError` re-raise contract that the existing lifespan shutdown depends on, and must add `app.state.game_running: bool` synchronization so both the demand-gate endpoint and the snapshot sequence see consistent state.

**Primary recommendation:** Plan in three vertical slices: (1) backend wiring (event gate + Redis last_result + game_status SSE), (2) frontend routing (IdleScreen.tsx + useGameStream extension + PokerApp routing), (3) prediction widget (PredictionWidget.tsx + localStorage + phase-gating).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Game running state | API / Backend | — | `app.state.game_running` is authoritative; frontend derives from SSE push |
| Demand gate (start button server check) | API / Backend | — | Viewer count + race prevention must be server-enforced (D-05) |
| SSE game_status event | API / Backend | — | Backend pushes; frontend listens. Same pattern as game_state event |
| Redis last_result persistence | Database / Storage | API (reads on connect) | Written by game_loop; read by snapshot sequence in stream.py |
| Idle/loading/game routing | Browser / Client | — | PokerApp.tsx routes on gameRunning state derived from SSE |
| Idle screen UI | Browser / Client | — | IdleScreen.tsx; pure render from props |
| Prediction widget logic | Browser / Client | — | PredictionWidget.tsx; reads gameState.phase; writes localStorage |
| localStorage persistence | Browser / Client | — | No backend persistence in v1 (locked decision) |
| "Start a Game" HTTP POST | Browser / Client | API (processes it) | Client initiates; backend validates and triggers |

---

## Standard Stack

### Core (no new packages needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | (existing) | New router `api/game.py` + asyncio.Event on app.state | Already in use; APIRouter pattern matches health.py and stream.py |
| redis.asyncio | (existing) | Write/read `game:last_result` key | Already used in publisher.py with same pattern as SNAPSHOT_KEY |
| asyncio | stdlib | `asyncio.Event` demand gate in game_loop.py | Built-in; no install needed |
| React 19.2.4 | (existing) | IdleScreen.tsx, PredictionWidget.tsx | Already in frontend/package.json |
| TypeScript 6.0.3 | (existing) | Type new GameStatus interface | Already in use |

**No new packages required.** All libraries needed are already installed. [VERIFIED: frontend/package.json, backend pyproject via existing imports]

### localStorage API (browser built-in)

`window.localStorage.getItem` / `setItem` / `removeItem` — no library needed. The prediction widget reads/writes the `poker_prediction` key directly. [VERIFIED: CONTEXT.md D-11, no existing localStorage usage in codebase to conflict with]

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (Viewer)
│
│  1. SSE connect (GET /api/stream)
│     ↓ snapshot sequence:
│       • game_state snapshot (if exists)
│       • reasoning_snapshot (if exists)
│       • game_status snapshot ← NEW (read app.state.game_running + Redis game:last_result)
│
│  2. Live events pushed:
│       • game_state events (existing, unchanged)
│       • reasoning events (existing, unchanged)
│       • game_status events ← NEW (on session start/end)
│
│  3. POST /api/game/start ← NEW REST call on button click
│     ↓
│     Backend checks: game_running? viewer_count >= 1?
│     → sets app.state.start_event (asyncio.Event)
│     → broadcasts game_status { running: true } immediately
│     → returns 200/409/503
│
useGameStream hook
│
├── gameRunning: null    → PokerApp shows loading overlay
├── gameRunning: false   → PokerApp shows <IdleScreen>
└── gameRunning: true    → PokerApp shows <Game>
    │
    └── PredictionWidget (floating overlay on Game area)
        │ reads: gameState.phase, gameState.players, gameState.winner
        │ writes: localStorage['poker_prediction']
        │ visible: PRE-FLOP, FLOP, TURN, RIVER
        │ hidden: DEALING, SHOWDOWN, WINNER

game_loop.py (demand-gated)
│
│  OLD: while True: run_session(); sleep(delay)
│  NEW: while True:
│         await start_event.wait()   ← blocks until viewer clicks Start
│         start_event.clear()
│         app.state.game_running = True
│         broadcast game_status(running=True)
│         run_session()
│         store game:last_result to Redis
│         app.state.game_running = False
│         broadcast game_status(running=False, lastWinner=...)
│         (loop back to wait)
```

### Recommended Project Structure (additions only)

```
backend/app/
├── api/
│   ├── game.py              ← NEW: POST /api/game/start
│   ├── health.py            (existing, unchanged)
│   └── stream.py            (existing, extend snapshot sequence)
├── broadcast/
│   ├── broker.py            (existing, add viewer_count property)
│   └── publisher.py         (existing, add publish_game_status())
├── game_loop.py             (existing, major refactor to demand-gate)
└── main.py                  (existing, add start_event + game_running to app.state, include game router)

frontend/src/
├── components/
│   ├── IdleScreen.tsx        ← NEW
│   ├── PredictionWidget.tsx  ← NEW
│   ├── PokerApp.tsx          (existing, add routing logic)
│   └── types.ts              (existing, add GameStatus type)
└── hooks/
    └── useGameStream.ts      (existing, add gameRunning state + game_status listener)
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| asyncio cross-task signaling | Custom flag polling in a sleep loop | `asyncio.Event` | Built-in, await-friendly, zero overhead; `event.wait()` suspends coroutine cleanly without CPU spin |
| Redis key existence check | Manual null-guard + parse logic | `await redis_client.get(key)` returns `None` if key absent — already used in publisher.py | Pattern established in SNAPSHOT_KEY handling |
| SSE event envelope | Custom serialization | Same JSON envelope pattern as existing `game_state` and `reasoning` events: `{"event": "game_status", "data": "..."}` | Broker already unpacks this envelope in stream.py |
| localStorage schema | IndexedDB or server persistence | `window.localStorage` with typed helper | Sufficient for single-key prediction state; no persistence requirement beyond current browser session |
| Player chip UI for prediction | Custom circular buttons | `StakeChip` component with `onClick` prop (needs adding) | StakeChip already renders correctly; add onClick + cursor:pointer |
| CORS for new endpoint | Middleware duplication | Existing `CORSMiddleware` in main.py covers all routes on the `app` instance including new router | Already handles `http://localhost:5173` |

**Key insight:** The existing patterns are the patterns. Every new piece in Phase 6 is either a property added to an existing class, a function added to an existing module, or a component using existing design tokens.

---

## Common Pitfalls

### Pitfall 1: asyncio.Event Created Outside Lifespan (Wrong Event Loop)

**What goes wrong:** If `app.state.start_event = asyncio.Event()` is called at module import time (e.g., as a module-level global), it binds to whatever event loop exists at import time — not the uvicorn event loop. `await event.wait()` in the game loop will raise `RuntimeError: got Future attached to a different loop`.

**Why it happens:** Python creates a new event loop per `asyncio.run()` call. FastAPI/uvicorn creates its own. Module-level asyncio objects bind to whichever loop was running at creation.

**How to avoid:** Create `asyncio.Event()` inside the `lifespan` async context manager, after the yield setup block. Assign to `app.state.start_event` there. This is the same reason `asyncio.Queue()` is created inside `broker.subscribe()` (see broker.py comment: "Queue is created here (inside async def) to avoid Pitfall 5 (wrong event loop)"). [VERIFIED: backend/app/broadcast/broker.py line 45]

**Warning signs:** `RuntimeError: got Future attached to a different loop` at first SSE connect or game loop start.

### Pitfall 2: Race Condition — game_running Flag vs. SSE Snapshot

**What goes wrong:** A viewer connects between `app.state.game_running = True` being set and `publish_game_status(running=True)` being broadcast. The SSE snapshot sequence reads `app.state.game_running` (True), sends `game_status { running: true }`. The viewer lands in the game view. But if the flag is not set before the broadcast, a viewer connecting between `start_event.set()` and `game_running = True` would get `running: false` from the snapshot and show the idle screen even though the game started.

**How to avoid:** In game_loop.py, set `app.state.game_running = True` BEFORE calling `publish_game_status(running=True)`. Same ordering principle as the SET-before-PUBLISH pattern in publisher.py (line 39-41). [VERIFIED: backend/app/broadcast/publisher.py]

**Warning signs:** Viewer occasionally lands on idle screen even though a game just started (timing-dependent flicker).

### Pitfall 3: Double-Start Race — Two Viewers Click Simultaneously

**What goes wrong:** Two viewers click "Start a Game" within milliseconds. Both POST `/api/game/start`. The endpoint checks `app.state.game_running` — both see `False`. Both set `start_event`. Only one game runs, but the second `Event.set()` is consumed by... nothing (Event was already cleared by the first). This is actually benign for `asyncio.Event` because `event.set()` on an already-set Event is a no-op in Python.

**Why it's safe:** `asyncio.Event.set()` is idempotent — setting an already-set event does nothing. The game loop calls `event.clear()` right after `event.wait()` returns, before running the session. The second viewer's POST returns 409 because `app.state.game_running` will be True by the time it's processed (FastAPI processes requests sequentially within a single coroutine on the event loop). [ASSUMED — asyncio.Event.set() idempotency is documented behavior but the exact interleaving with FastAPI request concurrency warrants a test]

**How to avoid:** Return 409 from `POST /api/game/start` if `app.state.game_running` is True. Since FastAPI/asyncio processes one await at a time, setting the flag before broadcasting ensures the second request sees it.

### Pitfall 4: CancelledError Swallowed in Demand-Gate Loop

**What goes wrong:** Adding `try/except Exception` around the `asyncio.Event.wait()` call would catch `CancelledError` in Python 3.7 (where it inherits from `Exception`). In Python 3.8+, `CancelledError` inherits from `BaseException` and is not caught by `except Exception`. However, if the except block uses bare `except:` or `except BaseException`, the game loop won't cleanly shut down.

**Why it matters:** The existing game_loop.py already has `except asyncio.CancelledError: raise` at line 81. The demand-gate refactor must preserve this pattern for the new `asyncio.Event.wait()` in the outer loop. [VERIFIED: backend/app/game_loop.py lines 81-83]

**How to avoid:** Wrap the `await start_event.wait()` call in the same outer `try/except asyncio.CancelledError` block that currently wraps the session. Never add bare `except:` in the game loop.

### Pitfall 5: StakeChip Not Clickable (onClick Prop Missing)

**What goes wrong:** StakeChip.tsx does not accept an `onClick` prop or `cursor: pointer`. The prediction widget needs to use it as a button. Passing `onClick` to a component that doesn't wire it to the `div` will silently do nothing.

**How to avoid:** PredictionWidget.tsx should either (a) wrap StakeChip in a `<button>` element with a Balatro-styled reset, or (b) extend StakeChip to accept `onClick?: () => void` and apply `cursor: pointer` when provided. Option (b) is cleaner since StakeChip is already the visual component. [VERIFIED: frontend/src/components/StakeChip.tsx — no onClick prop exists]

### Pitfall 6: game_status Not in broker.run_subscriber Channel Map

**What goes wrong:** `game_status` events are published to Redis via a new channel (e.g., `game:status`), but `broker.run_subscriber()` only subscribes to `game:state` and `game:reasoning` (hardcoded in `channels` list at line 87). If the new channel is not added, SSE clients never receive `game_status` events.

**How to avoid:** Add `"game:status"` to the `channels` list in `broker.run_subscriber()` and add `"game:status": "game_status"` to `event_name_by_channel`. Alternatively, publish `game_status` directly to client queues via `broker.broadcast()` (bypassing Redis pub/sub entirely) — simpler since `game_status` is always generated by the local process. [VERIFIED: backend/app/broadcast/broker.py lines 86-88]

**Recommendation:** Publish `game_status` directly via `broker.broadcast()` rather than through Redis pub/sub. It's always local-process-generated (unlike `game_state` which comes from the game engine callback chain). This avoids adding a third Redis channel and simplifies the broker. The `publish_game_status()` function in publisher.py should call `broker.broadcast()` directly or accept the broker as a parameter.

### Pitfall 7: phase String Case Mismatch for Prediction Widget Visibility

**What goes wrong:** CONTEXT.md says show widget on "PRE-FLOP, FLOP, TURN, RIVER" (uppercase). The backend GameState phase field uses lowercase with hyphens: `'pre-flop'`, `'flop'`, `'turn'`, `'river'`, `'showdown'`. Game.tsx already handles this with `PHASE_DISPLAY` mapping (line 18-22). The frontend `gameState.phase` from the SSE payload will be lowercase.

**How to avoid:** PredictionWidget.tsx must compare against lowercase phase strings: `['pre-flop', 'flop', 'turn', 'river'].includes(gameState.phase)`. Do not compare against uppercase. [VERIFIED: backend/app/engine/models.py GameState.phase is a plain string; Game.tsx PHASE_DISPLAY map shows lowercase keys like 'PRE-FLOP' which are actually the backend values]

**Wait — correction:** Game.tsx PHASE_DISPLAY keys are 'DEALING', 'PRE-FLOP', 'FLOP', etc. (uppercase). These match what the backend sends. The backend phase field in GameState uses uppercase strings like 'PRE-FLOP', 'FLOP', 'WINNER'. [VERIFIED: backend/app/broadcast/publisher.py — GameState.phase is set by game engine; Game.tsx line 18-22 shows keys ARE uppercase like 'DEALING', 'PRE-FLOP', 'FLOP', etc.] Phase strings from the backend are uppercase.

**Confirmed:** Use uppercase phase strings for visibility check: `['PRE-FLOP', 'FLOP', 'TURN', 'RIVER'].includes(gameState.phase)`.

---

## Code Examples

### Pattern 1: asyncio.Event Demand Gate in game_loop.py

[VERIFIED: based on existing game_loop.py structure + asyncio.Event stdlib]

```python
# In lifespan (main.py) — create inside async context to bind to correct event loop
app.state.start_event = asyncio.Event()
app.state.game_running = False

# game_loop.py — demand-gated loop
async def run_game_loop(redis_client, settings, start_event, app_state) -> None:
    logger.info("Game loop started — waiting for viewer trigger")
    while True:
        try:
            await start_event.wait()        # suspend until POST /api/game/start
            start_event.clear()             # consume the signal
            app_state.game_running = True   # SET BEFORE broadcast (race prevention)
            await publish_game_status(broker, redis_client, running=True)

            # ... run session ...
            session = GameSession(...)
            await session.run(n_hands=10, ...)

            # Store last result to Redis, then signal idle
            winner_player = session.players[final_winner_idx]
            await redis_client.set(
                GAME_LAST_RESULT_KEY,
                json.dumps({"winnerName": winner_player.name,
                            "winnerOrg": winner_player.org,
                            "winnerHand": final_hand_name}),
                ex=86400  # 24h TTL
            )
            app_state.game_running = False
            await publish_game_status(broker, redis_client, running=False)

        except asyncio.CancelledError:
            logger.info("Game loop cancelled — shutting down")
            raise  # MUST propagate
        except Exception as exc:
            logger.error("Game loop error: %s", exc, exc_info=True)
            app_state.game_running = False
            await asyncio.sleep(1)  # brief pause before returning to wait
```

### Pattern 2: broker.viewer_count Property

[VERIFIED: backend/app/broadcast/broker.py — `_queues: list[asyncio.Queue]`]

```python
@property
def viewer_count(self) -> int:
    """Return number of currently connected SSE clients."""
    return len(self._queues)
```

Note: No lock needed for reading `len()` — this is a point-in-time snapshot, acceptable for the demand-gate check. Atomicity is not required since the game loop double-checks `game_running` before broadcasting.

### Pattern 3: publish_game_status() in publisher.py

[VERIFIED: based on existing publish() and broker.broadcast() pattern]

```python
GAME_LAST_RESULT_KEY = "game:last_result"

async def publish_game_status(
    broker: "EventBroker",
    redis_client: redis.Redis,
    running: bool,
) -> None:
    """
    Broadcast game_status event directly to all connected clients.
    Uses broker.broadcast() directly — no Redis pub/sub channel needed.
    When running=False, reads game:last_result from Redis to include lastWinner.
    """
    if running:
        payload = json.dumps({"running": True})
    else:
        last_result_raw = await redis_client.get(GAME_LAST_RESULT_KEY)
        last_winner = None
        if last_result_raw:
            data = json.loads(last_result_raw.decode("utf-8") if isinstance(last_result_raw, bytes) else last_result_raw)
            last_winner = {
                "name": data["winnerName"],
                "org": data["winnerOrg"],
                "hand": data["winnerHand"],
            }
        payload = json.dumps({"running": False, "lastWinner": last_winner})

    envelope = json.dumps({"event": "game_status", "data": payload})
    await broker.broadcast(envelope)
```

### Pattern 4: stream.py snapshot extension (game_status)

[VERIFIED: backend/app/api/stream.py — existing snapshot sequence at lines 46-72]

```python
# After existing reasoning_snapshot block, add game_status snapshot:
game_running: bool = getattr(request.app.state, "game_running", False)
last_result_raw = await redis_client.get(GAME_LAST_RESULT_KEY)
if game_running:
    status_payload = json.dumps({"running": True})
else:
    last_winner = None
    if last_result_raw:
        data = json.loads(last_result_raw.decode("utf-8") if isinstance(last_result_raw, bytes) else last_result_raw)
        last_winner = {"name": data["winnerName"], "org": data["winnerOrg"], "hand": data["winnerHand"]}
    status_payload = json.dumps({"running": False, "lastWinner": last_winner})

yield ServerSentEvent(
    raw_data=status_payload,
    event="game_status",
    id=str(broker.next_id()),
    retry=3000,
)
```

### Pattern 5: POST /api/game/start endpoint

[VERIFIED: based on health.py and stream.py APIRouter patterns]

```python
# backend/app/api/game.py
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()

@router.post("/api/game/start")
async def start_game(request: Request):
    broker = request.app.state.broker
    start_event = request.app.state.start_event

    if request.app.state.game_running:
        raise HTTPException(status_code=409, detail="Game already running")
    if broker.viewer_count < 1:
        raise HTTPException(status_code=503, detail="No viewers connected")

    start_event.set()
    return {"started": True}
```

### Pattern 6: useGameStream extension (gameRunning state)

[VERIFIED: frontend/src/hooks/useGameStream.ts — existing addEventListener pattern]

```typescript
// Add to GameStream interface:
export interface GameStream {
  gameState: GameState | null
  reasoning: ReasoningEntry[]
  connectionState: ConnectionState
  gameRunning: boolean | null  // null = unknown (connecting)
}

// Add GameStatus type to types.ts:
export interface GameStatus {
  running: boolean
  lastWinner?: { name: string; org: string; hand: string } | null
}

// Inside useGameStream useEffect:
const [gameRunning, setGameRunning] = useState<boolean | null>(null)

es.addEventListener('game_status', (e: MessageEvent) => {
  try {
    const status: GameStatus = JSON.parse(e.data as string)
    setGameRunning(status.running)
  } catch (err) {
    console.error('[useGameStream] Failed to parse game_status event:', err)
  }
})
```

### Pattern 7: PokerApp.tsx routing

[VERIFIED: frontend/src/components/PokerApp.tsx — current structure renders <Game> directly]

```tsx
// Replace direct <Game> render with routing:
const { gameState, reasoning, connectionState, gameRunning } = useGameStream()

if (gameRunning === null) {
  return <LoadingScreen theme={theme} />    // or inline loading div
}
if (gameRunning === false) {
  return <IdleScreen theme={theme} lastWinner={...} onStart={handleStart} />
}
// gameRunning === true
return <Game theme={theme} gameState={gameState} reasoning={reasoning} connectionState={connectionState} />
```

### Pattern 8: PredictionWidget localStorage handling

[VERIFIED: localStorage API (browser built-in); CONTEXT.md D-11 schema]

```typescript
const PREDICTION_KEY = 'poker_prediction'

interface PredictionRecord {
  handId: string
  prediction: string  // playerId
  result: 'correct' | 'wrong' | null
}

function loadPrediction(): PredictionRecord | null {
  try {
    const raw = localStorage.getItem(PREDICTION_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

function savePrediction(record: PredictionRecord): void {
  localStorage.setItem(PREDICTION_KEY, JSON.stringify(record))
}
```

### Pattern 9: IdleScreen "Start a Game" button POST

[VERIFIED: VITE_API_URL pattern from useGameStream.ts line 21; CONTEXT.md D-05]

```typescript
const _base = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const START_URL = new URL('/api/game/start', _base).toString()

async function handleStart(): Promise<void> {
  try {
    const res = await fetch(START_URL, { method: 'POST' })
    if (res.status === 409) console.warn('Game already running')
    else if (res.status === 503) console.warn('No viewers connected (should not happen)')
    // On success, game_status { running: true } will arrive via SSE
    // and PokerApp routing will switch to <Game> automatically
  } catch (err) {
    console.error('Failed to start game:', err)
  }
}
```

### Pattern 10: Balatro button styling for IdleScreen

[VERIFIED: frontend/src/index.css — .bal-btn, .bal-btn-orange classes defined at lines 109-135]

```tsx
// Use existing CSS class — no inline style needed for button base
<button
  className="bal-btn bal-btn-orange"
  disabled={isStarting}
  onClick={handleStart}
  style={{ fontSize: 20, height: 52, padding: '0 32px' }}
>
  START A GAME
</button>
```

---

## Existing Code Integration Points

### broker.py Integration

Current `_queues: list[asyncio.Queue]` (line 28). The `viewer_count` property is simply `len(self._queues)`. The property requires no lock — a point-in-time count is sufficient for the demand-gate heuristic.

Existing subscribe/unsubscribe methods use `self._lock`. The `len()` read is not atomic with subscribe/unsubscribe, but this is acceptable: if a viewer disconnects microseconds before the count is checked, the worst outcome is a 503 response that the viewer immediately retries (they reconnected).

### publisher.py Integration

`SNAPSHOT_KEY`, `REASONING_SNAPSHOT_KEY` constants already follow the `game:*` naming convention. New constant `GAME_LAST_RESULT_KEY = "game:last_result"` follows the same pattern. The `SNAPSHOT_TTL = 3600` can be reused for `game:last_result` TTL.

The `publish_game_status()` function should accept the broker instance directly (not go through Redis pub/sub) since game_status is always generated by the local FastAPI process. This avoids adding a third Redis channel.

### stream.py Integration

The snapshot sequence at lines 46-72 must be extended with a `game_status` snapshot AFTER the reasoning_snapshot block. The ordering matters: game_status is the last snapshot item so the frontend can use it to decide whether to show Game or IdleScreen based on the most complete state information.

Import addition needed: `from app.broadcast.publisher import SNAPSHOT_KEY, REASONING_SNAPSHOT_KEY, GAME_LAST_RESULT_KEY`

### game_loop.py Integration

The current function signature `run_game_loop(redis_client, settings)` must be extended to receive `start_event` and a reference to `app.state` (or just `app`). The cleanest pattern: pass `app_state` (which is `app.state`) as a parameter, consistent with the existing `settings` parameter pattern.

The `while True` loop body must change from:
```
run session → sleep
```
to:
```
wait on event → clear event → set game_running=True → broadcast running → run session → store last_result → set game_running=False → broadcast idle
```

The `hand_delay_seconds` sleep between sessions is removed — the demand gate replaces it.

### main.py Integration

Two additions needed:
1. In lifespan startup: create `app.state.start_event = asyncio.Event()` and `app.state.game_running = False`
2. Include the new `game` router: `app.include_router(game_router)`
3. Pass `start_event` and `app.state` (or just `app`) to `run_game_loop()`

The existing CORS middleware covers the new `/api/game/start` endpoint automatically — no changes needed.

### useGameStream.ts Integration

The hook currently returns `{ gameState, reasoning, connectionState }`. After Phase 6 it returns `{ gameState, reasoning, connectionState, gameRunning }`. The `lastWinner` from `game_status` needs to be surfaced too (for IdleScreen). Two options:

**Option A:** Return `gameStatus: GameStatus | null` from the hook — IdleScreen reads `gameStatus.lastWinner`.
**Option B:** Return `gameRunning: boolean | null` and `lastWinner: { name, org, hand } | null` as separate fields.

Option B is simpler and matches the D-03 spec exactly. `lastWinner` is set when a `game_status { running: false, lastWinner: ... }` event arrives.

### PokerApp.tsx Integration

Current: renders `<TweaksPanel>` + `<Game>` unconditionally.
After Phase 6: routes on `gameRunning` state. The TweaksPanel is only meaningful during a game, so it should only render in the `gameRunning === true` branch (or could be deferred to v2).

The `settings` and theme logic can stay at the PokerApp level — passed down to whichever screen is active.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Continuous game loop (while True: run_session()) | Demand-gated (asyncio.Event wait) | Phase 6 | Game only runs when a viewer triggers it — core CLAUDE.md constraint |
| No idle state in SSE | `game_status` event in snapshot + transitions | Phase 6 | Frontend knows game state before any game_state events arrive |
| No REST game control | `POST /api/game/start` | Phase 6 | Viewer agency; server validates presence before starting |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `asyncio.Event.set()` is safe to call from multiple concurrent requests without a lock — idempotent | Pitfall 3 | Double-start scenario could trigger two sessions; mitigated by `game_running` flag check returning 409 |
| A2 | `len(self._queues)` read is safe without acquiring `self._lock` in `viewer_count` property | broker.py Integration | Could theoretically race with subscribe/unsubscribe but worst case is off-by-one count, acceptable |
| A3 | `game_loop.py` can receive `app_state` as a parameter rather than accessing `app` globally | game_loop.py Integration | If session.py or another layer needs app state, may need different approach |
| A4 | Phase strings from backend are uppercase ('PRE-FLOP', 'FLOP', etc.) — confirmed from Game.tsx PHASE_DISPLAY map | Pitfall 7 | Prediction widget would never show if wrong case used |

A4 is marked VERIFIED (not assumed) based on codebase evidence in Game.tsx PHASE_DISPLAY keys.

**If this table has A1-A3:** Only three minor assumptions, all low-risk with existing guards. No user confirmation needed before planning.

---

## Open Questions

1. **Where does `game_loop.py` get the session winner information to store in Redis?**
   - What we know: `session.run()` is async and runs hands. `GameSession` has a `players` list. The final session state has chip counts.
   - What's unclear: Does `session.run()` return the winner, or must `game_loop.py` inspect `session.players` after completion to find the chip leader? The current `session.run()` return value is unknown.
   - Recommendation: Inspect `backend/app/engine/session.py` `run()` method return value during planning. If it doesn't return winner info, determine it by finding the player with most chips at session end.

2. **Does `publish_game_status()` need the broker as a parameter, or should it read from `app.state.broker`?**
   - What we know: The existing `publish()` function only takes `redis_client` and `state` — no broker needed (it goes through Redis pub/sub). The proposed `publish_game_status()` bypasses Redis pub/sub and calls `broker.broadcast()` directly.
   - What's unclear: Whether to pass broker as a parameter to `publish_game_status()` or import it.
   - Recommendation: Pass broker as a parameter — matches existing `publish()` function's explicit dependency injection style. The planner can choose the exact signature.

3. **Should the loading state (gameRunning === null) be a separate component or an inline div in PokerApp?**
   - What we know: Currently Game.tsx renders "Connecting to game..." when `gameState === null`. After Phase 6, PokerApp handles routing before Game is even mounted.
   - Recommendation: Inline loading div in PokerApp (same style as Game.tsx's null guard) — avoids a third component file for a transient state. Claude's discretion per CONTEXT.md.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Backend game_loop refactor | Yes | 3.14.3 | — |
| uv | Backend package management | Yes | 0.11.6 | — |
| Node.js | Frontend dev/build | Yes | v24.13.0 | — |
| Docker | Redis (via docker-compose) | Yes | 29.4.2 | — |
| Redis | game:last_result persistence, SSE snapshot | Via Docker (redis:7-alpine in docker-compose.yml) | 7-alpine | — |
| redis-cli | Manual Redis inspection | Not in PATH | — | Docker exec: `docker compose exec redis redis-cli` |

**Missing dependencies with no fallback:** None — all required dependencies are available.

**Redis note:** Redis runs via Docker Compose (`docker compose up -d redis`). Not directly available on host PATH but accessible through the existing docker-compose.yml. [VERIFIED: docker-compose.yml, Docker 29.4.2 confirmed]

---

## Validation Architecture

> `nyquist_validation` is explicitly `false` in `.planning/config.json` — this section is SKIPPED.

---

## Security Domain

Phase 6 introduces one new attack surface: `POST /api/game/start`. Relevant controls:

| Control | Status | Notes |
|---------|--------|-------|
| Rate limiting on POST /api/game/start | Not required for v1 | Only consequence of spam: 409 responses after first success; game loop is protected by `game_running` flag |
| CORS on new endpoint | Handled | Existing CORSMiddleware in main.py covers all routes including new game router |
| Input validation | N/A | POST /api/game/start has no request body |
| localStorage prediction data | Client-side only | No server trust in prediction data; it is never sent to backend |
| Viewer anonymity | Preserved | No session, no auth, no identity in v1 (locked decision) |

No new security concerns beyond what existing architecture already handles. [VERIFIED: main.py CORS config, CONTEXT.md "Out of Scope: User authentication"]

---

## Sources

### Primary (HIGH confidence — verified against codebase)
- `backend/app/broadcast/broker.py` — EventBroker._queues, subscribe/unsubscribe/broadcast patterns
- `backend/app/broadcast/publisher.py` — publish(), SNAPSHOT_KEY, SNAPSHOT_TTL, Redis SET-before-PUBLISH pattern
- `backend/app/api/stream.py` — snapshot sequence, envelope handling, SSE event naming
- `backend/app/game_loop.py` — existing loop structure, CancelledError re-raise rule
- `backend/app/main.py` — lifespan pattern, app.state usage, router inclusion
- `backend/app/config.py` — Settings fields, hand_delay_seconds
- `frontend/src/hooks/useGameStream.ts` — SSE listener pattern, existing event types
- `frontend/src/components/PokerApp.tsx` — current component structure
- `frontend/src/components/StakeChip.tsx` — props interface (no onClick)
- `frontend/src/components/types.ts` — Player, GameState, ModelId interfaces
- `frontend/src/lib/constants.ts` — STAKE_COLORS, THEMES, MODELS, STAKE_MAP
- `frontend/src/index.css` — .bal-btn CSS classes, keyframe animations
- `frontend/src/components/Game.tsx` — PHASE_DISPLAY map (confirms uppercase phase strings), winner overlay pattern
- `.planning/phases/06-viewer-experience/06-CONTEXT.md` — all 16 locked decisions
- `.planning/REQUIREMENTS.md` — VIEWER-01/02/03 text
- `models.config.json` — player IDs, names, orgs, colors, stake colors

### Secondary (MEDIUM confidence)
- Python stdlib asyncio.Event documentation [ASSUMED: training knowledge, not re-verified via web, but asyncio.Event is stable stdlib]

---

## Metadata

**Confidence breakdown:**
- Backend wiring (asyncio.Event, broker.viewer_count, publish_game_status, Redis last_result): HIGH — all patterns are direct extensions of verified existing code
- SSE snapshot extension: HIGH — stream.py snapshot sequence is clearly readable, extension point is unambiguous
- Frontend routing (PokerApp, useGameStream): HIGH — existing hook and component structure is fully read
- IdleScreen visual design: MEDIUM — design guidance from existing components/CSS is thorough; exact layout is Claude's discretion
- PredictionWidget localStorage: HIGH — browser API is trivial; schema is locked by D-11
- Phase string case (uppercase vs lowercase): HIGH — verified from Game.tsx PHASE_DISPLAY map

**Research date:** 2026-05-12
**Valid until:** Indefinite — all findings are against local codebase, not remote sources
