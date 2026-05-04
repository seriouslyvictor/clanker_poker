# Technology Stack

**Analysis Date:** 2026-05-02

## Languages

**Primary:**
- TypeScript 5.x - Next.js frontend, all React components and type definitions
- Python 3.11+ - FastAPI backend (planned; not yet implemented as of Phase 1 planning)

**Secondary:**
- CSS (globals.css) - Global styles and keyframe animations

## Runtime

**Environment:**
- Node.js 20.x LTS (frontend)
- Python 3.11+ via `uv` toolchain (backend — planned)

**Package Manager:**
- pnpm (frontend) — lockfile `clanker_poker/pnpm-lock.yaml` present (node_modules/.pnpm structure confirmed)
- uv (backend) — `backend/pyproject.toml` + `backend/uv.lock` planned per Phase 1

## Frameworks

**Core:**
- Next.js 16.2.4 (App Router) — frontend UI, SSE proxy endpoint (Phase 5); runs on VPS via `next start`
- FastAPI (>=0.136.1) — backend game engine, SSE broadcast, LLM orchestration (planned Phase 1+)
- React 19.2.4 — UI component library

**LLM Integration:**
- LiteLLM (>=1.83.0) — unified Python interface for all 4 LLM providers (planned Phase 1); reads provider API keys directly from `os.environ`
- `@anthropic-ai/sdk` 0.92.0 — Anthropic SDK (currently installed in frontend; may be replaced by backend LiteLLM)
- `@google/generative-ai` 0.24.1 — Google Generative AI SDK (currently installed in frontend)
- `openai` 6.35.0 — OpenAI SDK (currently installed in frontend)

**Poker Math (Backend — planned):**
- `treys` (>=0.1.8) — Python hand evaluator; lookup-table based; handles all 9 hand ranks, kicker tiebreakers, multi-hand comparison
- Custom Monte Carlo equity calculator (~1000 samples) — win probability, pot odds; wraps treys in `backend/app/engine/poker_math.py`

**Testing:**
- pytest (>=9.0.0) — Python test runner (backend, planned)
- httpx (>=0.27.0) — async HTTP client for FastAPI test client (backend, planned)
- No frontend test framework detected

**Build/Dev:**
- Uvicorn (>=0.46.0) — ASGI server for FastAPI; entry: `uv run uvicorn app.main:app` from `backend/`
- ESLint 9.x with `eslint-config-next` 16.2.4 — frontend linting
- TypeScript compiler (strict mode) — `noEmit: true`, type-check only
- `babel-plugin-react-compiler` 1.0.0 — React 19 compiler optimization

## Key Dependencies

**Critical (Frontend — existing):**
- `next` 16.2.4 — NOTE: This is next.js version 16 (breaking changes from training data). Read `node_modules/next/dist/docs/` before writing any Next.js code.
- `react` / `react-dom` 19.2.4 — React 19 with concurrent features
- `@anthropic-ai/sdk`, `@google/generative-ai`, `openai` — LLM provider SDKs (may be superseded by backend LiteLLM in Phase 4+)

**Critical (Backend — planned):**
- `fastapi>=0.136.1` — REST API + SSE endpoints
- `litellm>=1.83.0` — unified LLM provider abstraction; provider API keys from `os.environ`
- `treys>=0.1.8` — hand evaluation engine
- `pydantic-settings>=2.14.0` — config management via `Settings(BaseSettings)` with `.env` file

**Infrastructure (Backend — planned):**
- Redis + `ioredis` (Node.js) or `aioredis` (Python) — game state Pub/Sub + transient state (Phase 3)
- PM2 — process manager for VPS deployment (runs Next.js + game engine as separate daemons)

## Configuration

**Environment:**
- Frontend: `.env*` files gitignored; environment-driven config
- Backend: `backend/.env` gitignored; `backend/.env.example` committed (documents all required vars)
- Key env vars: `PLAYER_MODELS` (LiteLLM model strings list), `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_AI_API_KEY`, `CORS_ORIGINS`, `LLM_TIMEOUT_SECONDS`
- LiteLLM reads provider keys directly from `os.environ` — NOT wrapped in pydantic Settings

**Build:**
- `clanker_poker/tsconfig.json` — TypeScript strict mode, `@/*` path alias maps to `./`
- `clanker_poker/eslint.config.mjs` — ESLint flat config, Next.js core web vitals + TypeScript rules
- `clanker_poker/next.config.*` — not detected (uses Next.js defaults)
- `backend/pyproject.toml` — hatchling build backend, pytest config with `pythonpath = ["."]`

## Platform Requirements

**Development:**
- Node.js 20.x LTS + pnpm (frontend)
- Python 3.11+ + uv (backend)
- Redis instance (Phase 3+)
- LLM provider API keys in `.env`

**Production:**
- VPS (NOT Vercel/serverless — SSE requires persistent connections)
- PM2 for process management
- Nginx reverse proxy with `X-Accel-Buffering: no` header for SSE

---

*Stack analysis: 2026-05-02*
