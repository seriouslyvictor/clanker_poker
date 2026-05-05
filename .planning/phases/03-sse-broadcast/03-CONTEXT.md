# Phase 3: SSE Broadcast — Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the Phase 2 game engine into a real-time SSE broadcast pipeline. All connected browser clients see identical game state pushed from FastAPI; late joiners receive a full snapshot immediately; connections survive proxy buffering and network blips via heartbeat and message IDs.

This phase still uses mock decisions — LLMs are Phase 4. The broadcast layer is the deliverable, not AI behavior.

</domain>

<decisions>
## Implementation Decisions

### Redis
- **D-01:** Use Redis Pub/Sub for fan-out — `redis.asyncio` (built into redis-py 4+, modern async-native). No aioredis.
- **D-02:** `docker-compose.yml` added with a Redis service for local development. FastAPI still runs outside Docker via `uv run uvicorn backend.app.main:app`. Keeps dev setup lightweight while making the VPS transition easier.
- **D-03:** Late-joiner snapshot stored in Redis as the last serialized `GameState`. On connect, the SSE handler reads from Redis and sends snapshot as the first event before subscribing to new events.

### SSE Event Schema
- **D-04:** Each broadcast event carries a **full `GameState` snapshot** — no delta encoding. Clients replace state on every event. Payload is small enough that full snapshots are always correct and simple to handle.
- **D-05:** Two event types:
  - `event: game_state` — carries the full camelCase JSON payload (`game_state.model_dump(by_alias=True)`)
  - Heartbeat: SSE comment line (`: ping`) every 5 seconds — no `event:` field needed per spec
- **D-06:** Broadcasts fire on **phase transitions only**: deal (pre-flop), flop, turn, river, showdown. Individual player actions within a street are NOT broadcast in Phase 3. Phase 4 LLM reasoning will have its own event stream.

### Message IDs
- **D-07:** Each `game_state` event includes a monotonically increasing integer `id:` field. Counter is in-memory (per server process). Phase 5 client uses IDs to detect missed events on reconnect.

### SSE Endpoint
- **D-08:** `GET /api/stream` — single endpoint all clients subscribe to. Consistent with existing `/api/` prefix.

### Fan-out Mechanism
- **D-09:** `sse-starlette` library for SSE wire format + per-client `asyncio.Queue` as the local broker. Flow: game loop publishes to Redis pub/sub → a subscriber asyncio task receives and enqueues into each connected client's queue → client SSE generator drains the queue. `X-Accel-Buffering: no` header set on the response.

### Game Loop (Phase 3 placeholder)
- **D-10:** FastAPI lifespan creates a background asyncio task that runs `GameSession.run()` in a continuous loop. When a hand completes, waits `HAND_DELAY_SECONDS` (env var, default 3s) then starts the next hand. This is the placeholder until Phase 6 adds viewer-triggered start.
- **D-11:** `HAND_DELAY_SECONDS` added to `Settings` in `config.py` with default 3.

### Module Layout
- **D-12 (Claude's Discretion):** New files under `backend/app/`:
  ```
  backend/app/
  ├── api/
  │   ├── health.py      ← existing
  │   └── stream.py      ← new: GET /api/stream SSE endpoint
  ├── broadcast/
  │   ├── __init__.py
  │   ├── broker.py      ← asyncio.Queue fan-out broker + Redis subscriber
  │   └── publisher.py   ← publish GameState to Redis pub/sub
  └── game_loop.py       ← background asyncio task (lifespan startup)
  ```

### Claude's Discretion
- Redis channel name for game events (e.g., `game:state`)
- Exact Redis connection URL config field name
- Number of Redis pub/sub retry attempts on connection loss
- Heartbeat task implementation (separate asyncio task vs inline generator sleep)
- Error handling for Redis unavailability at startup

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 3 Requirements
- `.planning/REQUIREMENTS.md` — STREAM-01 (SSE endpoint, all clients identical state), STREAM-02 (late-joiner snapshot), STREAM-03 (5s heartbeat + X-Accel-Buffering header)
- `.planning/ROADMAP.md` — Phase 3 success criteria (4 criteria, all must be TRUE)

### Frontend Type Contract
- `app/_components/types.ts` — `GameState`, `Player`, `Card` TypeScript interfaces. SSE payload MUST serialize to match these shapes. `game_state.model_dump(by_alias=True)` in Python produces camelCase JSON that matches.

### Existing Engine (Phase 2 output)
- `backend/app/engine/session.py` — `GameSession.run(n_hands, decision_fn)` — the loop to broadcast from
- `backend/app/engine/models.py` — `GameState`, `Player`, `Card` Pydantic models with camelCase alias generator
- `backend/app/engine/game.py` — `run_hand(...)` — produces final `GameState` per hand

### Phase 1 & 2 Context
- `.planning/phases/01-backend-foundation/01-CONTEXT.md` — D-01 to D-06 (directory layout, uv toolchain)
- `.planning/phases/02-game-state-machine/02-CONTEXT.md` — D-01 (Pydantic state model), D-02 (async decision seam), D-06 (module layout)

### Architecture Reference
- `.planning/research/ARCHITECTURE.md` — Component map; Phase 3 wires game engine → Redis → SSE

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/engine/models.py` — `GameState.model_dump(by_alias=True)` produces SSE-ready camelCase JSON with no extra serialization work
- `backend/app/engine/session.py` — `GameSession.run(n_hands, decision_fn)` is the game loop; the background task wraps this in a while-True with delay between runs
- `backend/app/main.py` — lifespan context manager already stubbed with comments noting "Phase 3 will add Redis connection here" — this is the right place for redis.asyncio connection setup and background task creation
- `backend/app/config.py` — `Settings` (pydantic-settings `BaseSettings`) ready to receive `redis_url: str` and `hand_delay_seconds: int` fields

### Established Patterns
- Pydantic `BaseSettings` with `@lru_cache` in `config.py` — new env vars follow this pattern
- `uv run pytest` from `backend/` — all new tests follow this convention
- FastAPI router pattern in `api/health.py` — new `api/stream.py` follows same router structure
- Async FastAPI lifespan (already set up in `main.py`)

### Integration Points
- `main.py` lifespan: startup creates Redis connection + starts background game loop task; shutdown cancels task + closes Redis
- `api/stream.py` router included in `main.py` alongside health router
- `game_loop.py` imports `GameSession` from `session.py` and `publisher.py` from `broadcast/`
- Phase 4: game loop passes LLM decision function to `GameSession.run()` — no refactor needed (async seam already in place)

</code_context>

<specifics>
## Specific Requirements

- SSE heartbeat: `: ping` comment line every 5s (not `event: heartbeat` — comment form is per-spec and simpler)
- `X-Accel-Buffering: no` header on `GET /api/stream` response
- Message ID: monotonically increasing integer in `id:` field on every `game_state` event
- Late-joiner snapshot: read last GameState JSON from Redis on connect, send as first event before subscribing
- `docker-compose.yml` in repo root alongside `package.json` and `backend/`
- `HAND_DELAY_SECONDS` default: 3 seconds
- Redis URL: `REDIS_URL` env var (e.g., `redis://localhost:6379`)

</specifics>

<deferred>
## Deferred Ideas

- Full app containerization (Dockerfile for FastAPI) — Phase 3 adds docker-compose for Redis only; full containerization deferred to deployment phase
- Viewer-triggered game start (`POST /api/game/start`) — Phase 6
- Viewer presence tracking / demand-gated loop — Phase 6
- Per-player LLM reasoning event stream — Phase 4 (separate `event: reasoning` events for streaming tokens)
- STREAM-04 (client auto-reconnect on disconnect) — Phase 5 (lives in Next.js frontend)
- Redis persistence / AOF for crash recovery — v2

</deferred>

---

*Phase: 03-sse-broadcast*
*Context gathered: 2026-05-05*
