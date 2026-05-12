"""
game.py — POST /api/game/start demand-gate endpoint.

D-05: Checks game_running flag and viewer_count before firing asyncio.Event.
D-08: Returns 409 if game already running, 503 if no viewers, 200 on success.
"""
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()


@router.post("/api/game/start")
async def start_game(request: Request):
    """
    Trigger a new game session. Enforces two server-side guards:
    1. No game currently running (409 if violated)
    2. At least one viewer connected (503 if violated)

    Sets app.state.start_event — the asyncio.Event that game_loop.py awaits.
    Returns {"started": True} on success.
    The game_status { running: true } SSE event will arrive separately via SSE channel.
    """
    if request.app.state.game_running:
        raise HTTPException(status_code=409, detail="Game already running")
    if request.app.state.broker.viewer_count < 1:
        raise HTTPException(status_code=503, detail="No viewers connected")

    request.app.state.start_event.set()
    return {"started": True}
