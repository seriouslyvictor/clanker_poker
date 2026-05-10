# Phase 3: SSE Broadcast - Pattern Map

**Mapped:** 2026-05-06
**Files analyzed:** 10 (7 new, 3 modified)
**Analogs found:** 9 / 10 (docker-compose.yml has no in-repo analog)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/api/stream.py` | route/controller | streaming (SSE) | `backend/app/api/health.py` | role-match |
| `backend/app/broadcast/__init__.py` | package init | n/a | any existing `__init__.py` | structural |
| `backend/app/broadcast/broker.py` | service | event-driven / pub-sub | `backend/app/engine/session.py` | partial (async service) |
| `backend/app/broadcast/publisher.py` | service | event-driven / pub-sub | `backend/app/engine/session.py` | partial (async service) |
| `backend/app/game_loop.py` | service | event-driven / batch | `backend/app/engine/session.py` | role-match (async background task) |
| `backend/app/config.py` | config | n/a | `backend/app/config.py` (self) | exact (modification) |
| `backend/app/main.py` | config/bootstrap | request-response | `backend/app/main.py` (self) | exact (modification) |
| `docker-compose.yml` | config | n/a | none | no analog |
| `backend/app/engine/game.py` | service | request-response | `backend/app/engine/game.py` (self) | exact (modification) |
| `backend/tests/test_sse.py` | test | request-response | `backend/tests/test_poker_math.py` | role-match |

---

## Pattern Assignments

### `backend/app/api/stream.py` (route, streaming/SSE)

**Analog:** `backend/app/api/health.py`

**Imports pattern** (health.py lines 1-3 — copy router boilerplate, expand for SSE):
```python
from fastapi import APIRouter

router = APIRouter()
```

**Core router pattern** (health.py lines 5-8 — the `router.get(...)` + `async def` skeleton):
```python
@router.get("/health")
async def health_check():
    return {"status": "ok"}
```

**SSE-specific additions from RESEARCH.md (verified against installed fastapi 0.136.1 source):**

The route handler must use `response_class=EventSourceResponse` and return `AsyncIterable[ServerSentEvent]`. The generator pattern follows RESEARCH.md Pattern 3 exactly:

```python
# Pattern from RESEARCH.md (verified against fastapi.sse source):
from collections.abc import AsyncIterable
from fastapi import APIRouter, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

router = APIRouter()

@router.get("/api/stream", response_class=EventSourceResponse)
async def sse_stream(request: Request) -> AsyncIterable[ServerSentEvent]:
    # 1. Subscribe to broker queue FIRST (avoids Pitfall 4 — late-joiner race)
    queue = await broker.subscribe()
    try:
        # 2. Send snapshot to late joiner before entering live loop
        snapshot = await redis_client.get(SNAPSHOT_KEY)
        if snapshot is not None:
            yield ServerSentEvent(
                raw_data=snapshot.decode("utf-8"),
                event="game_state",
                id=str(broker.next_id()),
            )
        # 3. Drain live events; check disconnect on each iteration
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
                continue
    finally:
        await broker.unsubscribe(queue)
```

**Note on `raw_data` vs `data`:** Use `raw_data` when the payload is already a JSON string (from Redis). `X-Accel-Buffering: no` and `Cache-Control: no-cache` are set automatically by `EventSourceResponse` — do not add them manually.

**Broker/Redis access:** Use `app.state.broker` and `app.state.redis_client` (set in lifespan) accessed via `request.app.state`. This keeps state off module globals and supports test injection.

---

### `backend/app/broadcast/__init__.py` (package init)

**Analog:** any project `__init__.py`

**Pattern:** Empty file or minimal re-export. No logic. The broadcast package exposes `EventBroker` from `broker.py` and `publish` from `publisher.py` if desired, but the planner may leave `__init__.py` empty since imports are explicit throughout the codebase.

```python
# Empty is fine. Optional re-exports:
from app.broadcast.broker import EventBroker
from app.broadcast.publisher import publish, CHANNEL, SNAPSHOT_KEY
```

---

### `backend/app/broadcast/broker.py` (service, event-driven / pub-sub)

**Analog:** `backend/app/engine/session.py` — closest async service with a class that manages shared state across multiple async calls.

**Class structure pattern** (session.py lines 41-61 — `__init__` with typed instance attrs):
```python
class GameSession:
    def __init__(
        self,
        n_players: int = 4,
        starting_chips: int = 1000,
        big_blind: int = 20,
    ) -> None:
        self.n_players = n_players
        ...
```

**Async method pattern** (session.py lines 63-109 — `async def run(...)` with typed args):
```python
async def run(
    self,
    n_hands: int = 10,
    decision_fn: Optional[DecisionFn] = None,
) -> list[GameState]:
    ...
    for hand_num in range(n_hands):
        ...
        try:
            ...
        except asyncio.CancelledError:
            raise  # propagate shutdown
```

**Full broker pattern** (from RESEARCH.md Pattern 1, verified redis-py 7.4.0 + asyncio):
```python
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
                pass  # slow client: drop rather than block

    async def run_subscriber(self, redis_client: redis.Redis, channel: str) -> None:
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
                await pubsub.unsubscribe(channel)
                raise
```

**Critical rules from RESEARCH.md:**
- `asyncio.Queue()` must be created inside `async def subscribe()` — never at module level (Pitfall 5)
- Lock snapshot before iterating `_queues` in `broadcast()` to avoid race with concurrent subscribe/unsubscribe
- `get_message(timeout=1.0)` not `pubsub.listen()` — allows clean `CancelledError` on shutdown
- Catch both `asyncio.CancelledError` AND `redis.exceptions.ConnectionError` during shutdown (Pitfall 2)
- `decode_responses=False` on Redis client; decode manually with `.decode("utf-8")` (Pitfall 3)

---

### `backend/app/broadcast/publisher.py` (service, event-driven)

**Analog:** `backend/app/engine/session.py` — module-level async function calling engine layer.

**Module-level constants pattern** (follows project style — constants at module top, no class needed):
```python
CHANNEL = "game:state"
SNAPSHOT_KEY = "game:state:last"
SNAPSHOT_TTL = 3600
```

**Full publisher pattern** (from RESEARCH.md Pattern 2, verified redis.io docs):
```python
import redis.asyncio as redis
from app.engine.models import GameState

CHANNEL = "game:state"
SNAPSHOT_KEY = "game:state:last"
SNAPSHOT_TTL = 3600  # 1 hour

async def publish(redis_client: redis.Redis, state: GameState) -> None:
    payload = state.model_dump_json(by_alias=True)  # camelCase JSON for browser
    # SET before PUBLISH: late joiners always see the snapshot (no race window)
    await redis_client.set(SNAPSHOT_KEY, payload, ex=SNAPSHOT_TTL)
    await redis_client.publish(CHANNEL, payload)
```

**Serialization rule:** `model_dump_json(by_alias=True)` — not `json.dumps(state.dict())`. The `alias_generator=to_camel` on `GameState` and `Player` (models.py) means `by_alias=True` produces the camelCase JSON shape matching `app/_components/types.ts`.

---

### `backend/app/game_loop.py` (service, batch / event-driven)

**Analog:** `backend/app/engine/session.py` — the closest in-repo async function with a continuous loop pattern.

**Module docstring pattern** (session.py lines 1-17):
```python
"""
session.py — multi-hand Texas Hold'em session with dealer rotation.
...
Phase 3: The game loop in session.run() is the seam where SSE broadcast hooks in.
"""
```

**Error handling pattern** (session.py lines 84-109 — `try/except asyncio.CancelledError: raise`):
```python
for hand_num in range(n_hands):
    ...
    try:
        final_state = await run_hand(...)
    except asyncio.CancelledError:
        raise
```

**Full game loop pattern** (from RESEARCH.md Pattern 5):
```python
import asyncio
import logging
import redis.asyncio as redis_asyncio
from app.engine.session import GameSession
from app.broadcast.publisher import publish
from app.config import Settings

logger = logging.getLogger(__name__)

async def run_game_loop(redis_client: redis_asyncio.Redis, settings: Settings) -> None:
    """Continuous game loop. Runs until cancelled by lifespan shutdown."""
    while True:
        try:
            session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
            await session.run(
                n_hands=10,
                # broadcast_fn passed here once game.py is modified (see game.py pattern below)
            )
            await asyncio.sleep(settings.hand_delay_seconds)
        except asyncio.CancelledError:
            raise  # propagate shutdown signal cleanly
        except Exception as e:
            logger.error("Game loop error: %s", e, exc_info=True)
            await asyncio.sleep(settings.hand_delay_seconds)
```

**Architectural note (open question from RESEARCH.md):** `GameSession.run()` returns `list[GameState]` — only final state per hand. D-06 requires broadcasting at each phase transition (deal, flop, turn, river, showdown). The planner must resolve this by adding a `broadcast_fn` callback to `run_hand()` in `game.py` (see `engine/game.py` pattern below). The game loop passes `publish` as that callback.

---

### `backend/app/config.py` (config, modification)

**Analog:** `backend/app/config.py` (self — adding fields to existing `Settings` class)

**Existing pattern to preserve** (config.py lines 1-27 — full file):
```python
import json
import pathlib
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_MODELS_CONFIG = pathlib.Path(__file__).parent.parent.parent / "models.config.json"

def _default_player_models() -> list[str]:
    with open(_MODELS_CONFIG) as f:
        return [m["litellmModel"] for m in json.load(f)]

class Settings(BaseSettings):
    player_models: list[str] = Field(default_factory=_default_player_models)
    llm_timeout_seconds: int = 8
    cors_origins: list[str] = ["http://localhost:3000"]
    # NEW FIELDS — add here:
    redis_url: str = "redis://localhost:6379"
    hand_delay_seconds: int = 3  # D-11 default

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Rules:**
- Field order: new fields after existing fields, before `model_config`
- `env_file=".env"` already set — `REDIS_URL` and `HAND_DELAY_SECONDS` are read from `.env` automatically via pydantic-settings naming convention (uppercase env var = lowercase field)
- Also add `REDIS_URL=redis://localhost:6379` to `backend/.env.example` following the existing comment+key pattern

---

### `backend/app/main.py` (bootstrap, modification)

**Analog:** `backend/app/main.py` (self — expanding the existing lifespan and adding router)

**Existing pattern to extend** (main.py lines 1-30 — full file):
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.health import router as health_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup — Phase 3 will add Redis connection here
    yield
    # shutdown — Phase 3 will add Redis cleanup here

app = FastAPI(lifespan=lifespan)
...
app.include_router(health_router)
```

**Expanded lifespan pattern** (from RESEARCH.md Pattern 4):
```python
from contextlib import asynccontextmanager
import asyncio
import fastapi.routing as _fastapi_routing
import redis.asyncio as redis_asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.health import router as health_router
from app.api.stream import router as stream_router
from app.broadcast.broker import EventBroker
from app.game_loop import run_game_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Patch SSE ping interval to 5s (STREAM-03)
    _fastapi_routing._PING_INTERVAL = 5.0

    # Redis connection (decode_responses=False — decode manually, Pitfall 3)
    app.state.redis_client = redis_asyncio.from_url(
        settings.redis_url, decode_responses=False
    )
    app.state.broker = EventBroker()

    # Background: Redis subscriber → fan-out
    app.state.subscriber_task = asyncio.create_task(
        app.state.broker.run_subscriber(app.state.redis_client, channel="game:state")
    )
    # Background: continuous game loop
    app.state.loop_task = asyncio.create_task(
        run_game_loop(app.state.redis_client, settings)
    )

    yield

    # Shutdown (cancel game loop first, then subscriber)
    app.state.loop_task.cancel()
    app.state.subscriber_task.cancel()
    for task in (app.state.loop_task, app.state.subscriber_task):
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    await app.state.redis_client.aclose()

app = FastAPI(lifespan=lifespan)
...
app.include_router(health_router)
app.include_router(stream_router)
```

**Key difference from RESEARCH.md Pattern 4:** Use `app.state.*` instead of module-level globals. This is cleaner for testing (Open Question 3 from RESEARCH.md). The stream endpoint accesses state via `request.app.state.broker` and `request.app.state.redis_client`.

---

### `docker-compose.yml` (config, new file)

**Analog:** None in repo. Pattern from RESEARCH.md Code Example 4 (verified against docker.io docs).

**Full file** (from RESEARCH.md):
```yaml
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

**Placement:** Repo root alongside `package.json` and `backend/` (D-02). FastAPI continues to run outside Docker via `uv run uvicorn backend.app.main:app`.

---

### `backend/app/engine/game.py` (service, modification)

**Analog:** `backend/app/engine/game.py` (self — adding `broadcast_fn` callback parameter to `run_hand()`)

**Existing `run_hand` signature** (game.py lines 260-265):
```python
async def run_hand(
    players: list[Player],
    dealer_seat: int,
    big_blind: int,
    decision_fn: DecisionFn,
) -> GameState:
```

**Modified signature — add optional callback:**
```python
from typing import Awaitable, Callable, Optional

BroadcastFn = Callable[[GameState], Awaitable[None]]

async def run_hand(
    players: list[Player],
    dealer_seat: int,
    big_blind: int,
    decision_fn: DecisionFn,
    broadcast_fn: Optional[BroadcastFn] = None,
) -> GameState:
```

**Call sites for `broadcast_fn` within `run_hand`** — after each phase transition line that sets `game_state.phase`, before the next betting round:

Phase transition points in game.py (by line reference):
- Line 327: `game_state = GameState(phase="pre-flop", ...)` — call `broadcast_fn` after initial state built (pre-flop deal)
- Line 352: `game_state.phase = "flop"` (line ~352) — call after setting phase and community cards
- Line 369: `game_state.phase = "turn"` — call after setting phase
- Line 386: `game_state.phase = "river"` — call after setting phase
- Line 400: `game_state.phase = "showdown"` — call after full showdown resolution

**Broadcast helper pattern** (inline, zero-overhead when `broadcast_fn` is `None`):
```python
async def _maybe_broadcast(state: GameState, fn: Optional[BroadcastFn]) -> None:
    if fn is not None:
        await fn(state)
```

**Existing tests** (`test_game_engine.py`, `test_session.py`) call `run_hand(...)` without `broadcast_fn` — the `Optional[BroadcastFn] = None` default means zero test refactor.

---

### `backend/tests/test_sse.py` (test, new)

**Analog:** `backend/tests/test_poker_math.py` — closest in-repo test structure (class-based, pytest, typed imports, docstring convention).

**Module docstring pattern** (test_poker_math.py lines 1-8):
```python
"""
Tests for backend/app/engine/poker_math.py

Covers POKER-03 (...) and POKER-04 (...).
"""
import pytest
from app.engine.poker_math import evaluate_hand, calculate_equity
```

**Test class pattern** (test_poker_math.py lines 13-29 — `class Test...: def test_...`):
```python
class TestEvaluateHand:
    def test_returns_none_preflop(self):
        ...
        assert result["hand_strength"] is None
```

**Async test pattern** — test_session.py uses bare `asyncio.run()` and no `@pytest.mark.asyncio`. Check `pyproject.toml` for `asyncio_mode`:
- RESEARCH.md states: `asyncio_mode = "strict"` is already set in `pyproject.toml`
- With `asyncio_mode = "strict"`, ALL async tests need `@pytest.mark.asyncio`. Synchronous tests do not need it.

**SSE test pattern** (from RESEARCH.md Code Example 6):
```python
"""
Tests for backend/app/api/stream.py

Covers STREAM-01 (identical state to all clients), STREAM-02 (late-joiner snapshot),
STREAM-03 (5s heartbeat, X-Accel-Buffering header).
"""
import asyncio
import json
import pytest
import httpx
from httpx_sse import aconnect_sse
from fastapi.testclient import TestClient

from app.main import app


class TestSSEEndpoint:
    @pytest.mark.asyncio
    async def test_snapshot_sent_on_connect(self):
        """STREAM-02: late joiner receives snapshot as first event."""
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
        data = json.loads(events[0].data)
        assert "phase" in data

    def test_no_buffering_header(self):
        """STREAM-03: X-Accel-Buffering: no header is present."""
        client = TestClient(app)
        with client.stream("GET", "/api/stream") as response:
            assert response.headers.get("x-accel-buffering") == "no"
```

**Test dependency:** `httpx-sse` must be installed: `uv add --dev httpx-sse`. Also requires `httpx` (already present as a FastAPI dev dependency).

---

## Shared Patterns

### Error Handling for `asyncio.CancelledError`
**Source:** `backend/app/engine/session.py` lines 84-109 + `backend/app/engine/game.py` lines 335-345
**Apply to:** `broker.py` (`run_subscriber`), `game_loop.py` (`run_game_loop`), `main.py` (lifespan shutdown)

Pattern: `except asyncio.CancelledError: raise` — always re-raise `CancelledError` so the task terminates cleanly. Never swallow it.

```python
except asyncio.CancelledError:
    raise  # propagate shutdown signal
```

### Logging Pattern
**Source:** Standard Python `logging` — no custom logger in project yet.
**Apply to:** `broker.py`, `game_loop.py`

```python
import logging
logger = logging.getLogger(__name__)
logger.error("Game loop error: %s", e, exc_info=True)
```

### Pydantic BaseSettings Field Pattern
**Source:** `backend/app/config.py` lines 16-22
**Apply to:** `config.py` modification (add `redis_url`, `hand_delay_seconds`)

```python
class Settings(BaseSettings):
    existing_field: type = default
    # new fields follow same pattern:
    redis_url: str = "redis://localhost:6379"
    hand_delay_seconds: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

### FastAPI Router Registration
**Source:** `backend/app/main.py` line 29 (`app.include_router(health_router)`)
**Apply to:** `main.py` modification (register `stream_router`)

```python
app.include_router(health_router)
app.include_router(stream_router)  # add this line
```

### Serialization Contract
**Source:** `backend/app/engine/models.py` lines 1-13 (docstring) + `GameState` class
**Apply to:** `publisher.py` (`publish` function), `stream.py` (snapshot send)

Rule: Always use `state.model_dump_json(by_alias=True)` (not `json.dumps(state.dict())`). The `alias_generator=to_camel` is set on `GameState` and `Player` models — `by_alias=True` is the only way to produce the camelCase JSON that `app/_components/types.ts` expects.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `docker-compose.yml` | config | n/a | No Docker Compose files exist in repo yet; use RESEARCH.md Code Example 4 |

---

## Critical Open Question (Must Resolve in Planning)

**File:** `backend/app/engine/game.py` + `backend/app/game_loop.py`

`GameSession.run()` returns `list[GameState]` (one per hand, final state only). D-06 requires broadcasting at each phase transition within a hand (pre-flop, flop, turn, river, showdown). The planner must choose:

1. **Recommended:** Add `broadcast_fn: Optional[BroadcastFn] = None` to `run_hand()` in `game.py`. Call it at each phase transition. Pass `lambda state: publish(redis_client, state)` from the game loop. Zero breakage of existing tests (default is `None`).
2. Change `run_hand()` to an async generator yielding states — requires session.py refactor.
3. Accept only per-hand (showdown) broadcast — does not satisfy D-06.

The pattern assignment above (game.py section) implements Option 1.

---

## Metadata

**Analog search scope:** `backend/app/api/`, `backend/app/engine/`, `backend/app/`, `backend/tests/`
**Files read:** 9 source files (health.py, main.py, config.py, session.py, game.py, models.py, test_poker_math.py, test_session.py, .env.example)
**Pattern extraction date:** 2026-05-06
