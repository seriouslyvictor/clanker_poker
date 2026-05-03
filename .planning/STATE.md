# Project State

## Current Phase
Phase 1 — Backend Foundation (executing — plan 01 complete)

## Project Reference
See: .planning/PROJECT.md

**Core value:** Spectators watch compelling, human-feeling AI poker with transparent reasoning — system never runs without viewers.
**Current focus:** Phase 1 executing — 1/3 plans complete

## Phase Status

| # | Phase | Status | Notes |
|---|-------|--------|-------|
| 1 | Backend Foundation | In progress (1/3 plans done) | FastAPI scaffold done; poker math engine next |
| 2 | Game State Machine | Not started | Full Hold'em flow runnable to console; no LLMs; mock decisions |
| 3 | SSE Broadcast | Not started | Real-time push to all clients; late-joiner snapshot; heartbeat |
| 4 | LLM Integration | Not started | 4 AI players, archetypes, guided decisions, streaming reasoning |
| 5 | Frontend Wiring | Not started | Replace MOCK_STATE with live SSE; auto-reconnect; CORS |
| 6 | Viewer Experience | Not started | Idle screen, Start button, anonymous winner predictions |

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

### Active Blockers
None — initialization complete.

### Deferred Items (v2)
- Live viewer count display
- Scheduled game intervals
- Prediction streak tracking
- Pre-game lobby with countdown
- Side pots / all-in handling
- Game history and replay (PostgreSQL)

## Session Continuity

**Last action:** Phase 1 Plan 01 executed — FastAPI scaffold with CORS, health endpoint, pydantic-settings config — 2026-05-03
**Next action:** Execute Plan 02 (poker math engine: treys + Monte Carlo equity + tests)
**Resumption note:** Plan 01 complete (commits a993ccc, 63f5415). backend/ has pyproject.toml, uv.lock, app/{config,main,api/health}.py. GET /health returns 200. Python 3.13.13 used without pin — treys compatible.
