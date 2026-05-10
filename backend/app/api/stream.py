"""
stream.py — GET /api/stream SSE endpoint.

D-08: Single endpoint, all clients subscribe here.
D-03: Late joiners receive Redis snapshot as first event before live events.
D-05: event: game_state for game state; heartbeat handled automatically by
      fastapi.routing._PING_INTERVAL (patched to 5.0s in main.py lifespan).
D-07: Monotonically increasing integer id: on every game_state event via broker.next_id().

CRITICAL ORDER for late-joiner correctness (Pitfall 4):
  1. Subscribe to broker queue FIRST (captures any events arriving during snapshot read)
  2. Read snapshot from Redis and send it
  3. Drain live events from queue

X-Accel-Buffering: no is set automatically by EventSourceResponse — do not set manually.
"""
import asyncio
import json
from collections.abc import AsyncIterable

from fastapi import APIRouter, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.broadcast.publisher import SNAPSHOT_KEY, REASONING_SNAPSHOT_KEY

router = APIRouter()


@router.get("/api/stream", response_class=EventSourceResponse)
async def sse_stream(request: Request) -> AsyncIterable[ServerSentEvent]:
    """
    SSE endpoint: push game state to all connected clients.

    - First event: Redis snapshot (last known GameState) — satisfies STREAM-02.
    - Subsequent events: live GameState on each phase transition — satisfies STREAM-01.
    - Heartbeat: ': ping' comment auto-sent by FastAPI every 5s — satisfies STREAM-03.
    - Message IDs: broker.next_id() — monotonically increasing — satisfies SC-4.
    - X-Accel-Buffering: no — set automatically by EventSourceResponse — satisfies STREAM-03.
    """
    broker = request.app.state.broker
    redis_client = request.app.state.redis_client

    # Step 1: Subscribe FIRST — any events arriving during snapshot read land in the queue
    queue = await broker.subscribe()

    try:
        # Step 2: Send snapshot to late joiner (may be None if no game has run yet)
        snapshot: bytes | None = await redis_client.get(SNAPSHOT_KEY)
        if snapshot is not None:
            yield ServerSentEvent(
                raw_data=snapshot.decode("utf-8"),
                event="game_state",
                id=str(broker.next_id()),
                retry=3000,
            )

        # Send reasoning snapshot to reconnecting clients — recover current hand reasoning state.
        # lrange returns [] if key doesn't exist (no reasoning yet this hand) — safe to call always.
        reasoning_deltas: list[bytes] = await redis_client.lrange(
            REASONING_SNAPSHOT_KEY, 0, -1
        )
        if reasoning_deltas:
            deltas_payload = json.dumps([
                json.loads(d.decode("utf-8") if isinstance(d, bytes) else d)
                for d in reasoning_deltas
            ])
            yield ServerSentEvent(
                raw_data=deltas_payload,
                event="reasoning_snapshot",
                id=str(broker.next_id()),
                retry=3000,
            )

        # Step 3: Drain live events; check disconnect on each iteration
        while True:
            if await request.is_disconnected():
                break
            try:
                envelope_str: str = await asyncio.wait_for(queue.get(), timeout=1.0)
                try:
                    envelope = json.loads(envelope_str)
                    event_type = envelope.get("event", "game_state")
                    raw_data = envelope.get("data", envelope_str)
                except (ValueError, AttributeError):
                    # Malformed envelope — treat as game_state for backward compat
                    event_type = "game_state"
                    raw_data = envelope_str
                yield ServerSentEvent(
                    raw_data=raw_data,
                    event=event_type,
                    id=str(broker.next_id()),
                    retry=3000,
                )
            except asyncio.TimeoutError:
                continue  # loop back to check is_disconnected

    finally:
        # Always unsubscribe — prevents orphaned queue leaking memory on disconnect
        await broker.unsubscribe(queue)
