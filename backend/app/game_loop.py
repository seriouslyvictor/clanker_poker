"""
game_loop.py — continuous background game loop with LLM decision integration (Phase 4).

D-10: FastAPI lifespan creates an asyncio.Task running this function.
D-14: Constructs LLM decision fn closure and passes to session.run().
D-15/D-16: BudgetTracker + CircuitBreaker created per session; logged at session end.

CancelledError re-raise rule: always propagate — never swallow.
Global 8s budget per decision phase: each individual LLM call has its own 2s timeout
(INDIVIDUAL_TIMEOUT_S in decision.py). Four sequential players x 2s = at most 8s of
LLM time per phase. This is a monitoring target enforced by per-call timeouts, not a
single asyncio.wait_for() wrapper around session.run(). The circuit breaker prevents
cost runaway if a provider is consistently slow.
"""
import asyncio
import logging
from functools import partial

import redis.asyncio as redis_asyncio

from app.ai.archetypes import assign_archetypes
from app.ai.budget import BudgetTracker, CircuitBreaker
from app.ai.decision import make_llm_decision_fn
from app.broadcast.publisher import publish
from app.config import Settings
from app.engine.session import GameSession

logger = logging.getLogger(__name__)


async def run_game_loop(redis_client: redis_asyncio.Redis, settings: Settings) -> None:
    """
    Continuous game loop with LLM decisions. Runs until cancelled by lifespan shutdown.

    Per session:
      1. Create fresh GameSession (config-driven players from models.config.json)
      2. Assign unique archetypes via random shuffle (D-08)
      3. Create BudgetTracker + CircuitBreaker (reset per session — D-15, D-16)
      4. Build LLM decision fn closure
      5. Run session.run() with LLM decision_fn + broadcast_fn
      6. Log budget summary at session end
    """
    logger.info("Game loop started with LLM decisions (hand_delay=%ds)", settings.hand_delay_seconds)

    while True:
        try:
            # Fresh session: config-driven players + starting stacks
            # NOTE: Viewer presence check intentionally deferred to Phase 6 (VIEWER-02 -- Start a Game
            # button). Game loop runs unconditionally in Phase 4 for development purposes.
            session = GameSession(n_players=4, starting_chips=1000, big_blind=20)

            # Archetype assignment: random shuffle, unique per player (D-08)
            archetypes = assign_archetypes(session.players)
            logger.info(
                "Archetypes assigned: %s",
                {pid: arch.name for pid, arch in archetypes.items()},
            )

            # Per-session budget protection (D-15, D-16, INFRA-05)
            budget = BudgetTracker()
            circuit = CircuitBreaker(threshold=3)

            # LLM decision fn closure — matches DecisionFn signature exactly
            decision_fn = make_llm_decision_fn(
                archetypes=archetypes,
                redis_client=redis_client,
                budget=budget,
                circuit=circuit,
                player_models=session.player_models,
            )

            # broadcast_fn: partial binds redis_client — called after each player action (D-03)
            broadcast_fn = partial(publish, redis_client)

            logger.info("Starting new GameSession (10 hands, LLM decisions)")
            await session.run(n_hands=10, decision_fn=decision_fn, broadcast_fn=broadcast_fn)

            # Log session spend at end (D-15)
            logger.info("GameSession complete — budget: %s", budget.summary())
            logger.info("Waiting %ds before next session", settings.hand_delay_seconds)

            await asyncio.sleep(settings.hand_delay_seconds)

        except asyncio.CancelledError:
            logger.info("Game loop cancelled — shutting down")
            raise  # MUST propagate — lifespan shutdown signal

        except Exception as exc:
            logger.error("Game loop error (will retry): %s", exc, exc_info=True)
            await asyncio.sleep(settings.hand_delay_seconds)
