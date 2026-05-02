# Phase 1: Backend Foundation — Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a working Python/FastAPI project with a provably correct poker math engine and all LLM provider credentials wired through LiteLLM. No game logic, no SSE, no UI changes in this phase.

Phase 1 output: a runnable `uvicorn backend.app.main:app` server that passes all poker math tests and confirms live connections to all 4 LLM providers.

</domain>

<decisions>
## Implementation Decisions

### Backend Directory Layout
- **D-01:** Python backend lives at `backend/` in the repo root, alongside `app/` (Next.js).
  ```
  clanker_poker/
  ├── app/          ← Next.js (existing, do not modify)
  ├── backend/      ← Python/FastAPI (new in Phase 1)
  ├── .planning/
  └── package.json
  ```

### Python Toolchain
- **D-02:** `uv` for package/environment management with `pyproject.toml` (hatchling build backend). Lockfile `uv.lock` is committed.
  - `uv sync` to install dependencies
  - `uv run pytest` to run tests
  - `uv run uvicorn backend.app.main:app` to start server
  - Python version constraint: `>=3.11`

### FastAPI App Structure
- **D-03:** Package layout from day one — no flat `main.py`. Future phases drop code into the right module without restructuring.
  ```
  backend/
  ├── app/
  │   ├── __init__.py
  │   ├── main.py          ← uvicorn entry point (app = FastAPI())
  │   ├── api/
  │   │   └── health.py    ← GET /health → 200
  │   └── engine/
  │       └── poker_math.py ← treys wrapper + equity calculator
  ├── tests/
  │   ├── test_poker_math.py
  │   └── test_litellm_providers.py
  ├── pyproject.toml
  ├── uv.lock
  └── .env.example
  ```

### Hand Evaluation Library
- **D-04 (Claude's Discretion):** Use `treys` — battle-tested Python hand evaluator, fast lookup tables, handles all 9 ranks and kicker tiebreakers. Wraps in `poker_math.py` to isolate the dependency.

### Equity Calculator
- **D-05 (Claude's Discretion):** Monte Carlo simulation with ~1000 samples for win probability. Runs in < 100ms. Pure Python, no LLM involvement. Accepts `(hole_cards, community_cards) → {hand_strength, pot_odds, win_probability}`.

### LiteLLM Provider Testing
- **D-06 (Claude's Discretion):** Pytest integration test in `tests/test_litellm_providers.py`. Each provider test is skipped (not failed) when the corresponding env var is absent — CI passes even without real keys. Running with real keys confirms live connectivity.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements for Phase 1
- `.planning/REQUIREMENTS.md` — POKER-03 (hand eval), POKER-04 (equity calc), INFRA-01 (FastAPI), INFRA-02 (LiteLLM), INFRA-03 (env vars)
- `.planning/ROADMAP.md` — Phase 1 success criteria (5 criteria, all must be TRUE)

### Frontend Type Contract
- `app/_components/types.ts` — Defines `GameState`, `Player`, `Card`, `ReasoningEntry` TypeScript interfaces. Backend JSON responses in Phase 3+ must be compatible with these shapes. Phase 1 doesn't produce game state yet, but planner should be aware.

### Stack Reference
- `.planning/research/STACK.md` — Architecture patterns and library rationale. Note: this doc assumes Node.js backend; Phase 1 uses Python equivalents (`treys` instead of pokersolver, `LiteLLM` instead of Vercel AI SDK, `aioredis` instead of ioredis for future phases).

### Architecture Reference
- `.planning/research/ARCHITECTURE.md` — Component map and data flow. Python equivalents apply; FastAPI + asyncio replaces Node.js event loop patterns.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/_components/types.ts` — TypeScript `GameState`, `Player`, `Card` interfaces. Phase 1 backend doesn't produce game state, but Phase 3 SSE output must serialize to match these shapes.
- No existing Python code — starting from scratch in `backend/`.

### Established Patterns
- Next.js frontend uses `MOCK_STATE` in `Game.tsx` — Phase 1 does not touch the frontend; that replacement happens in Phase 5.
- Existing `app/` uses TypeScript with pnpm workspaces — Python lives entirely in `backend/`, no cross-language build coupling needed for Phase 1.

### Integration Points
- `backend/app/main.py` health endpoint will be called by frontend in Phase 5 CORS tests — set up CORS headers from day one (even if not tested until Phase 5).
- `backend/app/engine/poker_math.py` is the seam Phase 2 imports to build the game state machine.

</code_context>

<specifics>
## Specific Requirements

- Uvicorn entry point: `uvicorn backend.app.main:app` (or `uvicorn app.main:app` when run from `backend/`)
- Health check endpoint: `GET /health` returns `{"status": "ok"}` with 200
- All API keys sourced from `.env` (loaded via `python-dotenv`); `.env.example` documents every required var
- `pytest` runs from `backend/` directory; all tests pass (or skip) with no real API keys

</specifics>

<deferred>
## Deferred Ideas

- Redis integration — not needed for Phase 1 (no game state yet); comes in Phase 3
- CORS configuration — add headers in Phase 1's `main.py` but not tested until Phase 5
- Database — deferred to v2 (game history/replay); Phase 1 has no persistence layer
- Provider credential tests skipping vs failing is already decided above (skip)

</deferred>

---

*Phase: 01-backend-foundation*
*Context gathered: 2026-05-02*
