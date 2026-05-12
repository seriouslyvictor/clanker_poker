"""
publisher.py — serialize GameState and publish to Redis pub/sub + snapshot key.

D-03: Snapshot stored as Redis string key (SNAPSHOT_KEY) — late joiners read this on connect.
D-04: Full GameState on every broadcast (no deltas).
D-06: Called at each phase transition by the broadcast_fn callback in game.py.

Order matters: SET snapshot BEFORE PUBLISH — eliminates late-joiner race window (Pitfall 4).
Serialization: model_dump_json(by_alias=True) produces camelCase JSON matching types.ts GameState.
"""
import json
import logging

import redis.asyncio as redis

from app.engine.models import GameState

logger = logging.getLogger(__name__)

CHANNEL = "game:state"
SNAPSHOT_KEY = "game:state:last"
SNAPSHOT_TTL = 3600  # 1 hour — prevents stale snapshot persisting across long server restarts
REASONING_CHANNEL = "game:reasoning"
REASONING_SNAPSHOT_KEY = "game:reasoning:current"  # Redis list of reasoning delta JSON strings


async def publish(redis_client: redis.Redis, state: GameState) -> None:
    """
    Serialize state as camelCase JSON, write to Redis snapshot key, then publish to channel.

    Args:
        redis_client: redis.asyncio.Redis with decode_responses=False
        state: Current GameState — serialized with by_alias=True for camelCase field names
    """
    payload = state.model_dump_json(by_alias=True)  # camelCase JSON matching types.ts
    # Clear reasoning snapshot only at hand start — late joiners can recover mid-hand reasoning.
    if state.phase == "pre-flop":
        await redis_client.delete(REASONING_SNAPSHOT_KEY)
    # SET before PUBLISH: late joiner arriving between these two ops sees the snapshot
    await redis_client.set(SNAPSHOT_KEY, payload, ex=SNAPSHOT_TTL)
    await redis_client.publish(CHANNEL, payload)
    logger.debug("Published game state (phase=%s, payload_len=%d)", state.phase, len(payload))


async def publish_reasoning(
    redis_client: redis.Redis,
    player_id: str,
    phase: str,
    delta: str,
    done: bool,
) -> None:
    """
    Publish a reasoning token delta to the reasoning Redis channel (D-01, D-02).

    Called by decision.py on each streaming chunk and once with done=True at stream end.
    Payload is camelCase to match TypeScript ReasoningEntry.delta expectation.

    Args:
        redis_client: Shared redis.asyncio.Redis connection
        player_id:    Player model ID (e.g. "gpt4", "gemini") — matches TypeScript ModelId
        phase:        Current game phase (e.g. "pre-flop", "flop")
        delta:        Token delta string; empty string ("") on final done=True call
        done:         True on the final event for this player's reasoning turn
    """
    payload = json.dumps({
        "playerId": player_id,
        "phase": phase,
        "delta": delta,
        "done": done,
    })
    await redis_client.publish(REASONING_CHANNEL, payload)
    # Append delta to reasoning snapshot — allows reconnecting clients to recover current reasoning.
    await redis_client.rpush(REASONING_SNAPSHOT_KEY, payload)
    await redis_client.expire(REASONING_SNAPSHOT_KEY, SNAPSHOT_TTL)
    logger.debug(
        "Published reasoning delta (player=%s, phase=%s, done=%s, delta_len=%d)",
        player_id, phase, done, len(delta),
    )
