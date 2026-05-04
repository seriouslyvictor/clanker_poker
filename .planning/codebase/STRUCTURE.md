# Codebase Structure

**Analysis Date:** 2026-05-02

## Directory Layout

```
D:\Balatro-Poker\
├── .planning/
│   └── codebase/           # Codebase maps (this directory)
└── clanker_poker/          # Project root (git repo)
    ├── app/                # Next.js App Router source
    │   ├── _components/    # All React components (underscore = private/not a route)
    │   ├── api/            # Next.js API route handlers (currently empty — planned for SSE)
    │   │   └── reasoning/  # (directory exists, no route.ts yet)
    │   ├── globals.css     # Global styles + keyframe animations
    │   ├── layout.tsx      # Root layout — fonts, metadata
    │   └── page.tsx        # Root page — renders <PokerApp />
    ├── backend/            # Python/FastAPI backend (PLANNED — not yet created)
    │   ├── app/
    │   │   ├── __init__.py
    │   │   ├── main.py     # FastAPI app + CORS + lifespan
    │   │   ├── config.py   # pydantic-settings Settings class
    │   │   ├── api/
    │   │   │   ├── __init__.py
    │   │   │   └── health.py   # GET /health
    │   │   └── engine/
    │   │       ├── __init__.py
    │   │       └── poker_math.py  # treys wrapper + equity calculator
    │   ├── tests/
    │   │   ├── __init__.py
    │   │   ├── test_poker_math.py
    │   │   └── test_litellm_providers.py
    │   ├── pyproject.toml
    │   ├── uv.lock
    │   └── .env.example    # Documents all required env vars (committed)
    ├── lib/
    │   └── constants.ts    # MODELS, THEMES, STAKE_COLORS, SUITS, RANKS, etc.
    ├── public/
    │   └── assets/         # Card deck images (deck-blue.png, deck-red.png, etc.)
    ├── .planning/          # Project planning docs
    │   ├── PROJECT.md      # Project context and decisions
    │   ├── REQUIREMENTS.md # 23 v1 requirements with REQ-IDs
    │   ├── ROADMAP.md      # 6 phases with success criteria
    │   ├── STATE.md        # Current project state and session continuity
    │   ├── research/       # Stack, architecture, features, pitfalls research
    │   └── phases/         # Per-phase context, plans, reviews
    ├── node_modules/       # pnpm dependencies
    ├── .gitignore          # .env*, .next/, node_modules/, etc.
    ├── eslint.config.mjs   # ESLint flat config (Next.js + TypeScript)
    ├── tsconfig.json       # TypeScript strict config, @/* path alias
    ├── package.json        # Next.js 16, React 19, LLM SDKs
    ├── CLAUDE.md           # AI agent instructions for this project
    └── AGENTS.md           # Warning: Next.js 16 has breaking changes
```

## Directory Purposes

**`clanker_poker/app/_components/`:**
- Purpose: All React UI components — underscore prefix prevents Next.js from treating it as a route segment
- Contains: Game board, player seats, cards, reasoning panel, tweaks panel, chip components, animations
- Key files:
  - `PokerApp.tsx` — root client component; owns `Settings` state; renders `Game` + `TweaksPanel`
  - `Game.tsx` — main game board layout; currently renders `MOCK_STATE` (replaced in Phase 5)
  - `PlayerSeat.tsx` — individual AI player card with hole cards, chips, action stamp, history popover
  - `ReasoningPanel.tsx` — left sidebar streaming AI thought log
  - `TweaksPanel.tsx` — draggable floating settings panel (tempo/voice/atmosphere)
  - `types.ts` — all shared TypeScript interfaces (`GameState`, `Player`, `Card`, `ReasoningEntry`, `Settings`)
  - `Card.tsx` — single playing card (face-up or face-down with card back image)
  - `ActionStamp.tsx` — fold/call/raise/check stamp overlay on player card
  - `StakeChip.tsx` — chip display component with color variants
  - `GoldCrownChip.tsx` — winner crown chip
  - `ConfettiBurst.tsx` — winner celebration animation
  - `HistoryPopover.tsx` — full reasoning history modal for a player

**`clanker_poker/lib/`:**
- Purpose: Shared constants and type exports used across components
- Contains: Game data constants, theme definitions, style lookup tables
- Key files:
  - `constants.ts` — `MODELS` (4 AI players), `THEMES` (felt/neon/noir), `STAKE_COLORS`, `STAKE_MAP`, `TEMPO_MULT`, `SUITS`, `RANKS`, `RANK_V`

**`clanker_poker/backend/app/engine/` (planned):**
- Purpose: Python poker math and game state machine
- Contains: `poker_math.py` (treys wrapper, equity calculator); future phases add `game_engine.py`, `llm_orchestrator.py`, `archetype_engine.py`

**`clanker_poker/backend/app/api/` (planned):**
- Purpose: FastAPI route handlers organized by domain
- Contains: `health.py` (Phase 1), future `game.py` (SSE + REST), `viewers.py` (betting)

**`clanker_poker/public/assets/`:**
- Purpose: Static card deck images served by Next.js
- Contains: `deck-blue.png` (GPT-4o), `deck-yellow.png` (Gemini), `deck-red.png` (Claude), `deck-ghost.png` (Llama), `deck-plasma.png` (Neon theme fallback)
- Referenced in `constants.ts` as CSS `url()` strings in `MODELS[i].deck`

**`clanker_poker/.planning/`:**
- Purpose: GSD planning system documents
- Generated: No — hand-crafted and auto-updated by GSD workflow
- Committed: Yes

## Key File Locations

**Entry Points:**
- `clanker_poker/app/page.tsx` — Next.js root page
- `clanker_poker/app/layout.tsx` — root layout with fonts
- `clanker_poker/backend/app/main.py` — FastAPI app (planned)

**Configuration:**
- `clanker_poker/tsconfig.json` — TypeScript config, `@/*` alias
- `clanker_poker/eslint.config.mjs` — ESLint flat config
- `clanker_poker/package.json` — Node.js dependencies and scripts
- `clanker_poker/backend/pyproject.toml` — Python dependencies, pytest config (planned)
- `clanker_poker/backend/app/config.py` — pydantic-settings, env var declarations (planned)

**Core Logic:**
- `clanker_poker/lib/constants.ts` — all shared game constants and theming
- `clanker_poker/app/_components/types.ts` — TypeScript type contract between frontend and backend
- `clanker_poker/app/_components/Game.tsx` — game board renderer; `MOCK_STATE` placeholder (remove Phase 5)
- `clanker_poker/backend/app/engine/poker_math.py` — hand evaluation and equity (planned)

**Testing:**
- `clanker_poker/backend/tests/test_poker_math.py` — hand rank and equity tests (planned)
- `clanker_poker/backend/tests/test_litellm_providers.py` — LLM connectivity tests (planned; skip if no key)

## Naming Conventions

**Files:**
- React components: `PascalCase.tsx` (e.g., `PlayerSeat.tsx`, `ReasoningPanel.tsx`)
- Shared types: `types.ts` (single file per feature area)
- Constants: `constants.ts` (lowercase, single file in `lib/`)
- Next.js API routes: `route.ts` inside named directory under `app/api/`
- Python modules: `snake_case.py` (e.g., `poker_math.py`, `health.py`)
- Python test files: `test_{module}.py`

**Directories:**
- Private Next.js directories: `_prefix` (e.g., `_components/`) to opt out of routing
- Python packages: `snake_case` (e.g., `poker_math`, `api`, `engine`)

**TypeScript:**
- Interfaces: `PascalCase` (e.g., `GameState`, `Player`, `Settings`)
- Type aliases and union types: `PascalCase` (e.g., `ModelId`, `ActionType`, `AtmosphereMode`)
- Constants: `SCREAMING_SNAKE_CASE` for module-level maps (e.g., `MODELS`, `THEMES`, `STAKE_COLORS`)
- Component props interfaces: `{ComponentName}Props`

## Where to Add New Code

**New React Component:**
- Implementation: `clanker_poker/app/_components/{ComponentName}.tsx`
- Add `'use client';` directive if using React hooks or browser APIs
- Import types from `clanker_poker/app/_components/types.ts`
- Import constants from `@/lib/constants` (path alias resolves to `clanker_poker/`)

**New Shared Constant or Type:**
- Constants: Add to `clanker_poker/lib/constants.ts`
- Types: Add to `clanker_poker/app/_components/types.ts`

**New Next.js API Route:**
- Create `clanker_poker/app/api/{route-name}/route.ts`
- Add `export const dynamic = 'force-dynamic'` for SSE routes to prevent caching

**New FastAPI Route (Backend):**
- Create `clanker_poker/backend/app/api/{domain}.py` with `router = APIRouter()`
- Register in `clanker_poker/backend/app/main.py` with `app.include_router(router)`

**New Python Game Engine Module:**
- Implementation: `clanker_poker/backend/app/engine/{module_name}.py`
- Tests: `clanker_poker/backend/tests/test_{module_name}.py`
- Run tests: `cd clanker_poker/backend && uv run pytest`

**New Static Asset:**
- Images: `clanker_poker/public/assets/{filename}` — served at `/assets/{filename}`

## Special Directories

**`clanker_poker/node_modules/`:**
- Purpose: pnpm-managed Node.js dependencies
- Generated: Yes (by `pnpm install`)
- Committed: No

**`clanker_poker/.next/`:**
- Purpose: Next.js build output and cache
- Generated: Yes (by `next build` or `next dev`)
- Committed: No

**`clanker_poker/backend/.venv/` (planned):**
- Purpose: Python virtual environment managed by uv
- Generated: Yes (by `uv sync`)
- Committed: No

**`clanker_poker/.planning/`:**
- Purpose: GSD workflow planning documents (project context, requirements, roadmap, phase plans)
- Generated: Partially (by GSD commands)
- Committed: Yes

**`D:\Balatro-Poker\.planning\codebase\`:**
- Purpose: Codebase analysis documents for use by GSD plan/execute commands
- Generated: Yes (by `/gsd-map-codebase`)
- Committed: No (outside the git repo at `clanker_poker/`)

---

*Structure analysis: 2026-05-02*
