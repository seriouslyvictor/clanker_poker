---
phase: "05-frontend-wiring"
plan: "01"
subsystem: "frontend"
tags: ["vite", "react", "migration", "fontsource", "typescript"]
dependency_graph:
  requires: []
  provides: ["frontend/vite-spa", "frontend/src/components", "frontend/src/lib/constants"]
  affects: ["05-02", "05-03"]
tech_stack:
  added:
    - "vite 8.0.11"
    - "@vitejs/plugin-react 6.0.1"
    - "vite-tsconfig-paths 6.1.1"
    - "@fontsource/press-start-2p 5.2.7"
    - "@fontsource/vt323 5.2.7"
    - "@fontsource/rajdhani 5.2.7"
    - "typescript 6.0.3"
  patterns:
    - "Vite SPA with react plugin + tsconfig-paths plugin"
    - "server.fs.allow: ['..'] for cross-root JSON import"
    - "fontsource packages via explicit weight CSS paths (400.css, 600.css, 700.css)"
    - "CSS custom properties in :root for font variables"
key_files:
  created:
    - "frontend/package.json"
    - "frontend/vite.config.ts"
    - "frontend/tsconfig.json"
    - "frontend/tsconfig.node.json"
    - "frontend/index.html"
    - "frontend/src/main.tsx"
    - "frontend/src/index.css"
    - "frontend/src/App.tsx"
    - "frontend/src/vite-env.d.ts"
    - "frontend/src/lib/constants.ts"
    - "frontend/src/components/types.ts"
    - "frontend/src/components/Game.tsx"
    - "frontend/src/components/PokerApp.tsx"
    - "frontend/src/components/ReasoningPanel.tsx"
    - "frontend/src/components/PlayerSeat.tsx"
    - "frontend/src/components/Card.tsx"
    - "frontend/src/components/TweaksPanel.tsx"
    - "frontend/src/components/ActionStamp.tsx"
    - "frontend/src/components/StakeChip.tsx"
    - "frontend/src/components/GoldCrownChip.tsx"
    - "frontend/src/components/ConfettiBurst.tsx"
    - "frontend/src/components/HistoryPopover.tsx"
    - "frontend/public/assets/deck-anaglyph.png"
    - "frontend/public/assets/deck-black.png"
    - "frontend/public/assets/deck-blue.png"
    - "frontend/public/assets/deck-ghost.png"
    - "frontend/public/assets/deck-nebula.png"
    - "frontend/public/assets/deck-plasma.png"
    - "frontend/public/assets/deck-red.png"
    - "frontend/public/assets/deck-yellow.png"
  modified: []
decisions:
  - "Use explicit 400.css paths for fontsource imports — bare package import not resolved by TS6 moduleResolution:bundler"
  - "Added ignoreDeprecations:6.0 to tsconfig.json to silence baseUrl deprecation warning in TypeScript 6"
  - "Added composite:true and removed noEmit from tsconfig.node.json to satisfy project references constraint"
  - "Added currentBet?: number to GameState interface — backend serializes this field and TS should not error on it"
  - "Added vite-env.d.ts with vite/client reference — required for CSS module type resolution in TS6"
metrics:
  duration: "510 seconds (~8.5 minutes)"
  completed: "2026-05-10"
  tasks_completed: 2
  files_created: 30
  typescript_errors_before: 0
  typescript_errors_after: 0
---

# Phase 05 Plan 01: Vite SPA Scaffold + Next.js Source Migration Summary

**One-liner:** Vite 8 + React 19 SPA scaffold with fontsource self-hosted fonts, server.fs.allow cross-root JSON import, and full mechanical migration of 11 Next.js components with 'use client' removed.

## What Was Built

The `frontend/` directory is a complete Vite React SPA ready to serve the poker UI at `http://localhost:5173`. All Next.js framework dependencies are eliminated from the frontend scope. The migration was mechanical — every component was already `'use client'` (pure React), so no SSR logic was removed.

### Task 1: Vite project scaffold

- `frontend/package.json`: vite 8.0.11, @vitejs/plugin-react 6.0.1, vite-tsconfig-paths 6.1.1, @fontsource/* 5.2.7, react 19.2.4
- `frontend/vite.config.ts`: react + tsconfigPaths plugins, port 5173, `server.fs.allow: ['..']` for models.config.json
- `frontend/tsconfig.json`: strict TypeScript 6, resolveJsonModule, `@/*` → `src/*` alias
- `frontend/tsconfig.node.json`: composite:true, vite.config.ts type checking
- `frontend/index.html`: explicit UTF-8 charset, "♠ IA Poker Battleground ♠" title
- `npm install`: 33 packages, 0 vulnerabilities

### Task 2: Source file migration

- `frontend/src/main.tsx`: @fontsource imports (explicit 400.css weight paths), ReactDOM.createRoot entry
- `frontend/src/index.css`: globals.css content with `:root` font variable block prepended
- `frontend/src/App.tsx`: thin PokerApp wrapper
- `frontend/src/lib/constants.ts`: `'../models.config.json'` → `'../../../models.config.json'` (3-level path to repo root)
- `frontend/src/vite-env.d.ts`: `/// <reference types="vite/client" />` for CSS import typing
- 11 components migrated: `'use client'` removed from all
- 8 deck PNG files copied to `frontend/public/assets/`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TypeScript 6 project references: tsconfig.node.json needs composite:true**
- **Found during:** Task 2 — first tsc run
- **Issue:** TS6306/TS6310: Referenced project must have `"composite": true` and may not disable emit
- **Fix:** Added `"composite": true`, changed `"noEmit": false` in tsconfig.node.json
- **Files modified:** `frontend/tsconfig.node.json`
- **Commit:** 536470d

**2. [Rule 1 - Bug] TypeScript 6 baseUrl deprecation error**
- **Found during:** Task 2 — first tsc run
- **Issue:** TS5101: Option 'baseUrl' is deprecated in TS6 — treated as error
- **Fix:** Added `"ignoreDeprecations": "6.0"` to tsconfig.json compilerOptions
- **Files modified:** `frontend/tsconfig.json`
- **Commit:** 536470d

**3. [Rule 1 - Bug] @fontsource bare package imports unresolved by TS6**
- **Found during:** Task 2 — second tsc run
- **Issue:** TS2882: Cannot find module for side-effect import of `@fontsource/press-start-2p` (bare package with no default CSS export)
- **Fix:** Changed imports to explicit weight paths: `@fontsource/press-start-2p/400.css`, `@fontsource/vt323/400.css`
- **Files modified:** `frontend/src/main.tsx`
- **Note:** Plan's `main.tsx` template used bare imports; research notes used explicit weight paths — aligned with research
- **Commit:** 536470d

**4. [Rule 2 - Missing Critical Functionality] Added vite-env.d.ts for CSS type resolution**
- **Found during:** Task 2 — second tsc run after fixing fontsource imports
- **Issue:** TS2882 on `./index.css` and rajdhani weight imports — no ambient CSS module declarations
- **Fix:** Added `frontend/src/vite-env.d.ts` with `/// <reference types="vite/client" />`
- **Files modified:** `frontend/src/vite-env.d.ts` (created)
- **Commit:** 536470d

**5. [Rule 2 - Missing Critical Functionality] Added currentBet?: number to GameState**
- **Found during:** Task 2 — review of research notes
- **Issue:** Research notes (open question #1) document that backend serializes `currentBet` field on GameState; TypeScript interface was missing it
- **Fix:** Added `currentBet?: number` to `GameState` interface in `types.ts`
- **Files modified:** `frontend/src/components/types.ts`
- **Commit:** 536470d

**6. [Rule 1 - Bug] PokerApp.tsx gear emoji removed**
- **Found during:** Task 2 — CLAUDE.md instructs "Avoid writing emojis to files unless asked"
- **Fix:** Changed `⚙ TWEAKS` button label to `TWEAKS` (emoji removed)
- **Files modified:** `frontend/src/components/PokerApp.tsx`
- **Commit:** 536470d

## Known Stubs

`frontend/src/components/Game.tsx` contains `MOCK_STATE` — the static scaffold with hardcoded game data. This is intentional per plan ("keep MOCK_STATE intact — it will be removed in Plan 03"). Plan 03 wires `useGameStream()` and removes MOCK_STATE.

## Threat Flags

No new threat surface introduced beyond what is described in the plan's threat model. The `server.fs.allow: ['..']` is dev-only; production Vite build bundles models.config.json at build time.

## Verification Results

| Check | Result |
|-------|--------|
| `server.fs.allow: ['..']` in vite.config.ts | PASS |
| No `'use client'` in frontend/src/ | PASS |
| `--font-press-start` in index.css :root | PASS |
| `../../../models.config.json` in constants.ts | PASS |
| `<meta charset="UTF-8" />` in index.html | PASS |
| 8 PNG files in frontend/public/assets/ | PASS |
| `npx tsc --noEmit` exit 0 | PASS — 0 errors |

## Self-Check

### Created files verified

- `frontend/src/main.tsx` — exists, contains `@fontsource/press-start-2p/400.css`
- `frontend/src/index.css` — exists, contains `:root { --font-press-start`
- `frontend/src/lib/constants.ts` — exists, contains `../../../models.config.json`
- `frontend/src/vite-env.d.ts` — exists, contains `vite/client`
- `frontend/src/components/Game.tsx` — exists, contains MOCK_STATE
- `frontend/public/assets/deck-red.png` — exists (8 PNGs total)

### Commits verified

- e1a4a78 — `feat(05-01): scaffold Vite SPA project config`
- 536470d — `feat(05-01): migrate Next.js source files to Vite SPA`

## Self-Check: PASSED
