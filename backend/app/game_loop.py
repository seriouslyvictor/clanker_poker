"""
game_loop.py — demand-gated background game loop with LLM decision integration (Phase 6).

D-10: FastAPI lifespan creates an asyncio.Task running this function.
D-14: Constructs LLM decision fn closure and passes to session.run().
D-15/D-16: BudgetTracker + CircuitBreaker created per session; logged at session end.
D-06 (Phase 6): Game loop is now demand-gated — waits on asyncio.Event after each session.
               No game starts without a viewer-triggered POST /api/game/start.

CancelledError re-raise rule: always propagate — never swallow.
Global 8s budget per decision phase: each individual LLM call has its own 2s timeout
(INDIVIDUAL_TIMEOUT_S in decision.py). Four sequential players x 2s = at most 8s of
LLM time per phase. This is a monitoring target enforced by per-call timeouts, not a
single asyncio.wait_for() wrapper around session.run(). The circuit breaker prevents
cost runaway if a provider is consistently slow.
"""
import asyncio
import json
import logging
from functools import partial

import redis.asyncio as redis_asyncio

from app.ai.archetypes import assign_archetypes
from app.ai.budget import BudgetTracker, CircuitBreaker
from app.ai.decision import make_llm_decision_fn
from app.broadcast.publisher import publish, publish_game_status, GAME_LAST_RESULT_KEY, SNAPSHOT_TTL
from app.config import Settings
from app.engine.session import GameSession

logger = logging.getLogger(__name__)


async def run_game_loop(
    redis_client: redis_asyncio.Redis,
    settings: Settings,
    broker,       # EventBroker — passed to publish_game_status
    start_event,  # asyncio.Event — demand gate signal
    app_state,    # app.state — for game_running flag
) -> None:
    """
    Demand-gated game loop with LLM decisions. Runs until cancelled by lifespan shutdown.

    Waits on asyncio.Event (set by POST /api/game/start) before each session.
    No game starts without a viewer trigger — enforces VIEWER-02 budget constraint.

    Per session:
      1. Wait for start_event (demand gate)
      2. Clear event + set game_running flag + broadcast game_status(running=True)
      3. Create fresh GameSession (config-driven players from models.config.json)
      4. Assign unique archetypes via random shuffle (D-08)
      5. Create BudgetTracker + CircuitBreaker (reset per session — D-15, D-16)
      6. Build LLM decision fn closure
      7. Run session.run() with LLM decision_fn + broadcast_fn
      8. Store last result in Redis + broadcast game_status(running=False)
      9. Wait for next trigger
    """
    logger.info("Game loop started — waiting for viewer trigger (demand-gated)")

    while True:
        try:
            await start_event.wait()        # suspend until POST /api/game/start
            start_event.clear()             # consume the signal
            app_state.game_running = True   # SET BEFORE broadcast — Pitfall 2 race prevention
            await publish_game_status(broker, redis_client, running=True)

            session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
            archetypes = assign_archetypes(session.players)

            logger.info("[bold cyan]═══ NEW SESSION ═══[/bold cyan]")
            for p in session.players:
                arch = archetypes.get(p.id)
                model = session.player_models.get(p.id, "?")
                logger.info(
                    "  [cyan]%-18s[/cyan] %-20s  %d chips  [dim]%s[/dim]",
                    p.name, f"({arch.name})" if arch else "", p.chips, model,
                )

            budget = BudgetTracker()
            circuit = CircuitBreaker(threshold=3)

            decision_fn = make_llm_decision_fn(
                archetypes=archetypes,
                redis_client=redis_client,
                budget=budget,
                circuit=circuit,
                player_models=session.player_models,
            )
            broadcast_fn = partial(publish, redis_client)

            completed_hands = await session.run(
                n_hands=10, decision_fn=decision_fn, broadcast_fn=broadcast_fn
            )

            logger.info("[bold green]Session complete[/bold green]")
            for p in session.players:
                logger.info("  [green]%-18s[/green]  %d chips", p.name, p.chips)
            logger.info("Budget: %s", budget.summary())

            # Determine session winner (chip leader) and last hand result
            session_winner = max(session.players, key=lambda p: p.chips)
            last_hand = completed_hands[-1] if completed_hands else None
            winner_hand_name = last_hand.winner_hand if last_hand and last_hand.winner_hand else "last standing"

            await redis_client.set(
                GAME_LAST_RESULT_KEY,
                json.dumps({
                    "winnerName": session_winner.name,
                    "winnerOrg": session_winner.org,
                    "winnerHand": winner_hand_name,
                }),
                ex=SNAPSHOT_TTL,
            )
            app_state.game_running = False
            await publish_game_status(broker, redis_client, running=False)

        except asyncio.CancelledError:
            logger.info("Game loop cancelled — shutting down")
            raise  # MUST propagate — lifespan shutdown signal

        except Exception as exc:
            logger.error("Game loop error (will retry on next trigger): %s", exc, exc_info=True)
            app_state.game_running = False
            await asyncio.sleep(1)
