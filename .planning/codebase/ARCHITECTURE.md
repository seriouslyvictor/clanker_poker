# Architecture

**Analysis Date:** 2026-05-02

## Pattern Overview

**Overall:** Three-tier event-driven architecture with a server-authoritative game engine

**Key Characteristics:**
- Game state lives entirely on the server (FastAPI); Next.js frontend is a pure viewer/renderer
- Real-time delivery via Server-Sent Events (SSE) — unidirectional push to all browser clients
- Demand-triggered game loop — game runs only when at least one viewer is connected (budget protection)
- LLMs handle narration and decision selection only; all poker math is programmatic
- Player roster and models are config-driven via env vars; no hardcoded providers

## Layers

**Frontend Layer (Existing — Next.js):**
- Purpose: Render game state received over SSE; display AI reasoning panel; settings tweaks
- Location: `clanker_poker/app/`
- Contains: React client components, layout, global CSS, no business logic
- Depends on: FastAPI SSE endpoint (Phase 5+); currently renders `MOCK_STATE` in `Game.tsx`
- Used by: Viewers (browsers)
- State: Entirely driven by SSE events; local UI state only (`useState` for tweaks panel, history popover)

**Backend Game Engine Layer (Planned — FastAPI):**
- Purpose: Texas Hold'em game state machine, LLM orchestration, SSE broadcast, viewer presence tracking
- Location: `clanker_poker/backend/app/`
- Contains: `main.py` (FastAPI app), `config.py` (Settings), `api/` (HTTP routes), `engine/` (poker logic)
- Depends on: Redis (game state pub/sub), LiteLLM (LLM providers)
- Used by: Next.js frontend (SSE consumer), browser clients (viewer betting REST calls)

**Poker Math Engine (Planned — pure functions):**
- Purpose: Hand evaluation, pot odds, win probability — no LLM involvement
- Location: `clanker_poker/backend/app/engine/poker_math.py`
- Contains: `treys` wrapper + custom Monte Carlo equity calculator (~1000 samples)
- Depends on: `treys` library only
- Used by: Game state machine at every decision point; results injected into LLM prompts

**Redis Pub/Sub Layer (Phase 3+):**
- Purpose: Decouple game engine from HTTP layer; distribute game state to all SSE subscribers
- Location: External Redis instance
- Contains: `game:{gameId}:state` (current game), `viewers:count`, `game-updates` pub/sub channel
- Depends on: Redis server
- Used by: Game engine (publisher), FastAPI SSE route (subscriber)

## Data Flow

**Game Decision Cycle (Phase 4+):**

1. `GameLoopController` triggers a phase tick
2. `GamePhaseOrchestrator` determines which player must act
3. `PokerMathEngine.calculate_equity(hole_cards, community_cards)` returns `{hand_strength, pot_odds, win_probability}`
4. `LLMOrchestrator.call_llm(player, context, archetype)` sends structured prompt to provider via LiteLLM
5. LLM streams reasoning tokens — each chunk published to `game-updates` Redis channel as `reasoning_update` event
6. LLM response parsed for action (`fold|call|raise|check`) + amount; fallback used if malformed or timeout >8s
7. `GameEngine.apply_action(player, action, amount)` updates game state
8. Full state published to `game-updates` Redis channel
9. FastAPI SSE route reads from Redis, writes `data: {JSON}\n\n` to all open SSE connections
10. Browser clients update React state; `Game.tsx` re-renders

**Viewer Connection Lifecycle:**

1. Browser opens `GET /api/game/stream` (EventSource)
2. `SSEConnectionManager` registers connection, sends full current state snapshot as first event
3. `ViewerPresenceManager.on_viewer_connected()` — if viewer count was 0, starts `GameLoopController`
4. Heartbeat ping every 5s keeps connection alive through proxies
5. On disconnect: `ViewerPresenceManager.on_viewer_disconnected()` — if last viewer, pauses game loop after current phase

**SSE Message Format:**

```
id: {monotonic_seq}
data: {"type":"gameState","phase":"FLOP","pot":175,"players":[...],...}\n\n

id: {seq}
data: {"type":"reasoningUpdate","playerId":"claude","text":"I see a strong...","streaming":true}\n\n

: ping
```

**State Management:**
- Game state: authoritative in FastAPI process (in-memory singleton) + Redis mirror (TTL 24h)
- Frontend state: pure reflection of last SSE event via `useState`; no local game logic
- Settings (tempo/voice/atmosphere): React `useState` in `PokerApp.tsx`; passed as props to `Game.tsx`
- Viewer predictions: `localStorage` only (Phase 6); no backend persistence in v1

## Key Abstractions

**GameState (TypeScript contract — `clanker_poker/app/_components/types.ts`):**
- Purpose: Defines the JSON shape the backend SSE stream must produce for the frontend to consume
- Examples: `clanker_poker/app/_components/types.ts`
- Pattern: `GameState`, `Player`, `ReasoningEntry`, `Card` interfaces; backend Python must serialize to match these shapes

**MOCK_STATE (current frontend placeholder — `clanker_poker/app/_components/Game.tsx` line 23):**
- Purpose: Static scaffold enabling UI development before backend exists
- Pattern: `const MOCK_STATE: GameState = {...}` — replaced by live SSE state in Phase 5
- Note: Remove entirely in Phase 5 (`MOCK_STATE` must not exist in `Game.tsx` post-Phase 5)

**MODELS constant (`clanker_poker/lib/constants.ts`):**
- Purpose: Player roster definition — `id`, `name`, `org`, `color`, `deck` for each AI player
- Pattern: `as const` typed array; `ModelId` union type derived from it
- Note: Frontend renders from this; backend player config is env-driven (`PLAYER_MODELS`); must remain in sync

**THEMES constant (`clanker_poker/lib/constants.ts`):**
- Purpose: Visual atmosphere variants (felt/neon/noir) — `tableBg`, `panelBg`, `accent`, `cardBack`, etc.
- Pattern: `Record<AtmosphereMode, {...}>` — selected by `settings.atmosphere`, passed as `theme` prop to `Game`

**Settings state (`clanker_poker/app/_components/PokerApp.tsx`):**
- Purpose: User-configurable game presentation — `tempo` (cinematic/normal/turbo), `voice` (analytical/balanced/theatrical), `atmosphere` (felt/neon/noir)
- Pattern: `useState<Settings>` in `PokerApp`, passed to `TweaksPanel` via props; `tempo` drives `TEMPO_MULT` timing multipliers

## Entry Points

**Frontend App Entry:**
- Location: `clanker_poker/app/page.tsx`
- Triggers: Next.js App Router page render
- Responsibilities: Renders `<PokerApp />` — single root component

**Frontend Layout:**
- Location: `clanker_poker/app/layout.tsx`
- Triggers: Wraps all pages
- Responsibilities: Google Fonts (Press Start 2P, VT323, Rajdhani), metadata, body font var

**Backend App Entry (planned):**
- Location: `clanker_poker/backend/app/main.py`
- Triggers: `uv run uvicorn app.main:app` from `backend/`
- Responsibilities: FastAPI instance, CORS middleware, router registration, lifespan (Redis connect/disconnect Phase 3)

**Backend Config Entry:**
- Location: `clanker_poker/backend/app/config.py`
- Pattern: `get_settings() -> Settings` with `@lru_cache`; `Settings(BaseSettings)` reads from `.env` via pydantic-settings

## Error Handling

**Strategy:** Defensive fallback at LLM decision point; no game-halting errors

**Patterns:**
- LLM timeout (>8s global per phase): fall back to deterministic action based on hand strength + archetype bias
- LLM malformed response: parse with regex; fallback to `call` on parse failure
- LLM provider error: circuit breaker per provider (Phase 4 — INFRA-05); log and use fallback
- SSE client disconnect: clean up connection from active set; stop game if last viewer
- Frontend SSE disconnect: auto-reconnect via EventSource API with message ID replay (Phase 5)

## Cross-Cutting Concerns

**Logging:** FastAPI/uvicorn default request logs; LiteLLM provider errors; per-game LLM spend (Phase 4)
**Validation:** pydantic-settings for config; LLM response validation in `parse_action()`; chip math validated (no player below 0)
**Authentication:** None — v1 fully anonymous; viewer predictions in localStorage only
**Budget protection:** 8s global deadline per decision phase; circuit breaker per LLM provider; game loop pauses when no viewers
**Poker rules simplification:** Single main pot only (no side pots); v1 constraint documented in REQUIREMENTS.md

## Archetype System

**Purpose:** Assigns each AI player a random personality at game start, driving biased decision-making
**Pattern:** `ArchetypeEngine` maps archetype name → bias parameters (`hand_looseness`, `raise_freq`, `bluff_freq`, `tilt_threshold`)
**LLM integration:** Archetype description injected into LLM prompt (narration voice only); bias parameters influence code-level decision weighting
**Defined archetypes:** Gunslinger (aggressive raiser), Rock (frequent folder), Grinder (tight-solid), Chaotic Optimist (calls anything)
**Extensibility:** Data-driven design allows "joke card" archetypes to be added later without code changes

---

*Architecture analysis: 2026-05-02*
