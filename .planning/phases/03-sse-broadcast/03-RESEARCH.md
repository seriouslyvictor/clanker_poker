# Phase 3: SSE Broadcast — Research

**Researched:** 2026-05-05
**Domain:** SSE, Redis Pub/Sub, asyncio fan-out, FastAPI streaming
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Use `redis.asyncio` (redis-py 4+) for pub/sub fan-out. No aioredis.
- **D-02:** `docker-compose.yml` added with a Redis service for local development. FastAPI still runs outside Docker via `uv run uvicorn`.
- **D-03:** Late-joiner snapshot stored in Redis as last serialized `GameState`. Read from Redis on connect; send as first event before subscribing to new events.
- **D-04:** Each broadcast event carries a **full `GameState` snapshot** (no deltas). Clients replace state on every event.
- **D-05:** Two event types: `event: game_state` (full payload) + SSE comment heartbeat (`: ping`) every 5 seconds.
- **D-06:** Broadcasts fire on **phase transitions only** (deal, flop, turn, river, showdown). Individual player actions are NOT broadcast in Phase 3.
- **D-07:** Each `game_state` event includes a monotonically increasing integer `id:` field. Counter is in-memory (per process).
- **D-08:** `GET /api/stream` — single endpoint all clients subscribe to.
- **D-09:** `fastapi.sse.EventSourceResponse` + `ServerSentEvent` (native FastAPI 0.136.1) for SSE wire format + per-client `asyncio.Queue` as local broker. Flow: game loop publishes to Redis pub/sub → subscriber asyncio task receives and enqueues into each connected client's queue → client SSE generator drains the queue. `X-Accel-Buffering: no` header set automatically by `EventSourceResponse`. (sse-starlette from initial discuss session replaced by native FastAPI SSE per research finding — see Critical Finding section.)
- **D-10:** FastAPI lifespan creates background asyncio task running `GameSession.run()` in a continuous loop. When a hand completes, waits `HAND_DELAY_SECONDS` then starts the next hand.
- **D-11:** `HAND_DELAY_SECONDS` added to `Settings` in `config.py` with default 3.
- **D-12:** New files: `api/stream.py`, `broadcast/__init__.py`, `broadcast/broker.py`, `broadcast/publisher.py`, `game_loop.py`.

### Claude's Discretion

- Redis channel name for game events (e.g., `game:state`)
- Exact Redis connection URL config field name
- Number of Redis pub/sub retry attempts on connection loss
- Heartbeat task implementation (separate asyncio task vs inline generator sleep)
- Error handling for Redis unavailability at startup

### Deferred Ideas (OUT OF SCOPE)

- Full app containerization (Dockerfile for FastAPI)
- Viewer-triggered game start (`POST /api/game/start`)
- Viewer presence tracking / demand-gated loop
- Per-player LLM reasoning event stream
- STREAM-04 (client auto-reconnect on disconnect)
- Redis persistence / AOF for crash recovery
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STREAM-01 | Python backend (FastAPI) serves game state via SSE — single endpoint pushes incremental game events to all connected clients; all viewers see identical state | Redis pub/sub fan-out pattern: publisher sends to one channel, all subscriber queues receive the same event. Confirmed via redis-py 7.4.0 asyncio examples. |
| STREAM-02 | Late joiners receive full current game state snapshot immediately on connection — no partial state, no waiting for next event | Redis `SET`/`GET` with `EX` for last snapshot key. On client connect, read snapshot before subscribing to channel. D-03 locked. |
| STREAM-03 | SSE connection includes 5s heartbeat and `X-Accel-Buffering: no` header — survives proxy buffering and corporate firewalls | sse-starlette `EventSourceResponse(ping=5, headers={"X-Accel-Buffering": "no"})`. FastAPI native SSE also available (see critical finding below). |
</phase_requirements>

---

## Summary

Phase 3 wires the Phase 2 game engine (`GameSession.run()`) into an SSE broadcast pipeline. The broadcast layer has three logical components: a **publisher** that serializes `GameState` and writes to Redis pub/sub, a **broker** that maintains per-client `asyncio.Queue` objects and fans out incoming Redis messages, and an **SSE endpoint** that drains each client's queue into the SSE wire format.

The CONTEXT.md locked `sse-starlette` for SSE (D-09), but a critical finding changes the trade-off: **FastAPI 0.136.1 (installed in the project) has built-in native SSE** via `fastapi.sse.EventSourceResponse` that automatically handles `X-Accel-Buffering: no`, `Cache-Control: no-cache`, and the `: ping` keepalive on a configurable interval. The native SSE does everything `sse-starlette` does, is better integrated, and requires zero additional dependencies. The planner should surface this to the user as a recommended change from D-09 — implementing with native FastAPI SSE saves a dependency and is the "read the docs first" outcome AGENTS.md demands.

**Primary recommendation:** Use `fastapi.sse.EventSourceResponse` (built into FastAPI 0.136.1) instead of `sse-starlette`. Set `fastapi.routing._PING_INTERVAL = 5.0` once at startup to match the 5-second heartbeat requirement (D-05, STREAM-03).

---

## Critical Finding: Native FastAPI SSE

**This supersedes the sse-starlette choice in D-09.** [VERIFIED: inspected installed fastapi 0.136.1 source at `backend/.venv/Lib/site-packages/fastapi/sse.py`]

FastAPI 0.136.1 ships `fastapi.sse` with:

- `EventSourceResponse` — use as `response_class=EventSourceResponse` on the route
- `ServerSentEvent` — Pydantic model with `data`, `raw_data`, `event`, `id`, `retry`, `comment` fields
- Auto headers: `X-Accel-Buffering: no` and `Cache-Control: no-cache` set on every SSE response
- Auto keepalive: `: ping\n\n` sent whenever the generator blocks longer than `_PING_INTERVAL` seconds (default 15s, patchable to 5s)
- Pydantic integration: `ServerSentEvent(data=some_pydantic_model)` calls `model_dump_json()` automatically

```python
# Source: inspected D:\Balatro-Poker\clanker_poker\backend\.venv\Lib\site-packages\fastapi\sse.py
from fastapi.sse import EventSourceResponse, ServerSentEvent

@router.get("/api/stream", response_class=EventSourceResponse)
async def stream(request: Request) -> AsyncIterable[ServerSentEvent]:
    queue: asyncio.Queue = broker.subscribe()
    try:
        while True:
            if await request.is_disconnected():
                break
            game_state = await queue.get()
            yield ServerSentEvent(
                data=game_state.model_dump(by_alias=True),
                event="game_state",
                id=str(broker.next_id()),
            )
    finally:
        broker.unsubscribe(queue)
```

The `_PING_INTERVAL` is a module-level float read at call time by `fastapi.routing`. Patch it once at app startup:

```python
# In main.py before app creation, or in lifespan startup:
import fastapi.routing as _fastapi_routing
_fastapi_routing._PING_INTERVAL = 5.0   # 5s heartbeat per STREAM-03
```

**If using sse-starlette instead (per locked D-09):** the API is different — see Standard Stack section. Both approaches produce the same SSE wire format.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SSE endpoint + connection lifecycle | FastAPI (API tier) | — | HTTP streaming belongs in the API layer; SSE is just a streaming HTTP response |
| Game state fan-out to N clients | Broker (in-process, API tier) | — | asyncio.Queue per client; broker lives in the same process as the endpoint |
| Pub/sub message routing (cross-process) | Redis | — | Redis channel decouples game loop from SSE endpoint; enables multi-instance scale |
| Game loop continuous execution | Background task (API startup) | — | Runs in FastAPI lifespan; directly calls GameSession.run() which is engine-tier |
| State snapshot for late joiners | Redis (string key) | — | Redis SET/GET with TTL; snapshot updated by publisher after each hand |
| SSE wire encoding (id/event/data/ping) | fastapi.sse or sse-starlette | — | Library owns wire format; no custom encoding needed |
| Heartbeat (`: ping` comment) | fastapi.sse (automatic) | sse-starlette (param) | Both libraries handle this; not a hand-rolled task |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi.sse | built into 0.136.1 | SSE wire format, keepalive, headers | Already installed; no extra dep; auto handles all STREAM-03 requirements |
| redis (redis-py) | 7.4.0 (latest) | Redis client with asyncio support | redis.asyncio is the locked choice (D-01); 7.x is current stable |
| sse-starlette | 3.4.1 (latest) | Alternative SSE library (locked D-09) | Only needed if native FastAPI SSE is rejected by user |
| anyio | 4.12.1 (already installed) | Async primitives used by FastAPI internally | Already present as FastAPI dependency |

[VERIFIED: `pip index versions` for redis and sse-starlette; `uv run pip show anyio` for anyio version; FastAPI 0.136.1 already in backend/.venv]

### Version Verification

```bash
# Verified registry versions (2026-05-05):
# sse-starlette: 3.4.1  (pip index versions sse-starlette)
# redis:         7.4.0  (pip index versions redis)
# anyio:         4.12.1 (uv run pip show anyio in backend env)
# fastapi:       0.136.1 (uv run python -c "import fastapi; print(fastapi.__version__)")
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| fastapi.sse (built-in) | sse-starlette 3.4.1 | sse-starlette adds 1 extra dep; marginally more configuration flexibility; D-09 locked this choice |
| asyncio.Queue fan-out | anyio MemoryObjectStream | anyio streams are what FastAPI uses internally; either works; asyncio.Queue is simpler and the locked choice |
| Redis SET for snapshot | Redis HSET | SET/GET with string value is simpler; snapshot is a single JSON blob, not a hash |

### Installation

```bash
# From backend/ directory:
uv add redis
# sse-starlette only if using instead of fastapi.sse:
# uv add sse-starlette
```

---

## Architecture Patterns

### System Architecture Diagram

```
[GameSession.run()]
    |
    | calls run_hand() at each phase transition
    v
[publisher.publish(game_state)]
    |
    | redis.asyncio PUBLISH "game:state" <json>
    v
[Redis Pub/Sub channel "game:state"]
    |
    | broker subscriber task: await pubsub.get_message(...)
    v
[broker.py: _subscriber_task (background)]
    |
    | iterates _queues list, puts message in each asyncio.Queue
    v
[N x asyncio.Queue (one per connected client)]
    |
    | client SSE generator: queue.get()
    v
[GET /api/stream SSE endpoint]
    |
    | yields ServerSentEvent(data=..., event="game_state", id=...)
    v
[Browser EventSource]

--- Late joiner path ---
[GET /api/stream (new connection)]
    |
    | redis.asyncio GET "game:state:last"
    v
[snapshot JSON → ServerSentEvent → client]
    |
    | then subscribe to queue for future events
    v
[same path as above]
```

### Recommended Project Structure

```
backend/app/
├── api/
│   ├── health.py          # existing
│   └── stream.py          # new: GET /api/stream endpoint
├── broadcast/
│   ├── __init__.py        # new: empty or re-exports
│   ├── broker.py          # new: Queue registry + Redis subscriber task
│   └── publisher.py       # new: publish GameState to Redis + write snapshot
├── engine/                # existing (Phase 2)
├── game_loop.py           # new: background asyncio task
├── config.py              # modified: add redis_url, hand_delay_seconds
└── main.py                # modified: lifespan startup + router registration
docker-compose.yml         # new: Redis service (repo root)
```

### Pattern 1: Redis Pub/Sub Subscriber + asyncio.Queue Fan-out (broker.py)

**What:** A single background task subscribes to the Redis channel, receives messages, and distributes them to all connected client queues.

**When to use:** Whenever one event source needs to feed N concurrent SSE connections.

```python
# Source: redis-py 7.4.0 asyncio examples + deepwiki.com/sysid/sse-starlette/4.3
import asyncio
import redis.asyncio as redis

class EventBroker:
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._message_id: int = 0

    def next_id(self) -> int:
        self._message_id += 1
        return self._message_id

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        async with self._lock:
            self._queues.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            self._queues.remove(q)

    async def broadcast(self, data: str) -> None:
        async with self._lock:
            queues_snapshot = list(self._queues)
        for q in queues_snapshot:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass  # slow client: drop event rather than block publisher

    async def run_subscriber(self, redis_client: redis.Redis, channel: str) -> None:
        """Background task: subscribe to Redis channel, fan-out to client queues."""
        async with redis_client.pubsub() as pubsub:
            await pubsub.subscribe(channel)
            try:
                while True:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                    if message is not None:
                        await self.broadcast(message["data"].decode("utf-8"))
            except asyncio.CancelledError:
                # Task cancelled on shutdown — clean exit
                await pubsub.unsubscribe(channel)
                raise
```

**Key details:**
- `maxsize=10` on queues prevents unbounded memory growth from slow clients; `put_nowait` + drop on `QueueFull` keeps the publisher non-blocking [ASSUMED — reasonable default; adjust based on observed behavior]
- Lock snapshot before iterating prevents race with subscribe/unsubscribe during broadcast
- `timeout=1.0` on `get_message` makes the loop cancellable (without timeout it blocks forever on shutdown)
- On `CancelledError`, unsubscribe before re-raising (ensures Redis channel cleanup)

### Pattern 2: Publisher (publisher.py)

**What:** Serialize `GameState` → publish to Redis channel + overwrite snapshot key.

```python
# Source: redis-py 7.4.0 docs (redis.io/docs/latest/develop/clients/redis-py/)
import redis.asyncio as redis
from app.engine.models import GameState

CHANNEL = "game:state"
SNAPSHOT_KEY = "game:state:last"
SNAPSHOT_TTL = 3600  # 1 hour; prevents stale snapshot persisting across server restarts

async def publish(redis_client: redis.Redis, state: GameState) -> None:
    payload = state.model_dump_json(by_alias=True)  # camelCase JSON for browser
    # Write snapshot first (late joiners read this)
    await redis_client.set(SNAPSHOT_KEY, payload, ex=SNAPSHOT_TTL)
    # Then broadcast to all subscribers
    await redis_client.publish(CHANNEL, payload)
```

**Key details:**
- `model_dump_json(by_alias=True)` produces camelCase JSON matching `types.ts GameState` — no intermediate dict needed [VERIFIED: models.py has `alias_generator=to_camel`]
- SET before PUBLISH ensures a late joiner arriving between SET and PUBLISH still gets the snapshot first event (no partial state window)
- `ex=SNAPSHOT_TTL` prevents the snapshot key from persisting across long server restarts

### Pattern 3: SSE Endpoint (api/stream.py)

```python
# Source: verified fastapi.sse source code (fastapi 0.136.1)
from collections.abc import AsyncIterable
from fastapi import APIRouter, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from app.broadcast.broker import EventBroker  # module-level singleton

router = APIRouter()

# broker is a module-level singleton, passed in or imported
def get_broker() -> EventBroker:
    from app.main import broker  # or use app.state.broker
    return broker

@router.get("/api/stream", response_class=EventSourceResponse)
async def sse_stream(request: Request) -> AsyncIterable[ServerSentEvent]:
    broker = get_broker()
    
    # Late-joiner snapshot
    from app.main import redis_client, SNAPSHOT_KEY
    snapshot = await redis_client.get(SNAPSHOT_KEY)
    if snapshot is not None:
        yield ServerSentEvent(
            raw_data=snapshot.decode("utf-8"),
            event="game_state",
            id=str(broker.next_id()),
        )
    
    # Subscribe to live events
    queue = await broker.subscribe()
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield ServerSentEvent(
                    raw_data=data,
                    event="game_state",
                    id=str(broker.next_id()),
                )
            except asyncio.TimeoutError:
                continue  # loop back to check is_disconnected
    finally:
        await broker.unsubscribe(queue)
```

**Note on `raw_data` vs `data`:** Use `raw_data` when the payload is already serialized JSON (string from Redis). Use `data=pydantic_model` when passing a Pydantic object directly (FastAPI calls `model_dump_json()` for you).

### Pattern 4: Lifespan (main.py)

```python
# Source: verified existing main.py + FastAPI docs pattern
from contextlib import asynccontextmanager
import redis.asyncio as redis_asyncio
import asyncio
import fastapi.routing as _fastapi_routing

from app.broadcast.broker import EventBroker
from app.game_loop import run_game_loop
from app.config import get_settings

SNAPSHOT_KEY = "game:state:last"
broker: EventBroker | None = None
redis_client: redis_asyncio.Redis | None = None
_loop_task: asyncio.Task | None = None
_subscriber_task: asyncio.Task | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global broker, redis_client, _loop_task, _subscriber_task
    settings = get_settings()
    
    # Patch ping interval to 5s (STREAM-03 requires 5s heartbeat)
    _fastapi_routing._PING_INTERVAL = 5.0
    
    # Redis connection
    redis_client = redis_asyncio.from_url(settings.redis_url, decode_responses=False)
    
    # Fan-out broker
    broker = EventBroker()
    
    # Background: Redis subscriber → fan-out to client queues
    _subscriber_task = asyncio.create_task(
        broker.run_subscriber(redis_client, channel="game:state")
    )
    
    # Background: continuous game loop
    _loop_task = asyncio.create_task(run_game_loop(redis_client, settings))
    
    yield
    
    # Shutdown: cancel tasks (order matters — cancel game loop first)
    _loop_task.cancel()
    _subscriber_task.cancel()
    try:
        await _loop_task
    except (asyncio.CancelledError, Exception):
        pass
    try:
        await _subscriber_task
    except (asyncio.CancelledError, Exception):
        pass
    await redis_client.aclose()
```

### Pattern 5: Background Game Loop (game_loop.py)

```python
# Source: CONTEXT.md D-10, D-11 + standard asyncio task exception pattern
import asyncio
import redis.asyncio as redis_asyncio
from app.engine.session import GameSession
from app.broadcast.publisher import publish
from app.config import Settings

async def run_game_loop(redis_client: redis_asyncio.Redis, settings: Settings) -> None:
    """Continuous game loop. Runs until cancelled."""
    while True:
        try:
            session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
            # Phase 3: broadcast each phase-transition state
            # We need to modify GameSession.run() to yield/callback on transitions,
            # OR wrap run_hand() directly in game_loop — see Open Questions
            hand_states = await session.run(n_hands=10)  # one session = 10 hands
            await asyncio.sleep(settings.hand_delay_seconds)
        except asyncio.CancelledError:
            raise  # propagate shutdown signal
        except Exception as e:
            # Log and continue — prevents silent crash of the game loop
            import logging
            logging.getLogger(__name__).error("Game loop error: %s", e, exc_info=True)
            await asyncio.sleep(settings.hand_delay_seconds)
```

**Critical architectural gap:** `GameSession.run()` returns `list[GameState]` at the end — it does not yield states during execution. Phase 3 requires broadcasting at each phase transition (D-06: deal, flop, turn, river, showdown). The game loop needs either:
1. A callback/hook injected into `GameSession.run()` or `run_hand()` — receives state at each transition
2. A generator variant of `GameSession.run()` that yields states
3. The game loop directly calling `run_hand()` in a loop and broadcasting after each hand's final state (simplest — but only broadcasts once per hand, not per phase within the hand)

The CONTEXT.md says "Broadcasts fire on phase transitions only" (D-06). `GameSession.run()` currently returns only the **final** state per hand. Broadcasting the final state per hand covers the showdown event. For deal/flop/turn/river states to be broadcast, `run_hand()` in `game.py` would need to surface intermediate states. **This is an open design question the planner must resolve** — see Open Questions.

### Anti-Patterns to Avoid

- **Blocking the publisher with slow client queues:** If any client's queue is full, `await queue.put(data)` will block the broadcaster and delay all other clients. Use `put_nowait()` with a drop-on-full policy instead.
- **Sharing one `asyncio.Queue` across all clients:** Every client drains the same queue — they compete and some will miss events. Each client needs its own queue.
- **Using `pubsub.listen()` instead of `get_message(timeout=...):`** `listen()` is a blocking async generator that cannot be cancelled cleanly. `get_message(timeout=1.0)` allows the loop to check `CancelledError` and exit.
- **Forgetting `unsubscribe` in the SSE generator's `finally:` block:** Client disconnect leaves an orphaned queue in the registry, leaking memory permanently.
- **Storing `asyncio.Queue` objects created outside the event loop:** Queues must be created inside an async context. Avoid module-level `asyncio.Queue()` instantiation.
- **Using `asyncio.get_event_loop_policy()` patterns:** Deprecated in Python 3.14; the project uses Python 3.13.13 via `uv` so this is safe for now, but avoid new usage.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE wire format (id/event/data fields, `\n\n` terminator) | Custom HTTP streaming response | `fastapi.sse.EventSourceResponse` + `ServerSentEvent` | Correct encoding, comments, multiline data escaping |
| Heartbeat / keepalive | Manual `asyncio.sleep(5)` + send comment | `fastapi.routing._PING_INTERVAL = 5.0` | Built-in; runs concurrently with generator; correct timing even when generator is slow |
| `X-Accel-Buffering` header | `response.headers["X-Accel-Buffering"] = "no"` | Let FastAPI native SSE set it automatically | FastAPI 0.136.1 does this for every EventSourceResponse |
| JSON serialization of Pydantic for SSE | `json.dumps(state.dict())` | `state.model_dump_json(by_alias=True)` | Preserves camelCase aliases; no intermediate dict; faster |
| Redis connection management | Manual socket pool | `redis.asyncio.from_url()` + `aclose()` | Connection pooling, retry, decode settings handled |

**Key insight:** FastAPI 0.136.1 makes sse-starlette unnecessary. The only reason to use sse-starlette is if D-09 is kept locked after user review.

---

## Common Pitfalls

### Pitfall 1: `GameSession.run()` Only Returns Final State Per Hand

**What goes wrong:** The game loop calls `session.run(n_hands=10)` and only gets 10 final (showdown) states back. No deal/flop/turn/river intermediate states are available for broadcast.

**Why it happens:** `game.py:run_hand()` runs the entire hand and returns one final `GameState`. It was designed for Phase 2 (console verification), not real-time streaming.

**How to avoid:** The planner must choose one of three approaches:
1. Add a `broadcast_fn` callback parameter to `run_hand()` that is called at each phase transition — cleanest, preserves existing call signatures
2. Change `run_hand()` to be an async generator yielding states at transitions — requires refactoring session.py
3. Accept that Phase 3 only broadcasts per-hand (showdown) state — simplest, but does not match D-06 intent of "phase transitions"

**Warning signs:** If the game loop only calls `publish()` once per 10-hand session, D-06 is not satisfied.

### Pitfall 2: Redis Pub/Sub Task Cancellation Raises ConnectionError

**What goes wrong:** Cancelling the `run_subscriber` task causes a `ConnectionError` from redis-py instead of `CancelledError`. The exception propagates as "Task exception was never retrieved."

**Why it happens:** A known regression in redis-py 4.5.4+ where internal socket closure raises `ConnectionError` during task cancellation. Partially present in redis-py 7.x.

**How to avoid:** In the `run_subscriber` task, catch both `asyncio.CancelledError` AND `redis.exceptions.ConnectionError` during shutdown. The lifespan shutdown handler should `try/except (asyncio.CancelledError, Exception)` when awaiting cancelled tasks.

**Warning signs:** Ugly stack traces in uvicorn output on Ctrl+C; "Task exception was never retrieved" in logs.

### Pitfall 3: `decode_responses=True` Breaks Binary Message Handling

**What goes wrong:** If `redis.asyncio.from_url(url, decode_responses=True)` is used, `pubsub.get_message()` returns `str` data. However, if publish sends bytes, the subscriber may receive garbled data.

**How to avoid:** Use `decode_responses=False` (default) and decode manually: `message["data"].decode("utf-8")`. This is explicit and safe.

**Warning signs:** `AttributeError: 'str' object has no attribute 'decode'` in the subscriber; or `TypeError` from JSON parsing.

### Pitfall 4: Snapshot Read Race — Client Misses First Live Event

**What goes wrong:** Client connects, reads snapshot (last state), then subscribes to the queue. Between snapshot read and queue subscription, a new event is published. Client misses that event until the next publish.

**Why it happens:** There is no atomic "read snapshot + subscribe" operation.

**How to avoid:** Subscribe to the queue **first**, then read the snapshot and send it. Any events arriving between subscribe and snapshot-send will be in the queue waiting. The snapshot send and queue drain will be slightly out of order in theory, but in practice the broker fan-out is synchronous within the asyncio event loop.

**Warning signs:** Occasional missed events for clients that connect during an active hand.

### Pitfall 5: asyncio.Queue Created Outside Async Context

**What goes wrong:** `asyncio.Queue()` instantiated at module import time (before the event loop runs) may attach to the wrong event loop. In Python 3.10+ this raises a DeprecationWarning; in Python 3.12+ it raises RuntimeError.

**How to avoid:** Create queues only inside `async def` functions (e.g., inside `broker.subscribe()`).

**Warning signs:** `DeprecationWarning: There is no current event loop` on startup.

### Pitfall 6: Docker Desktop Not Running on Dev Machine

**What goes wrong:** `docker compose up -d redis` fails silently or with a daemon connection error.

**How to avoid:** Document the "start Docker Desktop first" step in the wave 0 plan. The machine has Docker Desktop installed but it was not running at research time.

**Warning signs:** `failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`.

---

## Code Examples

### 1. SSE Wire Format (verified)

```python
# Source: inspected fastapi.sse.format_sse_event in fastapi 0.136.1

# event: game_state
# id: 42
# data: {"phase":"flop","pot":120,...}
#
# (blank line terminates event)

from fastapi.sse import ServerSentEvent

yield ServerSentEvent(
    raw_data='{"phase":"flop","pot":120}',  # pre-serialized JSON from Redis
    event="game_state",
    id="42",
)
# Heartbeat (produced automatically by fastapi.routing every _PING_INTERVAL seconds):
# : ping
#
# (blank line)
```

### 2. Redis pub/sub message format

```python
# Source: redis-py 7.4.0 asyncio examples (redis.readthedocs.io)
# Message dict from pubsub.get_message():
{
    "type": "message",       # 'subscribe' for confirmation messages
    "pattern": None,
    "channel": b"game:state",  # bytes when decode_responses=False
    "data": b'{"phase":"flop","pot":120,...}',  # bytes
}
# Access: message["data"].decode("utf-8")
```

### 3. Redis snapshot SET/GET

```python
# Source: redis.io/docs/latest/commands/set/
# Write snapshot (publisher.py):
await redis_client.set("game:state:last", payload_json_str, ex=3600)

# Read snapshot (stream.py on connect):
snapshot = await redis_client.get("game:state:last")  # returns bytes or None
if snapshot is not None:
    yield ServerSentEvent(raw_data=snapshot.decode("utf-8"), event="game_state", id=str(broker.next_id()))
```

### 4. docker-compose.yml

```yaml
# Source: docs.docker.com/compose + redis official image [CITED: hub.docker.com/_/redis]
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

### 5. config.py additions

```python
# Source: existing config.py pattern (pydantic-settings BaseSettings)
class Settings(BaseSettings):
    # ... existing fields ...
    redis_url: str = "redis://localhost:6379"
    hand_delay_seconds: int = 3  # D-11

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

### 6. Testing SSE with httpx-sse

```python
# Source: pypi.org/project/httpx-sse/ + pytest-asyncio 1.3.0 patterns
# pyproject.toml already has asyncio_mode = "strict"
import pytest
import httpx
from httpx_sse import aconnect_sse
from fastapi.testclient import TestClient

@pytest.mark.asyncio
async def test_sse_stream_returns_snapshot():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        async with aconnect_sse(client, "GET", "/api/stream") as event_source:
            events = []
            async for sse in event_source.aiter_sse():
                events.append(sse)
                if len(events) >= 1:
                    break
    assert events[0].event == "game_state"
    import json
    data = json.loads(events[0].data)
    assert "phase" in data
```

---

## Runtime State Inventory

> Greenfield phase adding new infrastructure. No rename/refactor involved.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — Redis does not exist yet; will be created fresh | None |
| Live service config | None — no existing Redis, no existing pub/sub channels | None |
| OS-registered state | None | None |
| Secrets/env vars | `REDIS_URL` is new — needs adding to `.env.example` and `config.py` | Code edit only |
| Build artifacts | None | None |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Desktop | `docker compose up -d redis` | Installed, not running | 29.1.3 | Start Docker Desktop before testing |
| Docker Compose | Redis service | Available | v5.0.1 | — |
| Redis (via Docker) | Publisher, broker, snapshot | Not running (Docker offline) | 7-alpine (to be pulled) | Run `redis-server` natively if Docker fails |
| Python 3.13.13 (uv) | Backend | Available | 3.13.13 | — |
| FastAPI | SSE endpoint | Available | 0.136.1 | — |
| redis-py | Pub/sub, snapshot | Not installed in backend venv yet | 7.4.0 (to install) | — |
| httpx-sse | SSE tests | Not installed in backend venv yet | 0.4.3 (to install) | Manual curl test only |
| anyio | FastAPI SSE internals | Available | 4.12.1 | — |

**Missing dependencies with no fallback:**
- redis (redis-py) — must install: `uv add redis`

**Missing dependencies with fallback:**
- httpx-sse — for testing only; not needed for production. Fallback: test with raw curl SSE.
- Docker Desktop running — start it manually; or install Redis natively (`redis-server`)

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| aioredis (separate package) | `redis.asyncio` built into redis-py 4+ | redis-py 4.2.0 (2022) | No separate install needed; D-01 locks this |
| Manual SSE encoding (custom StreamingResponse) | `fastapi.sse.EventSourceResponse` | FastAPI 0.135.0 (2025) | No sse-starlette needed; auto headers + ping |
| sse-starlette for FastAPI SSE | `fastapi.sse` (native) | FastAPI 0.135.0 | D-09 locks sse-starlette but native is available |
| `asyncio.get_event_loop()` (deprecated) | `asyncio.get_running_loop()` or just use `asyncio.create_task()` | Python 3.10+ | Avoid deprecated pattern |

**Deprecated/outdated:**
- `aioredis`: replaced by `redis.asyncio`; do not install
- `SETEX` / `GETSET` Redis commands: deprecated in Redis 2.6.12; use `SET key value EX seconds` instead
- `asyncio.get_event_loop_policy()`: deprecated Python 3.14; avoid new usage

---

## Open Questions (RESOLVED)

1. **How does the game loop broadcast per-phase-transition states?**
   - What we know: `GameSession.run()` returns final `GameState` per hand. D-06 says broadcast fires on "phase transitions: deal, flop, turn, river, showdown."
   - What's unclear: `run_hand()` in `game.py` does not yield intermediate states. To broadcast per-transition, it must be modified.
   - Recommendation: Add a `broadcast_fn: Optional[Callable[[GameState], Awaitable[None]]] = None` parameter to `run_hand()`. Call it after each betting round completes and at showdown. This is the cleanest extension — zero refactor, new optional parameter, Phase 3 passes it in, Phase 2 tests are unaffected.
   - RESOLVED: Add `broadcast_fn: Optional[Callable[[GameState], Awaitable[None]]] = None` parameter to `run_hand()` in game.py. Call it at 5 transition points (post-pre-flop-deal, post-flop, post-turn, post-river, post-showdown). See Plan 03-02.

2. **What happens when Redis is unavailable at startup?**
   - What we know: D-09 discretion area. The lifespan will try to create a Redis connection.
   - What's unclear: Should startup fail hard, or should the game loop run without broadcasting?
   - Recommendation: Fail hard — log a clear error and let uvicorn report startup failure. The system is non-functional without Redis; silent degradation would be confusing.
   - RESOLVED: Fail hard — the lifespan raises the exception from `redis_asyncio.from_url()` ping, uvicorn reports startup failure. Silent degradation would be confusing. See Plan 03-04 main.py acceptance criteria.

3. **Should the broker singleton live on `app.state` or as a module-level import?**
   - What we know: FastAPI's `app.state` is the idiomatic place for shared objects. Module-level singletons work but make testing harder (state bleeds between tests).
   - Recommendation: Use `app.state.broker` and `app.state.redis_client` — set in lifespan startup, accessed via dependency injection in endpoints. This allows test fixtures to inject a mock broker.
   - RESOLVED: Use `app.state.broker` and `app.state.redis_client` set in lifespan startup, accessed via FastAPI dependency injection in endpoints. Allows test fixtures to inject a mock broker. See Plans 03-03 and 03-04.

---

## Validation Architecture

> `nyquist_validation` is explicitly `false` in `.planning/config.json` — this section is omitted.

---

## Security Domain

> `security_enforcement` not set in config.json — treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | SSE is read-only, unauthenticated (v1 design) |
| V3 Session Management | No | No sessions; SSE connections are anonymous |
| V4 Access Control | No | All viewers see same state; no per-user ACL |
| V5 Input Validation | Yes | `REDIS_URL` from env — validate format; `HAND_DELAY_SECONDS` must be positive int |
| V6 Cryptography | No | No encryption in v1; VPS deployment; internal Redis |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Redis connection string injection | Tampering | pydantic-settings validates `redis_url` as `str`; no shell interpolation |
| Unbounded SSE connections (DoS) | DoS | asyncio.Queue maxsize limits per-client memory; consider max_connections limit in Phase 5 |
| Redis key naming collision | Tampering | Use prefixed keys (`game:state:last`) unique to this app; low risk for v1 single-instance |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | asyncio.Queue maxsize=10 is sufficient for slow clients without excessive dropped events | Architecture Patterns — broker.py | Clients may miss events during slow consumer periods; tune value empirically |
| A2 | Publishing snapshot before publish (SET before PUBLISH) eliminates the late-joiner race | Common Pitfalls — Pitfall 4 | There is still a brief window; in practice the event loop serializes these ops |
| A3 | `fastapi.routing._PING_INTERVAL = 5.0` set at startup persists for the process lifetime | Patterns — lifespan | If FastAPI re-imports routing module (unlikely), the patch would be lost |
| A4 | SNAPSHOT_TTL of 3600s is appropriate | Code Examples — publisher.py | Very stale snapshot shown to late joiners after 1h; acceptable for v1 |

---

## Sources

### Primary (HIGH confidence)

- FastAPI 0.136.1 installed source — `backend/.venv/Lib/site-packages/fastapi/sse.py` and `fastapi/routing.py` — confirmed via `uv run python -c "import inspect; ..."` 
- redis-py 7.4.0 asyncio examples — `redis.readthedocs.io/en/stable/examples/asyncio_examples.html` — pub/sub pattern, message format, cleanup
- `pip index versions` — sse-starlette (3.4.1), redis (7.4.0) verified as current
- `uv run pip show anyio` — anyio 4.12.1 confirmed installed
- FastAPI SSE tutorial — `fastapi.tiangolo.com/tutorial/server-sent-events/` — EventSourceResponse API, ServerSentEvent fields, auto-ping behavior

### Secondary (MEDIUM confidence)

- deepwiki.com/sysid/sse-starlette/4.3 — asyncio.Queue fan-out broadcaster pattern, lock snapshot before broadcast
- redis.io/docs/latest/commands/set/ — SET with EX option (replaces deprecated SETEX)
- GitHub sysid/sse-starlette README — EventSourceResponse constructor, ping_message_factory, headers

### Tertiary (LOW confidence)

- GitHub redis/redis-py issues #2523, #2717 — pubsub task cancellation ConnectionError; workaround via catch-both-exceptions pattern
- deepwiki.com/sysid/sse-starlette — disconnect cleanup gap documented

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all versions verified against registry; fastapi.sse verified from installed source
- Architecture: HIGH — patterns derived from verified source code of installed libraries
- Pitfalls: MEDIUM-HIGH — pubsub cancellation issues verified via GitHub issues; queue patterns derived from docs

**Research date:** 2026-05-05
**Valid until:** 2026-06-05 (redis-py and sse-starlette move slowly; FastAPI 0.136.x SSE API stable)
