# Research Summary — LLM Poker Arena

## Recommended Stack

- **Next.js 15** (App Router, SSE via ReadableStream + `force-dynamic`)
- **Redis 7 + ioredis 5** — Pub/Sub for game state broadcast; atomic Lua scripts for concurrent writes
- **pokersolver** — hand evaluation; battle-tested in production (CasinoRPG); explicit `.winners()` API
- **Vercel AI SDK 5** — LLM provider abstraction with streaming support across OpenAI / Anthropic / Google
- **PM2 5** — manages Next.js + game engine as separate processes on VPS
- **PostgreSQL** (Phase 4) — persistent game history, viewer bets, replay

## Architecture Overview

Three tiers, strictly separated:

1. **Game Engine** — `GameEngine`, `GamePhaseOrchestrator`, `LLMOrchestrator`, `PokerMathEngine`, `ArchetypeEngine` — publishes to Redis Pub/Sub. Runs as in-process singleton (migrate to Worker only if crashes impact web server).
2. **Broadcast Layer** — `SSEConnectionManager`, `ViewerPresenceManager`, `BroadcastEventBus` — fans Redis events out to all SSE clients.
3. **API Routes** — stateless Next.js routes: `GET /api/games/:id/sse`, `POST /api/games/create`, `GET /api/games/:id/state`, `POST /api/viewers/bet`.

**Critical constraint:** VPS only. SSE requires persistent connections — Vercel/serverless is incompatible.

## Table Stakes Features (v1 Must-Haves)

- Correct Texas Hold'em (4 betting rounds, hand rankings with kicker tiebreakers, showdown)
- All viewers see identical real-time game state via SSE
- Live viewer count (social proof + demand gate trigger)
- Per-phase AI reasoning streaming to ReasoningPanel
- Demand-triggered game loop (games only start when viewerCount ≥ 1)
- Anonymous viewer predictions (pick winner before showdown)

## Texas Hold'em Rules Checklist

**Hand Rankings** (high → low): Royal Flush, Straight Flush, Four of a Kind, Full House, Flush, Straight, Three of a Kind, Two Pair, One Pair, High Card

**Kicker rules:**
- Full house has NO kickers (determined entirely by rank)
- Pair / trips / two-pair: compare kickers high-to-low until tie breaks
- Board counterfeiting: if best 5 cards are all community, hole cards don't contribute kickers
- Nut-low possible in split scenarios

**Betting structure:**
- Pre-flop, flop, turn, river — 4 rounds
- Blinds set minimum bet; no-limit betting
- All-in allowed
- v1 simplified: single main pot only — no side pots

**Showdown:** best 5-card hand from any combination of 2 hole + 5 community cards wins

## AI Personality System

Math decisions (fold / call / raise) come from **code** (hand strength + archetype bias parameters). LLMs only **narrate** reasoning. This prevents analysis paralysis and controls cost.

Archetypes are randomly assigned per game and shown to viewers:

| Archetype | hand_looseness | raise_freq | bluff_freq | Viewer Hook |
|-----------|---------------|------------|------------|-------------|
| Aggressive Gunslinger | 0.75 | 0.65 | 0.45 | "Will they overextend?" |
| Paranoid Rock | 0.25 | 0.20 | 0.05 | "When will they finally move?" |
| Conservative Grinder | 0.40 | 0.35 | 0.20 | "Safe but dangerous late" |
| Chaotic Optimist | 0.80 | 0.75 | 0.70 | "Anything can happen" |

Parameters drive decision biases in code. Prompts reflect the archetype in narrative voice.

## Critical Pitfalls to Avoid

1. **LLM cost spiral** — No demand gate = runaway API bills. Prevention: `viewerCount ≥ 1` check before every game, per-game budget cap ($5–$10), global 8s deadline across 4 LLM calls, circuit breaker per provider.
2. **SSE proxy buffering** — Corporate proxies buffer streams → 20–60s delays or frozen state. Prevention: `X-Accel-Buffering: no` header, 5s heartbeat, message IDs for replay on reconnect.
3. **Race conditions on game state** — Concurrent LLM/betting writes corrupt state (negative chips, duplicate cards). Prevention: single event channel, atomic snapshots, serial message queue.
4. **LLM timeout mid-game** — One of 4 calls times out; game halts. Prevention: 2s per-call timeout, fallback to deterministic decision, schema validation on response.
5. **Hand eval bugs** — Kicker comparisons wrong, flush vs straight-flush ordering missed. Prevention: use `pokersolver`, test all 9 hand ranks + counterfeiting + split scenarios.
6. **Archetype decay** — After 20–30 games reasoning becomes mechanical/repetitive. Prevention: fresh context per game, lean prompts, controlled phrasing variation.

## Build Order

1. **PokerMathEngine** — pure functions: deck, shuffle, hand eval, pot odds, win probability. No LLMs. Test with 100K hand samples.
2. **GameEngine + GamePhaseOrchestrator** — state machine (pre-flop → flop → turn → river → showdown) with mock decisions. Runnable to console before any real-time or LLM work.
3. **SSE broadcast + ViewerPresenceManager** — Redis Pub/Sub fan-out; viewer join/leave tracking; demand-triggered start/stop. Test: 3 browsers see identical state.
4. **LLM integration + ArchetypeEngine** — 4 LLM clients, sequential calls (≈48s/decision), archetype bias applied to decision thresholds, reasoning streams to UI. MVP complete here.
5. **PostgreSQL persistence** — game history, phase logs, viewer bet resolution, replay.
6. **Scale & optimization** — parallel LLM calls (if budget allows), separate worker process, clustering.

## Open Decisions

| Decision | Recommendation |
|----------|---------------|
| LLM parallelization | Start sequential; migrate if latency becomes an issue |
| Worker vs in-process engine | Start in-process; separate only if crashes impact web server |
| Game schedule trigger | Demand-presence gated + configurable interval via env var |
| LLM fallback chain | Deterministic (code-based) if all 4 time out |
| Viewer auth | Defer — v1 fully anonymous (localStorage for predictions) |
| Side pots | Defer to v2 |

---
*Generated: 2026-05-01 — synthesized from STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md*
