import asyncio
from contextlib import asynccontextmanager

import fastapi.routing as _fastapi_routing
import redis.asyncio as redis_asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.stream import router as stream_router
from app.broadcast.broker import EventBroker
from app.config import get_settings
from app.game_loop import run_game_loop
from app.logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan: startup wires Redis + broker + background tasks; shutdown tears down cleanly.

    Startup order:
      1. Patch SSE heartbeat interval to 5s (STREAM-03)
      2. Connect to Redis
      3. Instantiate EventBroker
      4. Start Redis subscriber task (broker fan-out)
      5. Start game loop task (continuous GameSession)

    Shutdown order (reverse):
      1. Cancel game loop task
      2. Cancel subscriber task
      3. Await both tasks (ignoring CancelledError + other exceptions)
      4. Close Redis connection

    All shared state lives on app.state — not module globals.
    This supports test fixture injection (replace app.state.broker with a mock).
    """
    setup_logging()
    settings = get_settings()

    # 1. Patch SSE ping interval — must happen before any EventSourceResponse is created
    _fastapi_routing._PING_INTERVAL = 5.0  # 5s heartbeat per STREAM-03 / D-05

    # 2. Redis connection — decode_responses=False: messages are bytes, decoded manually (Pitfall 3)
    app.state.redis_client = redis_asyncio.from_url(
        settings.redis_url, decode_responses=False
    )

    # 3. Fan-out broker
    app.state.broker = EventBroker()

    # 4. Background: Redis subscriber → fan-out to client queues (both game:state + game:reasoning)
    app.state.subscriber_task = asyncio.create_task(
        app.state.broker.run_subscriber(
            app.state.redis_client
        )
    )

    # 5. Background: continuous game loop (Phase 3 placeholder — Phase 6 adds viewer trigger)
    app.state.loop_task = asyncio.create_task(
        run_game_loop(app.state.redis_client, settings)
    )

    yield

    # Shutdown: cancel game loop first (stops new publishes), then subscriber
    app.state.loop_task.cancel()
    app.state.subscriber_task.cancel()
    for task in (app.state.loop_task, app.state.subscriber_task):
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass  # both are expected during shutdown

    await app.state.redis_client.aclose()


app = FastAPI(lifespan=lifespan)

# CORS — configured now per CONTEXT.md; tested fully in Phase 5
# IMPORTANT: never use allow_origins=["*"] with allow_credentials=True — FastAPI rejects this
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(stream_router)
