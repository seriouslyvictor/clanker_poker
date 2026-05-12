# Project State

## Current Phase
Phase 6 — Viewer Experience (context gathered, ready to plan)

## Project Reference
See: .planning/PROJECT.md

**Core value:** Spectators watch compelling, human-feeling AI poker with transparent reasoning — system never runs without viewers.
**Current focus:** Phase 6 — Viewer Experience

## Phase Status

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 1 | Backend Foundation | Complete ✓ | FastAPI scaffold, poker math engine, LiteLLM wiring — human UAT passed 2026-05-03 |
| 2 | Game State Machine | Complete ✓ | cards.py, models.py, game.py, session.py, tests — 5/5 SC verified 2026-05-03 |
| 3 | SSE Broadcast | Complete ✓ | EventBroker, publisher, SSE endpoint, 6 tests — SC-1–4 human verified 2026-05-06 |
| 4 | LLM Integration | Complete ✓ | ai/ package, SSE envelope, decision closure, game wiring, tests — human UAT passed 2026-05-09 |
| 5 | Frontend Wiring | Complete ✓ | Vite SPA scaffold, CORS + reasoning snapshot, useGameStream hook — 7/8 UAT passed, 1 gap fixed 2026-05-11 |
| 6 | Viewer Experience | Context ◆ | game_status SSE event, POST /api/game/start demand gate, prediction widget, Redis last result |

## Performance Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Hand evaluation speed | < 100ms | - |
| LLM decision timeout | 8s global / 2s per call | - |
| SSE reconnect time | < 3s | - |
| Game start after button click | < 5s | - |
| Heartbeat interval | 5s | - |

## Accumulated Context

### Key Decisions Made
- Backend: Python (FastAPI) — not Node.js. LiteLLM as unified LLM interface.
- Architecture: FastAPI game engine (VPS persistent process) → SSE → Next.js frontend (UI only)
- LLM role: narration + decision selection only. All math (hand strength, pot odds, equity) computed in code.
- Game trigger: viewer-initiated ("Start a Game" button) — demand-gated server-side.
- Predictions: localStorage only in v1, no backend persistence.
- Poker rules: simplified — single main pot, no side pots.
- LLM calls: sequential per decision phase (not parallel) to start.
- Python 3.13.13 used (no pin) — treys 0.1.8 pure Python, compatible with 3.13; uv python pin 3.12 not needed.
- config.py is provider-agnostic: player_models list[str] holds LiteLLM model strings; no per-provider API key fields in Settings.

### Architecture Notes
- Frontend is already built. Game.tsx renders MOCK_STATE. Phase 5 replaces it.
- SSE message IDs enable client-side replay on reconnect (Phase 5 client consumes them).
- Archetype parameters (hand_looseness, raise_freq, bluff_freq, tilt_threshold) drive code-level decision biases — LLM receives archetype description in prompt for narrative voice only.
- Budget protection: per-game spend tracked, circuit breaker per provider, 8s global deadline.

### Pending Todos

| File | Title | Area |
|------|-------|------|
| [2026-05-10-configurable-hands-per-session.md](./todos/pending/2026-05-10-configurable-hands-per-session.md) | Configurable number of hands per session | backend |
| [2026-05-10-optional-archetypes-mode.md](./todos/pending/2026-05-10-optional-archetypes-mode.md) | Optional archetypes mode for sessions | backend |

### Active Blockers
None — initialization complete.

### Deferred Items (v2)
- Live viewer count display
- Scheduled game intervals
- Prediction streak tracking
- Pre-game lobby with countdown
- Side pots / all-in handling
- Game history and replay (PostgreSQL)

### Quick Tasks Completed

| # | Description | Date | Directory |
|---|-------------|------|-----------|
| 260503-01 | Centralized AI model config (models.config.json) | 2026-05-03 | [260503-01-centralized-model-config](./quick/260503-01-centralized-model-config/) |
| 260509-01 | Rich colored logging + LLM budget increase (max_tokens 5000) | 2026-05-09 | [260509-01-rich-logging-llm-budget](./quick/260509-01-rich-logging-llm-budget/) |

## Session Continuity

**Last action:** Phase 6 context gathered — 2026-05-12
**Next action:** `/gsd-plan-phase 6` (Viewer Experience)
**Resumption note:** Stack: `docker compose up -d redis` + `cd backend && uv run uvicorn app.main:app --reload` + `cd frontend && npm run dev`. Phase 5 complete (3/3 plans, 7/8 UAT passed, 1 gap fixed). Phase 6 context captured in `.planning/phases/06-viewer-experience/06-CONTEXT.md` — key decisions: game_status SSE event for idle detection, asyncio.Event demand gate with POST /api/game/start, per-hand prediction widget (floating overlay), Redis game:last_result for shared last winner.
