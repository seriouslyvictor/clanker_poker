# Phase 6: Viewer Experience — Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Viewers land on an idle screen when no game is running. Any viewer can trigger a game start (demand-gated server-side). Before showdown, viewers can anonymously predict the winner (localStorage). After showdown, UI returns to the idle screen showing the last result.

The idle → live game → winner overlay → idle cycle must close cleanly.

</domain>

<decisions>
## Implementation Decisions

### Idle State Signal
- **D-01:** Backend sends `event: game_status` as a new SSE event type. Payload: `{ running: boolean, lastWinner: { name, org, hand } | null }`. When `running: false`, `lastWinner` contains the most recent session winner (or null if no game has ever run). When `running: true`, `lastWinner` is omitted.
- **D-02:** `game_status` fires in two situations: (a) on every SSE connect/reconnect — included in the snapshot sequence so late joiners know state immediately, and (b) on session transitions — when a session starts (`running: true`) and when a session ends (`running: false` with updated `lastWinner`).
- **D-03:** `useGameStream` hook gains a `gameRunning: boolean | null` state (null = unknown/still connecting). `PokerApp.tsx` routes on this: `gameRunning === null` → loading, `gameRunning === false` → idle screen, `gameRunning === true` → `<Game>` component.
- **D-04:** A second viewer who arrives while a game is in progress receives `game_status { running: true }` → lands directly in the live game view. No idle screen.

### Game Trigger & Demand Gate
- **D-05:** New REST endpoint: `POST /api/game/start`. Backend checks: (a) no game currently running, (b) `broker.viewer_count >= 1`. If both conditions met, sets an `asyncio.Event` that the game loop is waiting on. Returns 400 if game already running or no viewers connected.
- **D-06:** `game_loop.py` becomes demand-gated: after each session completes, it waits on the asyncio.Event (does not auto-loop). The Event is created in lifespan and stored on `app.state.start_event`. Game loop pattern: wait → clear event → run session → broadcast `game_status { running: false }` → wait again.
- **D-07:** `EventBroker` gains a `viewer_count` property returning the current number of active subscriber queues. Used by `POST /api/game/start` to enforce the demand-triggered constraint (VIEWER-02 server-side gate).
- **D-08:** `POST /api/game/start` broadcasts `event: game_status { running: true }` immediately when the game is triggered — before the first hand begins. All connected viewers see the transition synchronously.

### Prediction Widget
- **D-09:** Prediction widget is a floating overlay positioned above the community card area (same layer as the winner overlay). It appears when the current game phase is PRE-FLOP, FLOP, TURN, or RIVER — and disappears when phase becomes SHOWDOWN or WINNER.
- **D-10:** Per-hand predictions: each hand is a fresh prediction. When winner transitions from non-null to null (new hand started — already detected in `useGameStream`), the prediction resets.
- **D-11:** localStorage key: `poker_prediction` stores `{ handId: string, prediction: playerId, result: 'correct' | 'wrong' | null }`. `handId` is assigned on the frontend when a new hand starts (e.g., timestamp-based). Result is set at WINNER phase by comparing `prediction` against `gameState.winner`.
- **D-12:** Widget shows 4 player chips (one per player) using the existing `StakeChip` component. After the viewer picks, the widget collapses to show "Prediction: [player name]" until result is revealed. At WINNER phase, shows "Correct! 🎉" or "Wrong" in the same position before collapsing fully.

### Last Game Result
- **D-13:** Backend stores last result in Redis under key `game:last_result` after each session ends. Payload: `{ winnerName, winnerOrg, winnerHand }`. This Redis key persists until the next session completes (not cleared on server restart).
- **D-14:** `lastWinner` is piggybacked on the `game_status { running: false }` event. The backend reads `game:last_result` from Redis and includes it in the payload. Frontend does not need a separate fetch.
- **D-15:** Idle screen displays `lastWinner` as a callout below the branding: "[winnerOrg]'s [winnerName] won with [winnerHand]". If `lastWinner` is null, the callout is omitted.

### Module Layout
- **D-16 (Claude's Discretion):** New/modified files:
  ```
  backend/app/
  ├── api/
  │   └── game.py              ← POST /api/game/start endpoint
  ├── broadcast/
  │   └── publisher.py         ← extend with publish_game_status()
  ├── broker.py                ← add viewer_count property
  └── game_loop.py             ← demand-gated loop (asyncio.Event wait)

  frontend/src/
  ├── hooks/
  │   └── useGameStream.ts     ← add gameRunning state, game_status listener
  ├── components/
  │   ├── IdleScreen.tsx        ← new: idle UI with Start button + last result
  │   ├── PredictionWidget.tsx  ← new: floating prediction overlay
  │   └── PokerApp.tsx          ← routing logic (loading / idle / game)
  ```

### Claude's Discretion
- Idle screen visual design (branding layout, button styling — should match existing Balatro aesthetic)
- PredictionWidget animation (fade in/out timing)
- `handId` generation strategy (timestamp, UUID, or counter)
- `POST /api/game/start` response body (200 OK with `{ started: true }` or just 204)
- Exact asyncio.Event placement in app.state (attribute name, initialization)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 6 Requirements
- `.planning/REQUIREMENTS.md` — VIEWER-01, VIEWER-02, VIEWER-03 (idle screen, Start button demand gate, anonymous winner predictions)
- `.planning/ROADMAP.md` — Phase 6 success criteria (4 criteria, all must be TRUE)

### Existing Frontend
- `frontend/src/hooks/useGameStream.ts` — SSE hook to extend with `gameRunning` state and `game_status` event listener
- `frontend/src/components/PokerApp.tsx` — top-level routing component to extend with idle/game branching
- `frontend/src/components/Game.tsx` — live game component (not modified in this phase)
- `frontend/src/components/types.ts` — TypeScript interfaces; may need `GameStatus` type added
- `frontend/src/components/StakeChip.tsx` — reuse for prediction player chips
- `frontend/src/components/GoldCrownChip.tsx` — reuse for winner reveal in prediction result
- `frontend/src/lib/constants.ts` — THEMES, STAKE_COLORS, etc.

### Existing Backend
- `backend/app/game_loop.py` — demand-gate refactor; add asyncio.Event wait loop
- `backend/app/broadcast/publisher.py` — extend with `publish_game_status()`
- `backend/app/broadcast/broker.py` — add `viewer_count` property
- `backend/app/main.py` — add `app.state.start_event`; include new `api/game.py` router
- `backend/app/api/stream.py` — extend snapshot sequence to include `game_status` event on connect
- `backend/app/config.py` — review for any new config fields needed (e.g., game_status Redis key)

### Prior Phase Context
- `.planning/phases/03-sse-broadcast/03-CONTEXT.md` — D-04 (snapshot model), D-09 (per-client asyncio.Queue fan-out)
- `.planning/phases/04-llm-integration/04-CONTEXT.md` — D-14 (game_loop.py pattern), D-16 (module layout)
- `.planning/phases/05-frontend-wiring/05-01-SUMMARY.md` — Vite SPA scaffold decisions, component file structure

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `StakeChip.tsx` — chip button component; reuse for prediction player chips (one per player)
- `GoldCrownChip.tsx` — gold chip for winner identity; reuse in prediction result reveal
- `ConfettiBurst.tsx` — confetti animation; optionally reuse on correct prediction
- `useGameStream` winner null-transition detection (`prevWinnerRef`) — reuse to reset per-hand prediction
- `EventBroker.subscribe/unsubscribe` — extend with `viewer_count` property (count of active queues)

### Established Patterns
- SSE event types: `game_state`, `reasoning`, `reasoning_snapshot` — new `game_status` follows same envelope format (`{ event, data }`)
- `app.state.*` for shared server state — add `app.state.start_event: asyncio.Event` and `app.state.game_running: bool`
- `asyncio.CancelledError` re-raise rule in game_loop.py — must preserve in demand-gated loop
- Snapshot sequence in `stream.py`: subscribe → send snapshots → drain live events — extend to send `game_status` in snapshot sequence
- localStorage pattern: no existing precedent; `poker_prediction` key is the new entry point

### Integration Points
- `stream.py` snapshot sequence: after `game_state` snapshot, send `game_status` snapshot (read from `app.state.game_running` + `game:last_result` Redis key)
- `game_loop.py`: replace `while True: run session` with `while True: await start_event.wait(); start_event.clear(); broadcast game_status(running=True); run session; store last_result; broadcast game_status(running=False)`
- `PokerApp.tsx`: `const { gameState, reasoning, connectionState, gameRunning } = useGameStream()` — add routing logic before rendering `<Game>`

</code_context>

<specifics>
## Specific Requirements

- `event: game_status` payload when idle: `{ running: false, lastWinner: { name, org, hand } | null }`
- `event: game_status` payload when running: `{ running: true }`
- `POST /api/game/start` returns 409 if game already running, 503 if no viewers, 200 on success
- `broker.viewer_count` = count of active asyncio.Queue entries (len of subscriber set)
- Prediction widget appears on phases: PRE-FLOP, FLOP, TURN, RIVER; hidden on SHOWDOWN, WINNER, DEALING
- localStorage key: `poker_prediction` with shape `{ handId: string, prediction: playerId, result: 'correct' | 'wrong' | null }`
- Idle screen last result callout: "{winnerOrg}'s {winnerName} won with {winnerHand}" (omit if lastWinner is null)
- Redis key for last result: `game:last_result` (JSON string `{ winnerName, winnerOrg, winnerHand }`)

</specifics>

<deferred>
## Deferred Ideas

- **Live viewer count display** — listed in REQUIREMENTS.md v2. The `broker.viewer_count` will be wired for demand-gating, but exposing it to the idle screen UI is v2.
- **Prediction streak tracking** — localStorage streak counter across hands/games is v2.
- **Pre-game lobby countdown** — gather viewers before game starts; show who else is waiting. Listed as v2.
- **Configurable hands per session** — pending todo (`2026-05-10-configurable-hands-per-session.md`), relevant to backend but not blocking Phase 6 viewer UX.
- **Optional archetypes mode** — pending todo (`2026-05-10-optional-archetypes-mode.md`), backend-only, not blocking Phase 6.

</deferred>

---

*Phase: 06-viewer-experience*
*Context gathered: 2026-05-12*
