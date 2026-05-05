# Phase 3: SSE Broadcast — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-05
**Phase:** 03-sse-broadcast
**Areas discussed:** Redis vs in-memory, SSE event schema, Game loop trigger, SSE fan-out library

---

## Redis vs In-Memory

| Option | Description | Selected |
|--------|-------------|----------|
| Redis now | Wire aioredis/redis.asyncio in Phase 3; follows CLAUDE.md architecture; Redis stores late-joiner snapshot | ✓ |
| In-memory first | asyncio.Queue per client + shared last-state variable; no Redis dependency; refactor risk later | |

**User's choice:** Redis now
**Notes:** User added that this may also mean starting containers to make the VPS deploy transition easier.

---

## Container scope for Redis

| Option | Description | Selected |
|--------|-------------|----------|
| docker-compose for local dev | Redis service only in docker-compose; FastAPI still runs via uv run uvicorn | ✓ |
| Full app containerized | Dockerfile for FastAPI + docker-compose with Redis | |

**User's choice:** docker-compose for local dev (recommended)
**Notes:** Keep dev setup minimal — just get Redis available locally.

---

## SSE Event Data

| Option | Description | Selected |
|--------|-------------|----------|
| Full GameState every time | Complete serialized snapshot on every broadcast; clients replace state | ✓ |
| Delta / incremental | Only changed fields broadcast; clients merge; more complex | |

**User's choice:** Full GameState every time (recommended)

---

## SSE Event Types

| Option | Description | Selected |
|--------|-------------|----------|
| game_state + heartbeat comment | `event: game_state` for payload; `: ping` comment for heartbeat | ✓ |
| Multiple typed events | Named events per action type (phase_change, player_action, showdown) | |

**User's choice:** game_state + heartbeat (recommended)

---

## Broadcast Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Phase transitions only | Broadcast after deal, flop, turn, river, showdown (~5 events/hand) | ✓ |
| Every player action | Broadcast after each fold/call/raise/check (~20+ events/hand) | |

**User's choice:** Phase transitions only (recommended)

---

## Game Loop Trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-loop on server start | Background asyncio task; runs continuously; configurable delay between hands | ✓ |
| REST endpoint placeholder | POST /api/game/start triggers one session; requires manual call per test | |

**User's choice:** Auto-loop on server start (recommended)

---

## Delay Between Hands

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable delay | HAND_DELAY_SECONDS env var, default 3s | ✓ |
| Immediate / no delay | Next hand starts right after showdown | |

**User's choice:** Configurable delay (recommended)

---

## SSE Fan-out Library

| Option | Description | Selected |
|--------|-------------|----------|
| sse-starlette | Established FastAPI SSE library; handles wire format; per-client asyncio.Queue broker on top | ✓ |
| Raw StreamingResponse | Custom generator with manual SSE formatting; more boilerplate; no added benefit | |

**User's choice:** sse-starlette (recommended)

---

## SSE Endpoint Path

| Option | Description | Selected |
|--------|-------------|----------|
| GET /api/stream | Short, convention-friendly, consistent with /api/ prefix | ✓ |
| GET /api/events | Slightly more descriptive | |

**User's choice:** GET /api/stream (recommended)

---

## Redis Client Library

| Option | Description | Selected |
|--------|-------------|----------|
| redis.asyncio | Built into redis-py 4+; modern, async-native, actively maintained | ✓ |
| aioredis | Older standalone client; merged into redis-py 4+ in 2022; outdated | |

**User's choice:** redis.asyncio (recommended)

---

## Claude's Discretion

- Redis channel name for game events
- Redis connection URL config field name
- Redis pub/sub retry behavior on connection loss
- Heartbeat task implementation detail
- Error handling for Redis unavailability at startup

## Deferred Ideas

- Full app containerization (Dockerfile for FastAPI) — deployment phase
- Viewer-triggered game start — Phase 6
- Viewer presence / demand-gated loop — Phase 6
- Per-player LLM reasoning stream — Phase 4
- Client auto-reconnect (STREAM-04) — Phase 5
