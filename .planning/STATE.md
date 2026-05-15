# Project State

## Current Phase

v0.5 milestone complete — planning next milestone (v1.0)

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-14)

**Core value:** Spectators watch compelling, human-feeling AI poker with transparent reasoning — system never runs without viewers.
**Current focus:** Planning v1.0 milestone (`/gsd-new-milestone`)

## Phase Status

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 1 | Backend Foundation | Complete ✓ | FastAPI scaffold, poker math engine, LiteLLM wiring — human UAT passed 2026-05-03 |
| 2 | Game State Machine | Complete ✓ | cards.py, models.py, game.py, session.py, tests — 5/5 SC verified 2026-05-03 |
| 3 | SSE Broadcast | Complete ✓ | EventBroker, publisher, SSE endpoint, 6 tests — SC-1–4 human verified 2026-05-06 |
| 4 | LLM Integration | Complete ✓ | ai/ package, SSE envelope, decision closure, game wiring, tests — human UAT passed 2026-05-09 |
| 5 | Frontend Wiring | Complete ✓ | Vite SPA scaffold, CORS + reasoning snapshot, useGameStream hook — 7/8 UAT passed, 1 gap fixed 2026-05-11 |
| 6 | Viewer Experience | Complete ✓ | 5/6 UAT passed, 1 skipped — human UAT passed 2026-05-14 |

## Accumulated Context

### Key Decisions Made

- Backend: Python (FastAPI) — not Node.js. LiteLLM as unified LLM interface.
- Architecture: FastAPI game engine (VPS persistent process) → SSE → Vite SPA (UI only)
- Frontend: Migrated from Next.js to Vite SPA during Phase 5 — all components were pure React
- LLM role: narration + decision selection only. All math (hand strength, pot odds, equity) computed in code.
- Game trigger: viewer-initiated ("Start a Game" button) — demand-gated server-side via asyncio.Event.
- Predictions: localStorage only in v1, no backend persistence.
- Poker rules: simplified — single main pot, no side pots.
- LLM calls: sequential per decision phase (not parallel) to start.
- Python 3.13.13 used — treys 0.1.8 pure Python, compatible with 3.13.
- config.py is provider-agnostic: player_models list[str] holds LiteLLM model strings via models.config.json.

### Architecture Notes

- FastAPI → Redis pub/sub → EventBroker (per-client asyncio.Queue) → SSE → Vite SPA
- SSE message IDs enable client-side replay on reconnect via EventSource native behavior.
- Archetype parameters (hand_looseness, raise_freq, bluff_freq, tilt_threshold) drive code-level decision biases.
- Budget protection: per-game spend tracked, circuit breaker per provider, 45s global timeout.
- Late-joiner snapshot served from Redis SNAPSHOT_KEY on first connect.

### Pending Todos

| File | Title | Area |
|------|-------|------|
| [2026-05-10-configurable-hands-per-session.md](./todos/pending/2026-05-10-configurable-hands-per-session.md) | Configurable number of hands per session | backend |
| [2026-05-10-optional-archetypes-mode.md](./todos/pending/2026-05-10-optional-archetypes-mode.md) | Optional archetypes mode for sessions | backend |

### Active Blockers

None.

### Deferred Items (v1.0+)

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

**Last action:** v0.5 milestone archived — all 6 phases complete, REQUIREMENTS.md removed, ROADMAP.md collapsed, git tagged v0.5. 2026-05-14
**Next action:** `/gsd-new-milestone` — define v1.0 requirements and roadmap
**Resumption note:** Stack: `docker compose up -d redis` + `cd backend && uv run uvicorn app.main:app --reload` + `cd frontend && npm run dev`.
