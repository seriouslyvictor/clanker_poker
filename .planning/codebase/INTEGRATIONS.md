# External Integrations

**Analysis Date:** 2026-05-02

## APIs & External Services

**LLM Providers (4 AI players):**
- OpenAI GPT-4o — player "gpt4", org "OpenAI", color #10a37f
  - SDK/Client: `openai` 6.35.0 (frontend, current); `litellm` with model string `"openai/gpt-4o"` (backend, planned)
  - Auth: `OPENAI_API_KEY` env var (read by LiteLLM from `os.environ`)
- Google Gemini — player "gemini", org "Google", color #4285f4
  - SDK/Client: `@google/generative-ai` 0.24.1 (frontend, current); `litellm` with `"gemini/gemini-2.0-flash"` (backend, planned)
  - Auth: `GOOGLE_AI_API_KEY` env var
- Anthropic Claude — player "claude", org "Anthropic", color #d97757
  - SDK/Client: `@anthropic-ai/sdk` 0.92.0 (frontend, current); `litellm` with `"anthropic/claude-3-5-haiku-20241022"` (backend, planned)
  - Auth: `ANTHROPIC_API_KEY` env var
- Meta Llama 3 — player "llama", org "Meta", color #a855f7
  - SDK/Client: `litellm` with `"ollama_chat/llama3"` (backend, planned)
  - Auth: Local Ollama instance or remote API endpoint

**LiteLLM Abstraction (Backend — Phase 1+):**
- Unified interface for all 4 providers via single call pattern
- Provider roster is config-driven: `PLAYER_MODELS` env var overrides defaults
- Any OpenAI-compatible or LiteLLM-supported model can be added without code changes
- 8-second global timeout per decision phase (`LLM_TIMEOUT_SECONDS` setting)
- Circuit breaker per provider for budget protection (Phase 4)

## Data Storage

**Databases:**
- Redis — transient game state (Phase 3+)
  - Connection: `REDIS_URL` env var (e.g., `redis://localhost:6379`)
  - Client: `ioredis` 5.x (Node.js) or `aioredis` (Python, TBD for Phase 3)
  - Data: current game state (`game:{gameId}:state`), viewer count (`viewers:count`), active games set
  - TTL: 24 hours on game keys; auto-cleanup on game end
  - Pattern: Pub/Sub on channel `game-updates`; atomic Lua scripts for state mutations
- PostgreSQL — persistent game history (deferred to v2)
  - Schema planned: `games`, `game_phases`, `player_decisions`, `viewer_bets` tables
  - Client: TBD (psycopg3 or asyncpg for Python backend)

**File Storage:**
- Local filesystem only — card deck images in `clanker_poker/public/assets/`
  - `deck-blue.png`, `deck-yellow.png`, `deck-red.png`, `deck-ghost.png`, `deck-plasma.png`

**Caching:**
- Redis (Phase 3+) — game state cache with TTL; viewer count

## Authentication & Identity

**Auth Provider:**
- None — v1 is fully anonymous; no user accounts, no persistent identity
- Viewer predictions stored in browser localStorage only (Phase 6)

## Monitoring & Observability

**Error Tracking:**
- None configured

**Logs:**
- FastAPI default request logs via uvicorn
- LiteLLM provider errors logged at decision point
- Per-game LLM spend tracked and logged (Phase 4 — INFRA-05)
- No log aggregation service configured

## CI/CD & Deployment

**Hosting:**
- VPS — required for persistent SSE connections (Vercel/serverless explicitly ruled out)
- PM2 manages two processes: `next-app` (Next.js) and `game-engine` (Python FastAPI)
- Nginx reverse proxy required; must set `X-Accel-Buffering: no` on SSE endpoint

**CI Pipeline:**
- None detected

## Environment Configuration

**Required env vars:**
- `PLAYER_MODELS` — JSON list of LiteLLM model strings (defaults to gpt-4o, claude, gemini, llama3)
- `OPENAI_API_KEY` — OpenAI provider key
- `ANTHROPIC_API_KEY` — Anthropic provider key
- `GOOGLE_AI_API_KEY` — Google AI provider key
- `CORS_ORIGINS` — allowed origins for CORS (default: `["http://localhost:3000"]`)
- `LLM_TIMEOUT_SECONDS` — global LLM call timeout (default: 8)
- `REDIS_URL` — Redis connection string (Phase 3+)

**Secrets location:**
- `clanker_poker/.env` (gitignored) — frontend env vars
- `clanker_poker/backend/.env` (gitignored) — backend env vars (planned)
- `clanker_poker/backend/.env.example` (committed) — documents all required vars with empty values

## Webhooks & Callbacks

**Incoming:**
- SSE polling — browsers connect to `GET /api/game/stream` (or FastAPI equivalent) to receive game state updates

**Outgoing:**
- LLM API calls — sequential per decision phase; each provider called once per player turn
- No webhooks configured

## Real-Time Communication

**Protocol:** Server-Sent Events (SSE) — one-directional push from server to browser clients

**FastAPI SSE Endpoint (Phase 3+):**
- `GET /api/game/stream` — streams game state updates
- Headers required: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`
- Heartbeat: 5-second ping comment (`: ping\n\n`) to keep connections alive
- Message format: `data: {JSON}\n\n` with monotonically increasing `id:` field
- Late-joiner snapshot: first event is full current game state

**Next.js SSE Client (Phase 5):**
- `EventSource('/api/game/stream')` — native browser API with auto-reconnect
- Reconnect logic uses SSE message IDs to detect missed events
- CORS configured: FastAPI allows Next.js origin; no server-side proxying needed

---

*Integration audit: 2026-05-02*
