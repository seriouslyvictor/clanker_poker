# Requirements — LLM Poker Arena

## v1 Requirements

### POKER — Texas Hold'em Engine

- [ ] **POKER-01**: Game runs standard Texas Hold'em flow — small blind, big blind, pre-flop deal, flop (3 cards), turn (1 card), river (1 card), showdown
- [ ] **POKER-02**: Correct action order enforced each round — left of dealer / left of big blind for pre-flop, clockwise thereafter; fold/call/raise/check options presented correctly
- [ ] **POKER-03**: Hand evaluation covers all 9 ranks with correct kicker tiebreakers — pair, two pair, trips, straight, flush, full house, quads, straight flush, royal flush; board counterfeiting handled
- [ ] **POKER-04**: Programmatic equity calculator — hand strength score, pot odds, approximate win probability computed in code and surfaced as structured data to the LLM at decision time
- [ ] **POKER-05**: Chip tracking across a full game — blinds deducted, bets added to pot, pot awarded to winner at showdown; no player goes below 0

### AI — Behavior & Reasoning

- [ ] **AI-01**: N configurable LLM players (default 4) — player roster defined in config/env vars, not hardcoded; initial defaults are GPT-4o, Gemini, Claude, Llama 3; any OpenAI-compatible or LiteLLM-supported model can be swapped in without code changes; players called sequentially per decision phase
- [ ] **AI-02**: Random archetype assigned to each player at game start — archetype defines personality label + behavioral bias parameters (hand looseness, raise frequency, bluff frequency, tilt threshold)
- [ ] **AI-03**: At each decision point, LLM receives structured math context — hand strength, pot odds, win probability, available actions (fold / call / raise / reraise with amounts), current pot, community cards, archetype description — and responds with a structured decision + reasoning text
- [ ] **AI-04**: Code validates LLM decision response — if response is malformed, times out (>8s), or picks an invalid action, fallback to deterministic decision based on hand strength + archetype bias
- [ ] **AI-05**: Reasoning text streams token-by-token into the ReasoningPanel for each player at each phase — viewers see the AI "thinking" in real time
- [ ] **AI-06**: Each archetype produces visibly different play style — Gunslinger raises aggresively, Rock folds often, Grinder plays tight-but-solid, Chaotic Optimist calls anything; differences must be legible to non-poker-expert viewers

### STREAM — Real-Time Broadcast

- [ ] **STREAM-01**: Python backend (FastAPI) serves game state via SSE — single endpoint pushes incremental game events to all connected clients; all viewers see identical state
- [ ] **STREAM-02**: Late joiners receive full current game state snapshot immediately on connection — no partial state, no waiting for next event
- [ ] **STREAM-03**: SSE connection includes 5s heartbeat and `X-Accel-Buffering: no` header — survives proxy buffering and corporate firewalls
- [ ] **STREAM-04**: Client auto-reconnects on disconnect and replays missed events via message IDs — viewer experience is seamless on network blips

### VIEWER — Presence & Interaction

- [ ] **VIEWER-01**: Idle screen displayed when no game is running — shows project branding, last game result (if any), and a "Start a Game" call-to-action button
- [ ] **VIEWER-02**: Any viewer can click "Start a Game" on the idle screen — game starts within 5 seconds of click; button is disabled once a game is in progress
- [ ] **VIEWER-03**: Anonymous winner prediction — before showdown, each viewer can pick which AI they think will win; result (correct/incorrect) shown at showdown; stored in localStorage

### INFRA — Backend & Deployment

- [ ] **INFRA-01**: Python backend (FastAPI) is the game engine — owns game state, LLM orchestration, SSE broadcast, and viewer presence tracking; runs as a persistent process on VPS
- [ ] **INFRA-02**: LiteLLM used as unified interface for all 4 LLM providers — single call pattern regardless of provider; fallback chain configurable via env vars
- [ ] **INFRA-03**: All API keys and configuration via environment variables — `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_AI_API_KEY`, `LITELLM_*`, game schedule config
- [ ] **INFRA-04**: Next.js frontend communicates with Python backend via its public SSE endpoint and REST calls — CORS configured; no server-side Next.js proxying required
- [ ] **INFRA-05**: Budget protection — per-game LLM spend tracked; global 8s deadline per decision phase across all 4 LLM calls; circuit breaker per provider

## v2 Requirements (Deferred)

- Pre-game lobby with countdown — gather viewers before game starts; show who else is waiting
- Live viewer count display — social proof while watching
- Prediction streak tracking — localStorage streak counter across games
- Scheduled game intervals — auto-start on a timer when viewers arrive
- Side pots and all-in handling — correct split pot logic for all-in scenarios
- Game history and replay — persist completed games to PostgreSQL; allow replay
- Viewer bet resolution leaderboard — track correct predictions across games

## Out of Scope

- **User authentication** — v1 is fully anonymous; no accounts, no persistent identity
- **Real money / tokens** — spectator engagement only; no financial mechanics
- **Viewer chat** — predictions/reactions are sufficient for v1 engagement
- **Joke cards / rule-twisting archetypes** — future milestone; archetype system is designed to support it
- **Multi-table / concurrent games** — single shared game only for v1
- **Vercel / serverless deployment** — SSE requires persistent connections; VPS only

## Key Open Decision: Backend Language

The original stack research assumed Node.js + PM2. User preference is Python backend for its more mature LLM ecosystem (LiteLLM, native async streaming). This changes the implementation language but not the architectural patterns.

**Decision:** Python (FastAPI) backend, Next.js frontend (existing, locked).
**Implication:** Stack research (STACK.md) patterns remain valid; implementation uses Python equivalents. Phase 1 planning should include Python environment setup and FastAPI SSE validation.

## Traceability

| REQ-ID | Phase | Status |
|--------|-------|--------|
| POKER-01 | Phase 2 | Not started |
| POKER-02 | Phase 2 | Not started |
| POKER-03 | Phase 1 | Not started |
| POKER-04 | Phase 1 | Not started |
| POKER-05 | Phase 2 | Not started |
| AI-01 | Phase 4 | Not started |
| AI-02 | Phase 4 | Not started |
| AI-03 | Phase 4 | Not started |
| AI-04 | Phase 4 | Not started |
| AI-05 | Phase 4 | Not started |
| AI-06 | Phase 4 | Not started |
| STREAM-01 | Phase 3 | Not started |
| STREAM-02 | Phase 3 | Not started |
| STREAM-03 | Phase 3 | Not started |
| STREAM-04 | Phase 5 | Not started |
| VIEWER-01 | Phase 6 | Not started |
| VIEWER-02 | Phase 6 | Not started |
| VIEWER-03 | Phase 6 | Not started |
| INFRA-01 | Phase 1 | Not started |
| INFRA-02 | Phase 1 | Not started |
| INFRA-03 | Phase 1 | Not started |
| INFRA-04 | Phase 5 | Not started |
| INFRA-05 | Phase 4 | Not started |

---
*Created: 2026-05-01 after requirements gathering*
*Traceability updated: 2026-05-01 after roadmap creation*
