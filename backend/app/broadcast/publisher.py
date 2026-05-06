"""
publisher.py — serialize GameState and publish to Redis pub/sub + snapshot key.

D-03: Snapshot stored as Redis string key (SNAPSHOT_KEY) — late joiners read this on connect.
D-04: Full GameState on every broadcast (no deltas).
D-06: Called at each phase transition by the broadcast_fn callback in game.py.

Order matters: SET snapshot BEFORE PUBLISH — eliminates late-joiner race window (Pitfall 4).
Serialization: model_dump_json(by_alias=True) produces camelCase JSON matching types.ts GameState.
"""
import logging

import redis.asyncio as redis

from app.engine.models import GameState

logger = logging.getLogger(__name__)

CHANNEL = "game:state"
SNAPSHOT_KEY = "game:state:last"
SNAPSHOT_TTL = 3600  # 1 hour — prevents stale snapshot persisting across long server restarts


async def publish(redis_client: redis.Redis, state: GameState) -> None:
    """
    Serialize state as camelCase JSON, write to Redis snapshot key, then publish to channel.

    Args:
        redis_client: redis.asyncio.Redis with decode_responses=False
        state: Current GameState — serialized with by_alias=True for camelCase field names
    """
    payload = state.model_dump_json(by_alias=True)  # camelCase JSON matching types.ts
    # SET before PUBLISH: late joiner arriving between these two ops sees the snapshot
    await redis_client.set(SNAPSHOT_KEY, payload, ex=SNAPSHOT_TTL)
    await redis_client.publish(CHANNEL, payload)
    logger.debug("Published game state (phase=%s, payload_len=%d)", state.phase, len(payload))
