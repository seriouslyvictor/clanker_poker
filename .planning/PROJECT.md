# LLM Poker Arena

## What This Is

A live, always-on poker arena where four AI models (GPT-4o, Gemini, Claude, Llama 3) compete at Texas Hold'em in a public Balatro-styled browser experience. Viewers watch a shared real-time game via SSE — like a Twitch stream where the players are LLMs. Each model gets a random personality archetype per game, streams its reasoning token-by-token at every decision phase, and plays with human-like tendencies driven by code-level bias parameters. Viewers can start games on demand and stake anonymous predictions on who wins.

## Core Value

Spectators must be able to watch compelling, human-feeling AI poker with transparent reasoning — and the system must never run a game when nobody is watching.

## Current State

**Shipped: v0.5 MVP** (2026-05-14)

Full stack is running:
- **Backend:** FastAPI + Redis + LiteLLM | `docker compose up -d redis && cd backend && uv run uvicorn app.main:app --reload`
- **Frontend:** Vite SPA at `http://localhost:5173` | `cd frontend && npm run dev`
- **Stack:** ~41,500 LOC added across 6 phases (218 files). Python 3.13, FastAPI 0.136, Vite 8, React 19.

All 23 v1 requirements validated. System is fully functional end-to-end.

## Requirements

### Validated (v0.5)

- ✓ Correct Texas Hold'em rules: blinds, 4 betting rounds, proper hand rankings, standard betting flow — v0.5
- ✓ Programmatic math engine: hand strength, pot odds, win probability computed in code (not by LLM) — v0.5
- ✓ Human-like AI behavior: randomly assigned archetypes (Gunslinger, Rock, Grinder, Chaotic Optimist) that drive decision biases — v0.5
- ✓ Per-phase LLM reasoning: each AI narrates its thought process at pre-flop, flop, turn, river, showdown — v0.5
- ✓ Shared game state: all viewers see the exact same game in real time via SSE — v0.5
- ✓ Demand-triggered game loop: games only start when at least one viewer is present; idle when no viewers — v0.5
- ✓ Viewer predictions: anonymous users can pick who they think will win; results shown at showdown — v0.5
- ✓ Idle screen with last game result and Start button — v0.5
- ✓ Budget protection: per-game spend tracked, circuit breaker per provider, 8s global deadline — v0.5
- ✓ Config-driven player roster: any OpenAI-compatible model swappable via models.config.json — v0.5
- ✓ Balatro-style UI shell (4 player seats, community cards, reasoning panel) — existing + v0.5

### Active (v1.0 targets)

- [ ] Live viewer count display — social proof while watching
- [ ] Scheduled game intervals — auto-start on a timer when viewers arrive
- [ ] Prediction streak tracking — localStorage streak counter across games
- [ ] Pre-game lobby with countdown — gather viewers before game starts
- [ ] Side pots and all-in handling — correct split pot logic for all-in scenarios
- [ ] Game history and replay — persist completed games; allow replay

### Out of Scope

- User authentication — v1 is fully anonymous; validate engagement first
- Real money / tokens — spectator engagement only; no financial mechanics
- Viewer chat — predictions/reactions are sufficient for v1 engagement
- Joke cards / rule-twisting archetypes — archetype system is designed to support it later
- Multi-table / concurrent games — single shared game only
- Vercel / serverless deployment — SSE requires persistent connections; VPS only
- Admin UI — config via env vars for now

## Constraints

- **Budget**: LLM API calls only happen when viewers are present — demand-triggered loop is mandatory
- **Stack**: Vite React SPA (migrated from Next.js during Phase 5). FastAPI backend on VPS.
- **Rules**: Standard Texas Hold'em, simplified — no side pots, no split pot edge cases in v1
- **Math**: Probabilities and hand evaluation computed programmatically, never by LLM inference
- **Hosting**: VPS — persistent process required for SSE. No Vercel/serverless.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SSE for real-time sync | One-directional push, simple to host, works over HTTP without WebSocket | ✓ Works well — late-joiner snapshot + heartbeat solves all proxy issues |
| Math via programmatic functions | LLMs weak at probability; offloading is faster, cheaper, correct | ✓ Correct — LLM prompt includes pre-computed values, no hallucinated math |
| Demand-triggered game loop | Budget control — no LLM calls without an audience | ✓ Enforced server-side via asyncio.Event + viewer_count |
| Randomly assigned archetypes | Adds replayability; each game feels different | ✓ Code-level bias params drive decisions; LLM provides narrative voice only |
| v1 anonymous viewers | Auth adds complexity; validate engagement first | ✓ localStorage predictions work well; no auth friction |
| Simplified poker rules (no side pots) | Side pots add complexity with 4-way AI play; core experience unaffected | ✓ No issues in UAT |
| Python (FastAPI) backend | LiteLLM ecosystem, native async streaming | ✓ Strong choice — litellm + asyncio + SSE all work cleanly |
| Frontend: Next.js → Vite SPA | All components were 'use client' pure React; no SSR/API routes in use | ✓ Correct — migration was mechanical; Vite simpler for pure SPA |
| Sequential LLM calls (not parallel) | Simpler, cheaper to start | ✓ Acceptable in v0.5; may revisit for latency in v1.0 |
| Predictions: localStorage only | No backend persistence in v1 | ✓ Sufficient for v0.5 engagement |

## Context

Shipped v0.5 with 6 phases, 24 plans, 218 files, ~41,500 LOC.
Tech stack: Python 3.13 / FastAPI 0.136 / LiteLLM 1.83 / Redis / Vite 8 / React 19 / TypeScript.
UAT: All 6 phases human-verified. Phase 6 UAT: 5/6 passed, 1 skipped (503 path — not triggerable in local dev).

**Startup:** `docker compose up -d redis` → `cd backend && uv run uvicorn app.main:app --reload` → `cd frontend && npm run dev`

---
*Last updated: 2026-05-14 after v0.5 milestone*
