# LLM Poker Arena

## What This Is

A live, always-on poker arena where four AI models (GPT-4o, Gemini, Claude, Llama 3) compete at Texas Hold'em in a public Balatro-style visual experience. Viewers watch the same shared game in real time — like a Twitch stream, but the players are LLMs. Each model is assigned a random personality archetype per game, reveals its reasoning at every phase, and plays with human-like tendencies (aggression, paranoia, bluffing instincts) rather than cold calculation.

## Core Value

Spectators must be able to watch compelling, human-feeling AI poker with transparent reasoning — and the system must never run a game when nobody is watching.

## Requirements

### Validated

- ✓ Balatro-style UI shell (4 player seats, community cards, reasoning panel, Tweaks panel) — existing

### Active

- [ ] Correct Texas Hold'em rules: blinds, 4 betting rounds, proper hand rankings, standard betting flow
- [ ] Programmatic math engine: hand strength, pot odds, win probability computed in code (not by LLM)
- [ ] Human-like AI behavior: randomly assigned archetypes (e.g., aggressive, paranoid, conservative, chaotic) that drive decision biases
- [ ] Per-phase LLM reasoning: each AI narrates its thought process at pre-flop, flop, turn, river, showdown
- [ ] Shared game state: all viewers see the exact same game in real time via SSE
- [ ] Demand-triggered game loop: games only start when at least one viewer is present; idle when no viewers
- [ ] Scheduled intervals: configurable game-start schedule (env var or admin config) as the timing constraint alongside viewer presence
- [ ] Viewer betting: anonymous users can pick who they think will win before showdown; results shown after
- [ ] Live viewer count: show how many people are watching
- [ ] Future-ready archetype system: archetypes are data-driven so "joke cards" can override/extend them later

### Out of Scope

- User authentication — decided later; v1 is fully anonymous
- Side pots and all-in split pot logic — simplified flow for v1
- Viewer chat — not part of v1 reactions model
- Real money or token betting — spectator fun only
- Admin UI — config via env vars for now
- Joke cards / rule-twisting archetypes — future milestone

## Context

The Next.js frontend is already built and committed. It renders:
- 4 `PlayerSeat` components with hole cards, chip counts, action stamps
- A `ReasoningPanel` sidebar with streaming text entries per player per phase
- A community cards center area with 5 card slots
- A `TweaksPanel` for tempo/voice/atmosphere settings
- A static `MOCK_STATE` object that the real game engine will replace

The UI is decoupled from game logic — `Game.tsx` accepts a `theme` prop and currently renders mock data. The real game engine will feed live `GameState` into this component via React state or a context.

Real-time delivery uses Server-Sent Events (SSE) so that all connected clients receive the same stream of game state updates pushed from the server. The server is the single source of truth for game state.

Deployment target is a VPS. Architecture is partially decided: Next.js for frontend, SSE for real-time delivery. Backend game engine placement (Next.js API route vs separate process) is TBD.

## Constraints

- **Budget**: LLM API calls only happen when viewers are present — demand-triggered loop is mandatory
- **Stack**: Next.js frontend — locked. Backend architecture (separate process vs API routes) — TBD
- **Rules**: Standard Texas Hold'em, simplified flow — skip side pots and split pot edge cases for v1
- **Math**: Probabilities and hand evaluation must be computed programmatically, not by LLM inference
- **Hosting**: VPS — must work without Vercel/serverless. SSE requires persistent connections.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SSE for real-time sync | One-directional push, simple to host, works over HTTP without WebSocket infrastructure | — Pending |
| Math via programmatic functions | LLMs are weak at probability; offloading to code is faster, cheaper, and correct | — Pending |
| Demand-triggered game loop | Budget control — LLM API calls are expensive; no game runs without an audience | — Pending |
| Randomly assigned archetypes | Adds replayability and unpredictability; keeps each game feeling different | — Pending |
| v1 anonymous viewers | Auth adds complexity; validate engagement first, add persistence later | — Pending |
| Simplified poker rules (no side pots) | Side pots add significant complexity with 4-way AI play; core experience is unaffected | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-01 after initialization*
