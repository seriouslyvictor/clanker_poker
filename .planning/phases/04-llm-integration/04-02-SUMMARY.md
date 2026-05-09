---
phase: 04-llm-integration
plan: "02"
subsystem: api
tags: [redis, sse, pubsub, fastapi, broker, envelope-routing]

requires:
  - phase: 03-sse-broadcast
    provides: EventBroker, run_subscriber(), SSE stream endpoint, publisher.publish()

provides:
  - publish_reasoning() publishes LLM token deltas to game:reasoning Redis channel
  - EventBroker.run_subscriber() dual-channel subscription with JSON envelope wrapping
  - stream.py SSE generator routes event= field by envelope type (game_state | reasoning)

affects:
  - 04-03 (decision.py calls publish_reasoning() for streaming LLM output)
  - 04-04 (frontend ReasoningPanel consumes event: reasoning SSE events)

tech-stack:
  added: []
  patterns:
    - "JSON envelope pattern: broker wraps Redis messages as {event, data} before fan-out"
    - "Backward-compat fallback: malformed envelope defaults to game_state event type"
    - "Dual-channel subscriber: single pubsub connection, multiple channels, envelope routing"

key-files:
  created: []
  modified:
    - backend/app/broadcast/publisher.py
    - backend/app/broadcast/broker.py
    - backend/app/api/stream.py
    - backend/app/main.py

key-decisions:
  - "Inline _REASONING_CHANNEL constant in broker.py (not imported from publisher) to keep broker infrastructure-independent"
  - "Single pubsub connection subscribes to both channels — avoids two background tasks"
  - "Envelope JSON wrapping in broker.broadcast() — stream.py unpacks; snapshot bypasses envelope (stored raw)"

patterns-established:
  - "Envelope routing: broker tags each message with event type before enqueuing; SSE layer unpacks"
  - "Snapshot bypasses envelope: Redis snapshot stored as raw game state JSON, always emits event=game_state"

requirements-completed:
  - AI-05

duration: 18min
completed: 2026-05-08
---

# Phase 4 Plan 02: SSE Dual-Channel Reasoning Broadcast Summary

**Dual-channel Redis pub/sub with JSON envelope routing: publish_reasoning() streams LLM token deltas via game:reasoning channel; broker wraps both channels in {event, data} envelopes; stream.py routes SSE event= field by type**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-08T00:00:00Z
- **Completed:** 2026-05-08T00:18:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added `publish_reasoning(redis_client, player_id, phase, delta, done)` to publisher.py with `REASONING_CHANNEL = "game:reasoning"` constant; camelCase payload matches TypeScript `ReasoningEntry`
- Extended `EventBroker.run_subscriber()` to subscribe to both `game:state` and `game:reasoning` channels in a single pubsub connection, wrapping each message in a `{"event": "...", "data": "..."}` envelope before fan-out
- Updated stream.py SSE generator to unpack envelopes and route `event=` field dynamically; snapshot path unchanged (always `game_state`); added malformed-envelope fallback for backward compat
- Updated main.py call site: `broker.run_subscriber(redis_client)` — no `channel=` arg; all 142 existing tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Add publish_reasoning() to publisher.py** - `d38db16` (feat)
2. **Task 2: Extend broker.py + stream.py for dual-channel envelope routing** - `eed08f8` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `backend/app/broadcast/publisher.py` - Added `REASONING_CHANNEL` constant and `publish_reasoning()` function; `publish()` and `CHANNEL` unchanged
- `backend/app/broadcast/broker.py` - Added `_REASONING_CHANNEL` constant, `import json`; replaced `run_subscriber(channel)` with dual-channel `run_subscriber()` using envelope wrapping
- `backend/app/api/stream.py` - Added `import json`; live event loop now unpacks envelope to set `event=` and `raw_data`; snapshot section unchanged
- `backend/app/main.py` - Updated `run_subscriber` call site to remove `channel="game:state"` kwarg

## Decisions Made
- Inlined `_REASONING_CHANNEL = "game:reasoning"` in broker.py rather than importing from publisher.py — keeps broker as standalone infrastructure without domain coupling
- Single pubsub connection subscribes to both channels (`await pubsub.subscribe(*channels)`) — avoids spawning a second background task and reduces Redis connection overhead
- Snapshot stored as raw game state JSON is NOT wrapped in envelope — it's fetched from Redis separately and always emits `event="game_state"` directly; only live broker fan-out messages use envelopes

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

The worktree's file system is separate from the main repo's working tree. Initial edits inadvertently targeted `D:/Balatro-Poker/clanker_poker/backend/...` (main repo) instead of `D:/Balatro-Poker/clanker_poker/.claude/worktrees/agent-a1caae9449cbe0061/backend/...` (worktree). Corrected by explicitly using the full worktree path for all subsequent file operations. The main repo's publisher.py was also modified as a side effect — that change mirrors the worktree change and is harmless since both files start from the same base commit.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 03 (decision.py) can now call `await publish_reasoning(redis_client, player_id, phase, delta, done)` on each LLM streaming chunk
- The SSE pipeline will correctly emit `event: reasoning` events to browser clients
- Frontend ReasoningPanel (Plan 04) can listen for `event: reasoning` and `event: game_state` independently
- No blockers

---
*Phase: 04-llm-integration*
*Completed: 2026-05-08*
