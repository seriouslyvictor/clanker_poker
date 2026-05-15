"""
broker.py — asyncio.Queue fan-out broker + Redis pub/sub subscriber.

Flow: Redis pub/sub message → EventBroker.broadcast() → each client's asyncio.Queue
Each connected SSE client has its own Queue (maxsize=10). Slow clients drop events
(put_nowait + QueueFull) rather than blocking the publisher.

D-09: per-client asyncio.Queue is the local broker; Redis pub/sub is the cross-process bus.
"""
import asyncio
import json
import logging

import redis.asyncio as redis

_REASONING_CHANNEL = "game:reasoning"  # same value as publisher.REASONING_CHANNEL

logger = logging.getLogger(__name__)


class EventBroker:
    """
    Fan-out broker: one Redis pub/sub subscriber feeds N per-client asyncio.Queues.

    Thread-safety: asyncio.Lock protects _queues list during subscribe/unsubscribe.
    Message IDs: _message_id is monotonically increasing (D-07); access via next_id().
    """

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._message_id: int = 0

    def next_id(self) -> int:
        """Return next monotonically increasing message ID (D-07). NOT thread-safe — single-threaded asyncio only."""
        self._message_id += 1
        return self._message_id

    @property
    def viewer_count(self) -> int:
        """Return number of currently connected SSE clients (point-in-time snapshot).
        No lock needed — len() read is safe for demand-gate heuristic (Assumption A2)."""
        return len(self._queues)

    async def subscribe(self) -> asyncio.Queue:
        """
        Register a new client queue and return it.
        Queue is created here (inside async def) to avoid Pitfall 5 (wrong event loop).
        maxsize=10: prevents unbounded memory growth from slow clients.
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        async with self._lock:
            self._queues.append(q)
        logger.info("Viewer connected — active viewers: %d", self.viewer_count)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove client queue on disconnect. Called in SSE generator finally block."""
        async with self._lock:
            try:
                self._queues.remove(q)
            except ValueError:
                pass  # already removed (double-disconnect is safe)
        logger.info("Viewer disconnected — active viewers: %d", self.viewer_count)

    async def broadcast(self, data: str) -> None:
        """
        Fan-out a message string to all connected client queues.
        Uses put_nowait() — slow clients drop events rather than blocking the publisher.
        Lock snapshot prevents race with concurrent subscribe/unsubscribe.
        """
        async with self._lock:
            queues_snapshot = list(self._queues)
        for q in queues_snapshot:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                logger.debug("Client queue full — dropping event for slow consumer")

    async def run_subscriber(self, redis_client: redis.Redis) -> None:
        """
        Background task: subscribe to both Redis channels, fan-out enveloped messages to client queues.

        Messages are wrapped in a JSON envelope {"event": "game_state"|"reasoning", "data": "..."}
        before broadcasting. stream.py unpacks the envelope to set the SSE event= field.

        Changed from Phase 3 signature: channel param removed — subscribes to both channels.
        main.py must update call site: broker.run_subscriber(redis_client)  (no channel arg).

        Uses get_message(timeout=1.0) NOT pubsub.listen() — allows clean CancelledError on shutdown.
        decode_responses=False on redis_client — messages arrive as bytes, decoded here.
        Catches both CancelledError and ConnectionError per Pitfall 2 (redis-py cancellation bug).
        """
        channels = ["game:state", _REASONING_CHANNEL]
        event_name_by_channel = {
            "game:state": "game_state",
            _REASONING_CHANNEL: "reasoning",
        }

        try:
            async with redis_client.pubsub() as pubsub:
                await pubsub.subscribe(*channels)
                logger.info("Broker subscribed to Redis channels: %s", channels)
                try:
                    while True:
                        message = await pubsub.get_message(
                            ignore_subscribe_messages=True, timeout=1.0
                        )
                        if message is not None:
                            channel_bytes = message.get("channel", b"game:state")
                            channel = channel_bytes.decode("utf-8") if isinstance(channel_bytes, bytes) else channel_bytes
                            data = message["data"]
                            if isinstance(data, bytes):
                                data = data.decode("utf-8")
                            event_name = event_name_by_channel.get(channel, "game_state")
                            envelope = json.dumps({"event": event_name, "data": data})
                            await self.broadcast(envelope)
                except asyncio.CancelledError:
                    await pubsub.unsubscribe(*channels)
                    raise  # propagate shutdown signal cleanly
                except redis.exceptions.ConnectionError as exc:
                    # Pitfall 2: redis-py cancellation sometimes raises ConnectionError
                    logger.warning("Redis subscriber ConnectionError (likely shutdown): %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Broker subscriber fatal error: %s", exc, exc_info=True)
