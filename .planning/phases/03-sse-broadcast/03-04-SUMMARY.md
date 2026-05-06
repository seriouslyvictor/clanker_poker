---
phase: 03-sse-broadcast
plan: 04
subsystem: sse-endpoint
tags: [fastapi, sse, streaming, lifespan, redis, asyncio]

# Dependency graph
requires:
  - phase: 03-sse-broadcast
    plan: 03
    provides: EventBroker, publisher.publish, run_game_loop
provides:
  - GET /api/stream SSE endpoint (STREAM-01, STREAM-02, STREAM-03)
  - Expanded FastAPI lifespan with Redis + broker + background task wiring
  - Complete broadcast pipeline integration (game loop → publisher → Redis → broker → SSE)
affects:
  - Phase 4 (LLM reasoning endpoint can hook into same broadcast pipeline)
  - Phase 5+ (client-side SSE consumption tested)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - EventSourceResponse with response_class (native FastAPI 0.136.1 SSE)
    - ServerSentEvent with raw_data= for pre-serialized JSON from Redis
    - Lifespan @asynccontextmanager for startup/shutdown orchestration
    - Per-client asyncio.Queue subscription (fan-out pattern from broker)
    - Background task creation via asyncio.create_task() in lifespan startup
    - Request.app.state for test-injectable shared dependencies
    - _fastapi_routing._PING_INTERVAL patching for 5s heartbeat

key-files:
  created:
    - backend/app/api/stream.py (GET /api/stream SSE endpoint, 71 lines)
  modified:
    - backend/app/main.py (lifespan expansion, router registration, 90 lines)

key-decisions:
  - Subscribe BEFORE snapshot read (Pitfall 4 avoidance): any events arriving during snapshot fetch land in queue
  - raw_data= (not data=) for Redis messages: payload is already JSON string from Redis bytes
  - app.state.broker / app.state.redis_client: shared state on app (not module globals) enables test fixture injection
  - Unsubscribe in finally block: prevents orphaned queue memory leaks on client disconnect
  - Heartbeat via _PING_INTERVAL = 5.0: patched once in lifespan startup, applies to all EventSourceResponse instances
  - Shutdown order: cancel game_loop first (stops new publishes), then subscriber (avoids race)

requirements-completed:
  - STREAM-01 (SSE endpoint with identical state to all clients)
  - STREAM-02 (late-joiner snapshot as first event)
  - STREAM-03 (5s heartbeat via _PING_INTERVAL, X-Accel-Buffering: no auto-set)

# Metrics
duration: 5min
completed: 2026-05-06
---

# Phase 3 Plan 04: SSE Endpoint & Lifespan Wiring — Summary

**GET /api/stream SSE endpoint created and wired into expanded FastAPI lifespan. Redis connection, EventBroker, subscriber task, and game loop task all connected. Complete broadcast pipeline now operational.**

## Performance

- **Duration:** 5 min
- **Tasks:** 2
- **Files created:** 1
- **Files modified:** 1

## Accomplishments

### Task 1: Create GET /api/stream SSE endpoint (backend/app/api/stream.py)

**File: 71 lines**

Implements STREAM-01, STREAM-02, STREAM-03 requirements:

- **Route:** `GET /api/stream` with `response_class=EventSourceResponse`
- **Response type:** `AsyncIterable[ServerSentEvent]`
- **Late-joiner snapshot** (STREAM-02):
  - Subscribe to broker queue FIRST (Pitfall 4 avoidance)
  - Read Redis snapshot key (SNAPSHOT_KEY = "game:state:last")
  - Send snapshot as first event with `raw_data=` (pre-serialized JSON from Redis)
  - Then drain live events from queue
- **Live events** (STREAM-01):
  - Drain queue via `queue.get()` with 1.0s timeout
  - Monotonically increasing ID via `broker.next_id()` on every event
  - Check `request.is_disconnected()` to exit on client close
- **Heartbeat** (STREAM-03):
  - Auto-sent by FastAPI via `_PING_INTERVAL` (patched to 5.0s in lifespan)
  - No manual implementation needed
  - Comments (`: ping`) sent by EventSourceResponse automatically
- **Connection cleanup:**
  - Unsubscribe in `finally` block to prevent queue leaks
  - Safe against double-unsubscribe (try/except ValueError in broker)
- **Dependency access:**
  - `request.app.state.broker` (set by lifespan)
  - `request.app.state.redis_client` (set by lifespan)
  - No module-level globals — supports test injection

**Verification:**
- Import: `from app.api.stream import router` → passes
- Criteria: response_class, raw_data usage, subscribe-before-snapshot order, finally block, app.state access all verified

### Task 2: Expand FastAPI lifespan and register stream router (backend/app/main.py)

**File: 90 lines (expanded from 30)**

Lifespan orchestration and router registration:

**Startup sequence (5 steps in order):**

1. **Patch SSE heartbeat:** `_fastapi_routing._PING_INTERVAL = 5.0` (must happen before any EventSourceResponse creation)
2. **Redis connection:** `app.state.redis_client = redis_asyncio.from_url(settings.redis_url, decode_responses=False)`
   - `decode_responses=False` per Pitfall 3 — messages arrive as bytes, decoded manually in broker
3. **EventBroker:** `app.state.broker = EventBroker()` (singleton for this app instance)
4. **Subscriber background task:** `asyncio.create_task(broker.run_subscriber(redis_client, "game:state"))`
   - Subscribes to Redis pub/sub channel
   - Fans out messages to all connected client queues
5. **Game loop background task:** `asyncio.create_task(run_game_loop(redis_client, settings))`
   - Continuous loop: create GameSession(n_players=4, ...), run 10 hands, wait hand_delay_seconds, repeat
   - Broadcasts state at each phase transition via publisher.publish()

**Shutdown sequence (reverse order, safe exception handling):**

1. Cancel game loop task (stops new publishes)
2. Cancel subscriber task
3. Await both tasks with try/except for `asyncio.CancelledError` and other exceptions (both expected)
4. Close Redis connection: `await redis_client.aclose()`

**Router registration:**
- `app.include_router(health_router)` (preserved from original)
- `app.include_router(stream_router)` (new)

**CORS middleware:**
- Preserved from original configuration
- Uses pydantic Settings cors_origins list
- Configured with allow_credentials=True + specific origins (never `["*"]` with credentials)

**State management:**
- All shared state on `app.state` (not module-level globals)
- Enables test fixtures to inject mocks
- Clean dependency injection for endpoints

**Verification:**
- Import: `from app.main import app` → passes
- Routes: `app.routes` shows `/health` and `/api/stream` both registered
- Criteria: _PING_INTERVAL patching, redis_asyncio usage, decode_responses=False, broker creation, two create_task calls, stream_router registration, CORS preserved, correct shutdown order, aclose() all verified

## Task Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | `695ee93` | feat(03-04): create GET /api/stream SSE endpoint |
| 2 | `598a3c1` | feat(03-04): expand FastAPI lifespan with Redis + broker + background tasks |

## Verification Results

**Import checks:**
```
from app.main import app                    ✓ OK
from app.api.stream import router           ✓ OK
```

**Route registration:**
```
app.routes: ['/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc', '/health', '/api/stream']
                                                                                             ✓ Both registered
```

**Phase 2 test suite:**
```
136 passed, 1 skipped
```
All prior game engine tests still pass — no regressions.

**Acceptance criteria all verified:**
- GET /api/stream importable ✓
- EventSourceResponse response_class ✓
- Subscribe before snapshot (order verified) ✓
- Unsubscribe in finally block ✓
- raw_data= usage (not data=) ✓
- request.app.state.broker access ✓
- request.app.state.redis_client access ✓
- No manual X-Accel-Buffering header ✓
- _fastapi_routing._PING_INTERVAL = 5.0 ✓
- redis_asyncio.from_url with decode_responses=False ✓
- EventBroker instantiation ✓
- Two asyncio.create_task calls (subscriber + game loop) ✓
- stream_router registered ✓
- CORS middleware preserved ✓
- Cancel game_loop before subscriber_task ✓
- redis_client.aclose() in shutdown ✓

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria met on first attempt.

## Known Stubs

No known stubs or placeholders. The pipeline is complete and operational:
- Game loop runs continuously (Phase 3 placeholder — Phase 6 adds viewer trigger)
- SSE endpoint ready to serve live game state
- Late joiners receive full snapshot on connect

## Threat Flags

No new threat surfaces introduced:
- GET /api/stream is read-only, unauthenticated (T-03-11: info disclosure of game state is design intent — all viewers see same state)
- Redis connection is internal network (not exposed externally in v1)
- EventBroker queues bounded by maxsize=10 (T-03-09: DoS mitigation in place from Plan 03-03)
- Game loop exception handling prevents crash (T-03-10: graceful error recovery)

## Next Phase Readiness

**Complete broadcast pipeline operational:**
```
game_loop.run_game_loop()
    |
    | calls GameSession.run(n_hands=10, broadcast_fn=lambda state: publish(redis_client, state))
    |
    | (calls publish() at each phase transition: pre-flop, flop, turn, river, showdown)
    |
    v
publisher.publish(redis_client, state)
    |
    | model_dump_json(by_alias=True)
    |
    | SET snapshot, then PUBLISH to Redis channel
    |
    v
Redis pub/sub "game:state"
    |
    | message: {"phase": "flop", ...camelCase JSON...}
    |
    v
EventBroker.run_subscriber() (background task)
    |
    | redis pubsub.get_message(timeout=1.0)
    |
    | fan-out via broker.broadcast()
    |
    v
N x asyncio.Queue (one per SSE client)
    |
    | queue.get() in SSE generator
    |
    v
GET /api/stream SSE endpoint
    |
    | yield ServerSentEvent(raw_data=data, event="game_state", id=...)
    |
    v
Browser EventSource (WebAPI)
    |
    | addEventListener("game_state", (event) => { /* Next.js React state update */ })
    |
    v
Next.js Game component re-renders with live state
```

**Ready for Phase 4:**
- SSE endpoint fully operational
- Can add per-player LLM reasoning event stream on separate event type (e.g., `event: reasoning`)
- Same EventBroker can fan-out multiple event types

---

*Phase: 03-sse-broadcast*
*Plan: 04*
*Completed: 2026-05-06*
