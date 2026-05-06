"""
game_loop.py — continuous background game loop for Phase 3.

D-10: FastAPI lifespan creates an asyncio.Task running this function.
      Runs GameSession continuously; waits HAND_DELAY_SECONDS between sessions.

D-11: HAND_DELAY_SECONDS defaults to 3 — configurable via Settings / env var.

Phase 6 will replace this with a viewer-triggered start. For now the loop runs
unconditionally — no viewer presence check.

Error handling:
  - asyncio.CancelledError: re-raised immediately (lifespan shutdown signal)
  - Any other exception: logged + loop continues after HAND_DELAY_SECONDS
    This prevents a single bad hand from killing the entire broadcast pipeline.
"""
import asyncio
import logging
from functools import partial

import redis.asyncio as redis_asyncio

from app.broadcast.publisher import publish
from app.config import Settings
from app.engine.session import GameSession

logger = logging.getLogger(__name__)


async def run_game_loop(redis_client: redis_asyncio.Redis, settings: Settings) -> None:
    """
    Continuous game loop. Runs until cancelled by FastAPI lifespan shutdown.

    Creates a new GameSession each iteration (fresh chip stacks).
    Passes publish() as broadcast_fn so each phase transition is pushed to Redis.

    Args:
        redis_client: Shared redis.asyncio.Redis connection from app.state
        settings: App settings (hand_delay_seconds, etc.)
    """
    logger.info("Game loop started (hand_delay=%ds)", settings.hand_delay_seconds)

    while True:
        try:
            session = GameSession(n_players=4, starting_chips=1000, big_blind=20)

            # broadcast_fn: partial binds redis_client so game.py can call publish(state)
            broadcast_fn = partial(publish, redis_client)

            logger.info("Starting new GameSession (10 hands)")
            await session.run(n_hands=10, broadcast_fn=broadcast_fn)
            logger.info("GameSession complete — waiting %ds before next session", settings.hand_delay_seconds)

            await asyncio.sleep(settings.hand_delay_seconds)

        except asyncio.CancelledError:
            logger.info("Game loop cancelled — shutting down")
            raise  # propagate to lifespan; do NOT swallow

        except Exception as exc:
            # Log and continue — prevents silent crash of the broadcast pipeline
            # A single bad hand must not kill SSE for all connected clients
            logger.error("Game loop error (will retry): %s", exc, exc_info=True)
            await asyncio.sleep(settings.hand_delay_seconds)
