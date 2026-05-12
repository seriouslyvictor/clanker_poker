# Roadmap — LLM Poker Arena

## Phases

- [x] **Phase 1: Backend Foundation** - FastAPI project, Python environment, poker math engine, LiteLLM wiring
- [x] **Phase 2: Game State Machine** - Full Texas Hold'em flow runnable to console with mock decisions
- [x] **Phase 3: SSE Broadcast** - Real-time game state pushed to all viewers; late-joiner snapshot; heartbeat
- [ ] **Phase 4: LLM Integration** - 4 AI players with archetypes, guided decisions, streaming reasoning, fallbacks
- [ ] **Phase 5: Frontend Wiring** - Vite SPA migration, SSE wiring (replace MOCK_STATE), auto-reconnect, CORS
- [ ] **Phase 6: Viewer Experience** - Idle screen, Start button, anonymous winner predictions

---

## Phase Details

### Phase 1: Backend Foundation
**Goal**: A working Python/FastAPI project with a provably correct poker math engine and all LLM provider credentials wired through LiteLLM.
**Depends on**: Nothing (first phase)
**Requirements**: POKER-03, POKER-04, INFRA-01, INFRA-02, INFRA-03
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — FastAPI scaffold: pyproject.toml, config.py, main.py, health endpoint
- [x] 01-02-PLAN.md — Poker math engine: treys hand evaluator + Monte Carlo equity calculator + tests
- [x] 01-03-PLAN.md — LiteLLM provider wiring: .env.example + provider integration tests

**Success Criteria** (what must be TRUE):
1. Running `python -m pytest` passes tests covering all 9 hand ranks, kicker tiebreakers, and board counterfeiting — no hand evaluation bug survives
2. The equity calculator returns hand strength score, pot odds, and approximate win probability given any hole cards + community cards, in under 100ms
3. A test script calls all 4 LLM providers through LiteLLM using env var credentials and receives a non-error response from each
4. The FastAPI app starts (`uvicorn main:app`) and returns 200 on a health check endpoint
5. All secrets (API keys, config) are sourced from environment variables — no hardcoded credentials anywhere in the codebase

**Notes**
Hand evaluation must use a battle-tested library (e.g., `treys` or equivalent) rather than hand-rolled logic. The equity calculator uses programmatic simulation — no LLM inference for math. INFRA-03 means `.env.example` documents every required variable; actual values never committed.

---

### Phase 2: Game State Machine
**Goal**: A complete Texas Hold'em game runs from pre-flop through showdown in code, with correct blinds, action order, chip tracking, and a winner — no UI, no LLMs, no network.
**Depends on**: Phase 1 (hand evaluator, chip math)
**Requirements**: POKER-01, POKER-02, POKER-05
**Plans:** 5 plans

Plans:
- [x] 02-01-PLAN.md — pyproject.toml asyncio_mode patch + cards.py treys conversion boundary
- [x] 02-02-PLAN.md — models.py Pydantic GameState, Player, Card, Action + BettingRoundState + DecisionFn
- [x] 02-03-PLAN.md — game.py single-hand engine: deal, betting rounds, showdown, mock_decision
- [x] 02-04-PLAN.md — session.py multi-hand session with dealer rotation and stack carry-over
- [x] 02-05-PLAN.md — test_game_engine.py covering all 5 success criteria

**Success Criteria** (what must be TRUE):
1. Running the game engine produces a complete hand: small blind posted, big blind posted, 2 hole cards dealt to each of 4 players, flop (3) → turn (1) → river (1) community cards dealt in correct order
2. Action order is correct: pre-flop starts left of big blind; post-flop starts left of dealer; fold/call/raise/check options are only offered when valid for that player's position and current bet
3. At showdown the correct winner is determined using the hand evaluator, and the pot (minus rake if any) is awarded — chip counts update correctly and no player goes below 0
4. A mock decision function (always call) can drive a full 10-hand session to completion without errors or infinite loops
5. Chip counts are consistent throughout: sum of all player stacks + pot always equals the starting total

**Notes**
No LLMs, no SSE, no HTTP in this phase — pure game logic. The mock decision function is the seam where LLMs will plug in during Phase 4. Console output is sufficient for verification. Simplified flow: single main pot, no side pots (v1 constraint).

---

### Phase 3: SSE Broadcast
**Goal**: All connected browser clients see the same game state in real time, pushed from the FastAPI server; late joiners get a full snapshot immediately; connections survive proxy buffering and network blips.
**Depends on**: Phase 2 (game state to broadcast)
**Requirements**: STREAM-01, STREAM-02, STREAM-03
**Plans:** 5 plans

Plans:
- [x] 03-01-PLAN.md — Infrastructure: docker-compose.yml (Redis), config.py extensions, .env.example, redis-py install
- [x] 03-02-PLAN.md — Engine callback: broadcast_fn parameter on run_hand() + session.py wire-through
- [x] 03-03-PLAN.md — Broadcast layer: broadcast/broker.py (EventBroker), broadcast/publisher.py, game_loop.py
- [x] 03-04-PLAN.md — SSE endpoint + lifespan: api/stream.py (GET /api/stream), expanded main.py
- [x] 03-05-PLAN.md — Tests + human UAT: test_sse.py (6 tests) + 3-browser verification checkpoint

**Success Criteria** (what must be TRUE):
1. Three browsers opened to the SSE endpoint simultaneously all show identical game state events within 100ms of each state change — no viewer sees a different game
2. A browser that connects mid-hand receives the full current game state snapshot as the first SSE event — it does not wait for the next state change to know what is happening
3. The SSE connection sends a heartbeat comment (`: ping`) every 5 seconds and includes the `X-Accel-Buffering: no` header — verified by inspecting raw HTTP response headers and watching the connection stay alive behind nginx
4. Game events carry monotonically increasing message IDs that clients can use to detect gaps in the event stream

**Notes**
This phase wires the Phase 2 game engine's state transitions into the SSE broadcast pipeline. The game still uses mock decisions — LLMs come in Phase 4. Test with 3 actual browser tabs, not just curl. STREAM-04 (client-side auto-reconnect) is deferred to Phase 5 because it lives in the Next.js frontend.

**UI hint**: yes

---

### Phase 4: LLM Integration
**Goal**: All 4 AI players make real decisions driven by archetype bias and math context, stream their reasoning token-by-token, and never halt the game on timeout or bad output.
**Depends on**: Phase 2 (decision seam), Phase 3 (SSE pipeline for streaming reasoning)
**Requirements**: AI-01, AI-02, AI-03, AI-04, AI-05, AI-06, INFRA-05
**Plans:** 5 plans

Plans:
- [ ] 04-01-PLAN.md — ai/ package foundation: archetypes, budget/circuit-breaker, Pydantic models + engine/models.py current_bet patch
- [ ] 04-02-PLAN.md — SSE envelope extension: publish_reasoning(), dual-channel broker, stream.py reasoning routing
- [ ] 04-03-PLAN.md — Core LLM decision module: prompt.py (build_system/user_prompt) + decision.py (make_llm_decision_fn, fallback, streaming)
- [ ] 04-04-PLAN.md — Game engine wiring: session.py config-driven players, game.py per-action broadcast + current_bet sync, game_loop.py LLM integration
- [ ] 04-05-PLAN.md — Tests + human UAT: test_llm_decisions.py + test_ai_prompt.py + live game verification

**Success Criteria** (what must be TRUE):
1. Each of the 4 LLM players (GPT-4o, Gemini, Claude, Llama 3) is called at every decision point and returns a structured action (fold / call / raise with amount) plus reasoning text — verified by watching a live game log
2. Each player is assigned a random archetype at game start and that archetype visibly influences behavior: the Gunslinger raises more than the Rock across a 10-hand session (not every hand, but measurably more)
3. The LLM receives a structured prompt containing hand strength, pot odds, win probability, available actions with amounts, current pot, community cards, and archetype description — no math is left for the LLM to calculate
4. If an LLM call times out (>8s), returns malformed JSON, or picks an invalid action, the game continues using the deterministic fallback — no game-halting errors in a 10-hand session that includes a simulated timeout
5. Reasoning text appears in the ReasoningPanel streaming token-by-token during decision — viewers see the AI "thinking" before the action is revealed
6. Per-game LLM spend is tracked and logged; a circuit breaker per provider prevents runaway cost if a provider starts erroring repeatedly

**Notes**
LLM calls are sequential per decision phase (all players in turn). This is intentionally slower than parallel but simpler and cheaper to start. The 8s global deadline covers all calls combined — individual call timeout is 2s with fallback. INFRA-05 (budget protection) lives here because it's inseparable from LLM orchestration. Player roster is config-driven (env vars / config file) — initial defaults are GPT-4o, Gemini, Claude, Llama 3, but any OpenAI-compatible or LiteLLM-supported model can be added without code changes. Design for N players, not hardcoded 4.

---

### Phase 5: Frontend Wiring
**Goal**: The Vite React SPA displays a live game — MOCK_STATE is gone, replaced by real game state arriving over SSE — and the connection is resilient to drops and proxy buffering.
**Depends on**: Phase 3 (SSE endpoint), Phase 4 (real game events)
**Requirements**: STREAM-04, INFRA-04
**Plans:** 3 plans

Plans:
- [ ] 05-01-PLAN.md — Vite SPA scaffold + full source migration from Next.js (frontend/ directory, fonts, path alias, assets)
- [ ] 05-02-PLAN.md — Backend CORS update: add localhost:5173 to cors_origins + .env.example documentation
- [ ] 05-03-PLAN.md — SSE wiring: useGameStream hook + Game.tsx/PokerApp.tsx live state (remove MOCK_STATE)

**Success Criteria** (what must be TRUE):
1. Opening the Vite app in a browser shows a live game in progress — player cards, community cards, chip counts, and pot all update in real time without any page refresh
2. Killing and restoring the network connection causes the client to auto-reconnect within 3 seconds and resume from the correct game position — no manual refresh required
3. The ReasoningPanel shows streaming reasoning text for each player at each decision phase, matching what the server is sending — no reasoning is lost or duplicated on reconnect
4. CORS is configured so the Vite origin (localhost:5173) can reach the FastAPI SSE endpoint and REST calls — verified by running both on separate ports locally and confirming no browser CORS errors
5. MOCK_STATE is completely removed from Game.tsx — the component only renders from live state

**Notes**
Scope expanded from original roadmap: Next.js is replaced by Vite React SPA (all components were already 'use client' pure React; no SSR, no API routes, no Next.js features in use). Migration is mechanical. SSE wiring is well-defined: named events (game_state, reasoning) consumed via EventSource.addEventListener. STREAM-04 auto-reconnect is satisfied by native EventSource behavior + backend late-joiner snapshot.

**UI hint**: yes

---

### Phase 6: Viewer Experience
**Goal**: Viewers land on an idle screen when no game is running, can start a game themselves, and can stake their prediction on who wins before showdown.
**Depends on**: Phase 5 (live game state in UI), Phase 3 (viewer presence tracking)
**Requirements**: VIEWER-01, VIEWER-02, VIEWER-03
**Plans:** 3 plans

Plans:
- [ ] 06-01-PLAN.md — Backend demand gate: broker.viewer_count + publish_game_status + game_loop asyncio.Event + POST /api/game/start + stream.py game_status snapshot
- [ ] 06-02-PLAN.md — Frontend routing: GameStatus type + useGameStream extension + IdleScreen.tsx + PokerApp routing (loading / idle / game)
- [ ] 06-03-PLAN.md — Prediction widget: StakeChip onClick + PredictionWidget.tsx (States A/B/C) + localStorage + Game.tsx wiring

**Success Criteria** (what must be TRUE):
1. When no game is running, the app shows an idle screen with project branding, the last game result (if any), and a "Start a Game" call-to-action button — not a blank page or error state
2. Clicking "Start a Game" causes a game to begin within 5 seconds of click; the button becomes disabled immediately on click and stays disabled while a game is in progress — a second viewer cannot double-start
3. Before showdown, each viewer can select which AI player they predict will win — the prediction UI disappears after they pick, and at showdown the result (correct / incorrect) is shown using localStorage to persist their choice
4. The idle → game → idle cycle completes cleanly: after showdown the UI returns to the idle screen showing the just-completed game's result

**Notes**
The "Start a Game" button triggers a POST to the FastAPI backend, which checks viewer presence before starting — the demand-triggered loop is enforced server-side, not client-side. Predictions are stored in localStorage only (no backend persistence in v1). The idle screen must handle the cold-start case where there is no previous game result to show.

**UI hint**: yes

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Backend Foundation | 3/3 | Complete | 2026-05-02 |
| 2. Game State Machine | 5/5 | Complete | 2026-05-03 |
| 3. SSE Broadcast | 5/5 | Complete | 2026-05-06 |
| 4. LLM Integration | 0/5 | Not started | - |
| 5. Frontend Wiring | 3/3 | Human UAT | - |
| 6. Viewer Experience | 0/3 | Not started | - |
