---
phase: 05-frontend-wiring
plan: "02"
subsystem: backend-cors-sse
tags: [cors, sse, redis, reconnect, reasoning-snapshot]
dependency_graph:
  requires: []
  provides: [cors-vite-origin, sse-retry-3000, reasoning-snapshot-on-connect]
  affects: [backend/app/config.py, backend/.env.example, backend/app/api/stream.py, backend/app/broadcast/publisher.py]
tech_stack:
  added: []
  patterns: [redis-list-as-replay-buffer, sse-retry-field, cors-enumerated-origins]
key_files:
  created: []
  modified:
    - backend/app/config.py
    - backend/.env.example
    - backend/app/api/stream.py
    - backend/app/broadcast/publisher.py
decisions:
  - "REASONING_SNAPSHOT_KEY cleared on every publish() call (phase transition), not on every hand end — phase transitions are the natural reset boundary already used by the game loop"
  - "reasoning_snapshot emitted unconditionally after game_state snapshot — lrange returns [] if key absent, so no guard needed; if reasoning_deltas is empty, no event is emitted"
  - "retry=3000 added to ALL three ServerSentEvent call sites including the new reasoning_snapshot event — 3s SLA applies to every event type"
metrics:
  duration_seconds: 122
  completed: "2026-05-10"
  tasks_completed: 2
  files_modified: 4
---

# Phase 5 Plan 02: Backend CORS + retry:3000 + Reasoning Snapshot Summary

Three backend fixes applied to unblock Vite frontend wiring: CORS extended to 5173, SSE retry field set to 3s, reasoning replay buffer added to Redis.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add Vite origin to CORS config and update env.example | f4e9270 | backend/app/config.py, backend/.env.example |
| 2 | Add retry:3000 to SSE events and emit reasoning snapshot on connect | 6f9e57a | backend/app/api/stream.py, backend/app/broadcast/publisher.py |

## Changes Applied

### Task 1 — backend/app/config.py

```diff
-    cors_origins: list[str] = ["http://localhost:3000"]
+    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
```

### Task 1 — backend/.env.example

```diff
-# CORS allowed origins for Next.js frontend (JSON array format)
-CORS_ORIGINS=["http://localhost:3000"]
+# CORS allowed origins — JSON array of allowed frontend origins.
+# Dev: Vite (5173) + legacy Next.js (3000) are included in the default.
+# Production: set this env var to your VPS frontend origin, e.g.:
+# CORS_ORIGINS=["https://poker.yourdomain.com"]
+CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

### Task 2 — backend/app/broadcast/publisher.py

```diff
 REASONING_CHANNEL = "game:reasoning"
+REASONING_SNAPSHOT_KEY = "game:reasoning:current"  # Redis list of reasoning delta JSON strings

 async def publish(redis_client, state):
     payload = state.model_dump_json(by_alias=True)
+    # Clear reasoning snapshot on each phase transition — new phase, fresh accumulation.
+    await redis_client.delete(REASONING_SNAPSHOT_KEY)
     await redis_client.set(SNAPSHOT_KEY, payload, ex=SNAPSHOT_TTL)
     await redis_client.publish(CHANNEL, payload)

 async def publish_reasoning(redis_client, player_id, phase, delta, done):
     payload = json.dumps({"playerId": player_id, "phase": phase, "delta": delta, "done": done})
     await redis_client.publish(REASONING_CHANNEL, payload)
+    # Append delta to reasoning snapshot — allows reconnecting clients to recover current reasoning.
+    await redis_client.rpush(REASONING_SNAPSHOT_KEY, payload)
+    await redis_client.expire(REASONING_SNAPSHOT_KEY, SNAPSHOT_TTL)
```

### Task 2 — backend/app/api/stream.py

```diff
-from app.broadcast.publisher import SNAPSHOT_KEY
+from app.broadcast.publisher import SNAPSHOT_KEY, REASONING_SNAPSHOT_KEY

         if snapshot is not None:
             yield ServerSentEvent(
                 raw_data=snapshot.decode("utf-8"),
                 event="game_state",
                 id=str(broker.next_id()),
+                retry=3000,
             )

+        # Send reasoning snapshot to reconnecting clients — recover current hand reasoning state.
+        # lrange returns [] if key doesn't exist (no reasoning yet this hand) — safe to call always.
+        reasoning_deltas: list[bytes] = await redis_client.lrange(
+            REASONING_SNAPSHOT_KEY, 0, -1
+        )
+        if reasoning_deltas:
+            deltas_payload = json.dumps([
+                json.loads(d.decode("utf-8") if isinstance(d, bytes) else d)
+                for d in reasoning_deltas
+            ])
+            yield ServerSentEvent(
+                raw_data=deltas_payload,
+                event="reasoning_snapshot",
+                id=str(broker.next_id()),
+                retry=3000,
+            )

             yield ServerSentEvent(
                 raw_data=raw_data,
                 event=event_type,
                 id=str(broker.next_id()),
+                retry=3000,
             )
```

## Verification Output

```
# CORS origins check
5173 present: True
3000 present: True

# retry=3000 count in stream.py
3 matches (lines 54, 71, 92)

# REASONING_SNAPSHOT_KEY in publisher.py
3 matches (constant definition line 24, delete line 37, rpush line 72, expire line 73)

# REASONING_SNAPSHOT_KEY in stream.py
2 matches (import line 24, lrange line 60)

# reasoning_snapshot event
1 match (line 69)

# py_compile checks
stream.py: OK
publisher.py: OK
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all changes are fully wired to Redis. The reasoning_snapshot event emits real data from Redis; Plan 03 (frontend) will consume it.

## Threat Flags

None — all trust boundaries addressed per the plan's threat model:
- T-05-02-01 mitigated: specific origins enumerated, no wildcard
- T-05-02-02 mitigated: .env.example documents production pattern
- T-05-02-05 mitigated: SNAPSHOT_TTL expire called on every rpush; delete() on phase transition

## Self-Check: PASSED

- backend/app/config.py: modified, contains localhost:5173
- backend/.env.example: modified, contains localhost:5173
- backend/app/api/stream.py: modified, contains 3x retry=3000 + reasoning_snapshot event
- backend/app/broadcast/publisher.py: modified, contains REASONING_SNAPSHOT_KEY + rpush + delete
- Commit f4e9270: exists (Task 1)
- Commit 6f9e57a: exists (Task 2)
