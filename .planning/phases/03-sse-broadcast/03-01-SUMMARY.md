---
phase: 03-sse-broadcast
plan: 01
subsystem: infrastructure
tags:
  - redis
  - configuration
  - docker-compose
dependency_graph:
  requires: []
  provides:
    - Redis infrastructure for local dev
    - Settings.redis_url and Settings.hand_delay_seconds
    - .env.example documented with REDIS_URL and HAND_DELAY_SECONDS
  affects:
    - Phase 03-02 (game loop will use hand_delay_seconds)
    - Phase 03-03 (SSE endpoint will use redis_url)
    - Phase 03-04 (main.py lifespan will initialize Redis connection)
tech_stack:
  added:
    - redis-py 7.4.0 (redis.asyncio for async pub/sub)
  patterns:
    - Pydantic Settings with environment variable mapping
    - Docker Compose for local infrastructure
key_files:
  created:
    - docker-compose.yml
  modified:
    - backend/app/config.py
    - backend/.env.example
    - backend/pyproject.toml (auto-updated by uv add)
decisions:
  - Docker Desktop must be running before `docker compose up -d redis` (documented in docker-compose.yml comment)
  - FastAPI runs outside Docker for local development (lighter setup, easier for Phase 4 LLM integration testing)
  - redis_url defaults to "redis://localhost:6379" for local development
  - hand_delay_seconds defaults to 3 seconds (placeholder until Phase 6 viewer-triggered game start)
metrics:
  duration: 52 seconds (2026-05-06T14:59:26Z to 2026-05-06T15:00:18Z)
  completed_date: 2026-05-06
  tasks_completed: 2
  files_modified: 3
---

# Phase 03 Plan 01: Redis Infrastructure Setup Summary

**Redis and configuration layer for SSE broadcast pipeline**

## Objective

Set up the Redis infrastructure layer: Docker Compose for local development, config.py extended with redis_url and hand_delay_seconds, .env.example updated, and redis-py installed in the backend venv.

Purpose: All subsequent plans depend on Redis being available (docker-compose) and the Settings class knowing how to configure the connection (config.py). This is the zero-dependency foundation.

## Tasks Completed

### Task 1: Create docker-compose.yml and install redis-py

**Status:** ✓ PASSED

**Files created/modified:**
- Created: `docker-compose.yml` at repo root
- Modified: `backend/pyproject.toml` (via `uv add redis`)

**What was done:**
1. Created `docker-compose.yml` at repository root with Redis 7-alpine service
2. Service exposes port 6379 and includes a healthcheck using `redis-cli ping`
3. Added startup documentation comment: "Start Docker Desktop first, then: docker compose up -d redis"
4. Installed redis-py 7.4.0 into backend venv via `uv add redis`

**Verification:**
- ✓ docker-compose.yml exists and contains "redis:7-alpine"
- ✓ docker-compose.yml contains "6379:6379" port mapping
- ✓ docker-compose.yml contains "redis-cli ping" in healthcheck
- ✓ `uv run python -c "import redis; print(redis.__version__)"` outputs "7.4.0"
- ✓ backend/pyproject.toml contains "redis>=7.4.0" in dependencies

**Commit:** cdc0507

### Task 2: Extend Settings with redis_url and hand_delay_seconds; update .env.example

**Status:** ✓ PASSED

**Files created/modified:**
- Modified: `backend/app/config.py`
- Modified: `backend/.env.example`

**What was done:**
1. Added `redis_url: str = "redis://localhost:6379"` to Settings class
2. Added `hand_delay_seconds: int = 3` to Settings class (with D-11 comment)
3. Updated .env.example with new environment variables and documentation:
   - `REDIS_URL=redis://localhost:6379` (with comment explaining Redis requirement)
   - `HAND_DELAY_SECONDS=3` (with comment explaining game loop delay)
4. Fields inserted after `cors_origins` and before `model_config` (as specified in interfaces)

**Verification:**
- ✓ `uv run python -c "from app.config import get_settings; s = get_settings(); print(s.redis_url, s.hand_delay_seconds)"` outputs "redis://localhost:6379 3"
- ✓ backend/app/config.py contains `redis_url: str = "redis://localhost:6379"`
- ✓ backend/app/config.py contains `hand_delay_seconds: int = 3`
- ✓ backend/.env.example contains `REDIS_URL=redis://localhost:6379`
- ✓ backend/.env.example contains `HAND_DELAY_SECONDS=3`
- ✓ Existing Settings fields unchanged (player_models, llm_timeout_seconds, cors_origins)

**Commit:** e676427

## Success Criteria Achieved

- ✓ docker-compose.yml committed with Redis 7-alpine service
- ✓ redis-py 7.4.0 importable in backend venv
- ✓ Settings has redis_url (default "redis://localhost:6379") and hand_delay_seconds (default 3)
- ✓ .env.example documents both new env vars with comments
- ✓ Both tasks committed individually with atomic, well-documented commits

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — no placeholder values or stub patterns found.

## Threat Flags

No new threats introduced. Phase 1 threat model covers configuration validation (pydantic-settings validates redis_url as str; hand_delay_seconds as int). No shell interpolation or injection vectors present.

## Requirements Traceability

| Requirement | Status | Evidence |
|-------------|--------|----------|
| STREAM-01 | Foundation set | redis_url in Settings allows Phase 03-03 SSE endpoint to connect to Redis pub/sub |
| STREAM-03 | Foundation set | hand_delay_seconds in Settings allows Phase 03-02 game loop to implement 5s heartbeat via delay between hands |

## Next Steps

Phase 03-02: Modify GameSession to broadcast at phase transitions (requires callback/hook mechanism for deal/flop/turn/river/showdown events).

Phase 03-03: Create SSE endpoint (`api/stream.py`) and broker (`broadcast/broker.py, publisher.py`).

Phase 03-04: Create game loop background task (`game_loop.py`) and integrate with FastAPI lifespan (`main.py`).

---

**Executed by:** Claude Sonnet 4.6  
**Executed on:** 2026-05-06  
**Plan type:** execute (autonomous)  
**Wave:** 1
