---
phase: 03-sse-broadcast
reviewed: 2026-05-06T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - docker-compose.yml
  - backend/app/config.py
  - backend/app/engine/game.py
  - backend/app/engine/session.py
  - backend/app/broadcast/__init__.py
  - backend/app/broadcast/broker.py
  - backend/app/broadcast/publisher.py
  - backend/app/game_loop.py
  - backend/app/api/stream.py
  - backend/app/main.py
  - backend/tests/test_sse.py
findings:
  critical: 0
  warning: 4
  high: 0
  medium: 0
  low: 0
  info: 4
  total: 8
status: issues_found
---

# Phase 03: Code Review Report — SSE Broadcast

**Reviewed:** 2026-05-06
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

The SSE broadcast pipeline is structurally sound. The critical design decisions are correct:
subscribe-before-snapshot ordering eliminates the late-joiner race window (Pitfall 4), `decode_responses=False` with manual decoding is applied consistently, CancelledError is re-raised everywhere it matters, and the `finally` block in the SSE generator guarantees queue cleanup on disconnect. No hardcoded credentials were found; no SQL/command injection surfaces exist.

Four warnings are raised. None are showstoppers, but two carry real failure risk under load or during deployment: the double-reset of `player.bet` in `run_betting_round`, and the private API mutation of `_fastapi_routing._PING_INTERVAL` which will silently break whenever FastAPI is upgraded. Two additional warnings cover a Redis connection error that is swallowed without retry and a broker subscriber that goes permanently silent after a fatal error.

Four info items cover test gaps and minor style issues.

---

## Warnings

### WR-01: Double reset of `player.bet` in `run_betting_round`

**File:** `backend/app/engine/game.py:253-257`

**Issue:** `_collect_bets_to_pot` already zeros every player's `bet` field on line 134. Immediately after, `run_betting_round` loops again and zeros `bet` a second time on lines 256-257. The comment labels this "Pitfall 5" but the pitfall is already handled inside `_collect_bets_to_pot`. The double reset is harmless today, but it makes the invariant harder to reason about and will cause a subtle bug if `_collect_bets_to_pot` is ever changed to only zero matched bets (e.g., for side-pot support). The function contract for `_collect_bets_to_pot` says "Resets each player.bet to 0 after collection" — that contract should be the single source of truth.

**Fix:** Remove the redundant loop at lines 255-257 in `run_betting_round`:
```python
# Collect all bets into pot after round closes
game_state.pot = _collect_bets_to_pot(players, game_state.pot)
# No second reset needed — _collect_bets_to_pot already zeroes player.bet

game_state.players = players
return game_state, players
```

---

### WR-02: Private FastAPI internals mutated at startup (`_PING_INTERVAL`)

**File:** `backend/app/main.py:40`

**Issue:** `_fastapi_routing._PING_INTERVAL = 5.0` patches a private module attribute. FastAPI does not document this attribute as a stable API. Any FastAPI upgrade can rename, remove, or change the semantics of this attribute — when that happens, the mutation silently has no effect. The 5-second heartbeat requirement (STREAM-03) will be violated without any error, test failure, or log warning. There is no assertion in the test suite that the heartbeat actually fires at the configured interval.

**Fix (short-term):** Add an assertion immediately after the patch so breakage is loud:
```python
_fastapi_routing._PING_INTERVAL = 5.0
assert getattr(_fastapi_routing, "_PING_INTERVAL", None) == 5.0, (
    "FastAPI internals changed — _PING_INTERVAL no longer exists; update heartbeat configuration"
)
```

**Fix (long-term):** If FastAPI exposes a supported configuration mechanism for the SSE ping interval in the version in use, prefer that. Check `node_modules/next/dist/docs/` equivalent for the FastAPI version pinned in `pyproject.toml`.

---

### WR-03: Redis `ConnectionError` swallowed silently — broker goes permanently silent

**File:** `backend/app/broadcast/broker.py:95-97`

**Issue:** The `ConnectionError` handler at line 95 logs a warning and then falls through — the `run_subscriber` coroutine returns normally. The background task created in `main.py` line 51 is then done and never restarted. Every Redis reconnection event (Redis restart, network blip, Docker container restart) permanently silences the SSE broadcast for the lifetime of the FastAPI process. All connected clients stop receiving events; there is no log entry indicating the broadcast pipeline is dead; no exception propagates to the task runner.

```python
except redis.exceptions.ConnectionError as exc:
    logger.warning("Redis subscriber ConnectionError (likely shutdown): %s", exc)
# falls through — task is now done, never restarted
```

**Fix:** Either re-raise the exception so the lifespan shutdown or task supervisor can react, or implement a reconnect loop with back-off:
```python
except redis.exceptions.ConnectionError as exc:
    logger.error(
        "Redis subscriber ConnectionError — broadcast pipeline is DOWN: %s", exc, exc_info=True
    )
    raise  # let lifespan handle it; a dead subscriber is not a clean shutdown
```

If reconnect-on-error is desired, wrap `run_subscriber` in a retry loop inside the lifespan rather than hiding the retry logic inside the subscriber itself.

---

### WR-04: `broker.run_subscriber` exits silently on non-CancelledError fatal errors

**File:** `backend/app/broadcast/broker.py:100-101`

**Issue:** The outermost `except Exception` block at line 100 logs the error and returns. Same consequence as WR-03: the subscriber task is done, the broadcast pipeline is dead, but FastAPI continues accepting SSE connections that will never receive another event. The lifespan has no mechanism to detect that `subscriber_task` died unexpectedly — `task.done()` would return `True` but nobody checks it.

**Fix:** Re-raise after logging so the exception surface is visible to the task supervisor:
```python
except Exception as exc:
    logger.error("Broker subscriber fatal error: %s", exc, exc_info=True)
    raise  # propagate — a dead subscriber must not be silently swallowed
```

Alternatively, add a task-done callback in `main.py` lifespan that logs and raises if the task exits without cancellation:
```python
def _on_subscriber_done(task: asyncio.Task) -> None:
    if not task.cancelled() and (exc := task.exception()):
        logger.critical("Subscriber task died unexpectedly: %s", exc)

app.state.subscriber_task.add_done_callback(_on_subscriber_done)
```

---

## Info

### IN-01: `test_snapshot_sent_on_connect` does not test the SSE generator directly

**File:** `backend/tests/test_sse.py:93-107`

**Issue:** The test verifies that `StubRedis.get()` returns a snapshot — it does not exercise the SSE generator itself. The actual late-joiner ordering (subscribe → get snapshot → yield snapshot → drain queue) is untested. A regression in `stream.py` that, say, reads the snapshot before subscribing to the broker would not be caught.

**Suggestion:** Add an async test that instantiates the `sse_stream` async generator, drives it through one iteration, and asserts the first yielded `ServerSentEvent` contains the snapshot payload.

---

### IN-02: `test_no_buffering_header` does not assert the header value

**File:** `backend/tests/test_sse.py:80-90`

**Issue:** The test asserts `media_type == "text/event-stream"` but the test name is `test_no_buffering_header`. The actual `X-Accel-Buffering: no` header is never checked. STREAM-03 compliance is asserted in the comment but not in the assertion.

**Suggestion:**
```python
response = EventSourceResponse(iter([test_event]))
assert response.headers.get("X-Accel-Buffering") == "no", (
    "X-Accel-Buffering: no must be set for nginx proxy compatibility"
)
```

---

### IN-03: `redis_url` has no format validation — misconfigured URLs produce cryptic errors

**File:** `backend/app/config.py:21`

**Issue:** `redis_url: str = "redis://localhost:6379"` accepts any string. A misconfigured `.env` (e.g., `REDIS_URL=localhost:6379` without the scheme) will produce a cryptic `redis.asyncio` connection error at startup rather than a clear validation message.

**Suggestion:** Add a `field_validator` for basic scheme check:
```python
from pydantic import Field, field_validator

@field_validator("redis_url")
@classmethod
def redis_url_must_have_scheme(cls, v: str) -> str:
    if not v.startswith(("redis://", "rediss://", "unix://")):
        raise ValueError(
            f"redis_url must start with redis://, rediss://, or unix://; got: {v!r}"
        )
    return v
```

---

### IN-04: `docker-compose.yml` has no Redis data persistence or memory limit

**File:** `docker-compose.yml`

**Issue:** The Redis service has no `volumes` mount for AOF/RDB persistence and no `mem_limit`. For a dev-only Redis instance this is acceptable. However, if this compose file is also used for staging deployment, a container restart drops all snapshot state and an unbounded Redis can exhaust host memory under a sustained broadcast load.

**Suggestion:** If this is dev-only, add a comment making that explicit. If used for staging, add:
```yaml
redis:
  image: redis:7-alpine
  command: redis-server --save "" --appendonly no --maxmemory 128mb --maxmemory-policy allkeys-lru
  deploy:
    resources:
      limits:
        memory: 192M
```

---

_Reviewed: 2026-05-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
