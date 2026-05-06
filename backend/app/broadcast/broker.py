"""
broker.py — asyncio.Queue fan-out broker + Redis pub/sub subscriber.

Flow: Redis pub/sub message → EventBroker.broadcast() → each client's asyncio.Queue
Each connected SSE client has its own Queue (maxsize=10). Slow clients drop events
(put_nowait + QueueFull) rather than blocking the publisher.

D-09: per-client asyncio.Queue is the local broker; Redis pub/sub is the cross-process bus.
"""
import asyncio
import logging

import redis.asyncio as redis

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

    async def subscribe(self) -> asyncio.Queue:
        """
        Register a new client queue and return it.
        Queue is created here (inside async def) to avoid Pitfall 5 (wrong event loop).
        maxsize=10: prevents unbounded memory growth from slow clients.
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        async with self._lock:
            self._queues.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove client queue on disconnect. Called in SSE generator finally block."""
        async with self._lock:
            try:
                self._queues.remove(q)
            except ValueError:
                pass  # already removed (double-disconnect is safe)

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

    async def run_subscriber(self, redis_client: redis.Redis, channel: str) -> None:
        """
        Background task: subscribe to Redis pub/sub channel, fan-out messages to client queues.
        Runs until cancelled (FastAPI lifespan shutdown).

        Uses get_message(timeout=1.0) NOT pubsub.listen() — allows clean CancelledError on shutdown.
        decode_responses=False on redis_client — messages arrive as bytes, decoded here.
        Catches both CancelledError and ConnectionError per Pitfall 2 (redis-py cancellation bug).
        """
        try:
            async with redis_client.pubsub() as pubsub:
                await pubsub.subscribe(channel)
                logger.info("Broker subscribed to Redis channel: %s", channel)
                try:
                    while True:
                        message = await pubsub.get_message(
                            ignore_subscribe_messages=True, timeout=1.0
                        )
                        if message is not None:
                            data = message["data"]
                            if isinstance(data, bytes):
                                data = data.decode("utf-8")
                            await self.broadcast(data)
                except asyncio.CancelledError:
                    await pubsub.unsubscribe(channel)
                    raise  # propagate shutdown signal cleanly
                except redis.exceptions.ConnectionError as exc:
                    # Pitfall 2: redis-py cancellation sometimes raises ConnectionError
                    logger.warning("Redis subscriber ConnectionError (likely shutdown): %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Broker subscriber fatal error: %s", exc, exc_info=True)
