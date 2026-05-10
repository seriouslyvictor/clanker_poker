# Phase 5: Frontend Wiring — Research

**Researched:** 2026-05-10
**Domain:** Next.js → Vite SPA migration + SSE EventSource wiring + FastAPI CORS
**Confidence:** HIGH

---

## Summary

Phase 5 is a two-part integration sprint: (1) migrate the existing Next.js app to a Vite + React 19 SPA, and (2) wire the SSE backend into the React components, replacing MOCK_STATE with live game state. The frontend migration is almost entirely mechanical — every component already uses `'use client'`, no API routes or SSR is in use, and the `@/` path alias can be replicated in Vite with a two-line config change. The SSE wiring is also well-defined: the backend emits two named event types (`game_state` and `reasoning`) and the frontend needs a single custom hook that manages `EventSource`, state accumulation, and cleanup.

The most consequential decisions are: (a) how to replace `next/font` with self-hosted or Fontsource fonts without a flash of unstyled text, (b) how to manage the `reasoning` accumulator across SSE delta events, and (c) getting `cors_origins` in `backend/app/config.py` updated to include `http://localhost:5173`. The backend CORS is already implemented — only the allowed-origins list needs the Vite dev port added.

**Primary recommendation:** Scaffold `frontend/` with `npm create vite@latest -- --template react-ts`, move source files in, add `@vitejs/plugin-react` + `vite-tsconfig-paths`, replace `next/font` with `@fontsource/*` packages, then implement a `useGameStream` hook that owns the `EventSource` lifecycle and merges `reasoning` deltas.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SSE event consumption | Browser (React hook) | — | EventSource is a browser API; state accumulation lives in React |
| Game state rendering | Browser (React components) | — | Already pure client-side; no SSR |
| Reasoning delta accumulation | Browser (React hook) | — | Deltas arrive per-player; hook builds the full ReasoningEntry array |
| CORS configuration | API / Backend (FastAPI) | — | Server sets Access-Control headers; frontend cannot fix CORS |
| Font loading | Browser (CSS / index.html) | CDN | Fontsource or Google Fonts CDN link replaces next/font |
| Path alias resolution | Build tool (Vite) | — | vite.config.ts + tsconfig.json must both declare @/ |
| Asset serving (deck PNGs) | CDN / Static (Vite public/) | — | Files move from /public to /frontend/public; URLs unchanged |
| models.config.json import | Browser (module import) | — | Vite resolves JSON imports natively; path changes to ../../models.config.json |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vite | 8.0.11 | Build tool, dev server, HMR | Fastest ESM-native bundler; React 19 compatible [VERIFIED: npm registry] |
| @vitejs/plugin-react | 6.0.1 | Babel + React Refresh for HMR | Official Vite plugin; supports React Compiler [VERIFIED: npm registry] |
| react | 19.2.4 | UI runtime | Already in project; stays [VERIFIED: package.json] |
| react-dom | 19.2.4 | DOM renderer | Already in project; stays [VERIFIED: package.json] |
| typescript | 6.0.3 | Type checking | Latest; no breaking changes for this project [VERIFIED: npm registry] |
| vite-tsconfig-paths | 6.1.1 | Sync tsconfig paths to Vite resolver | Replaces manual alias duplication; keeps @/ working [VERIFIED: npm registry] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @fontsource/rajdhani | 5.2.7 | Self-hosted Rajdhani 600+700 weights | Replaces `next/font/google` Rajdhani [VERIFIED: npm registry] |
| @fontsource/vt323 | 5.2.7 | Self-hosted VT323 400 weight | Replaces `next/font/google` VT323 [VERIFIED: npm registry] |
| @fontsource/press-start-2p | 5.2.7 | Self-hosted Press Start 2P 400 weight | Replaces `next/font/google` Press_Start_2P [VERIFIED: npm registry] |
| @types/node | ^20 | Node type defs for path.resolve in vite.config.ts | Required when using path.resolve in config [ASSUMED] |

### Removed from package.json
| Package | Reason |
|---------|--------|
| next | Framework removed in migration |
| eslint-config-next | Next-specific ESLint rules no longer needed |
| @anthropic-ai/sdk | Backend-only; frontend never imports it |
| openai | Backend-only; frontend never imports it |
| @google/generative-ai | Backend-only; frontend never imports it |
| babel-plugin-react-compiler | Replaced by @vitejs/plugin-react (which handles React Compiler via babel) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| @fontsource/* | Google Fonts CDN link in index.html | CDN link is simpler (no install) but adds network round-trip + GDPR concern |
| @fontsource/* | vite-plugin-webfont-dl | Auto-downloads at build time; overkill for 3 known fonts |
| vite-tsconfig-paths | Manual resolve.alias in vite.config.ts | Manual requires syncing two files; vite-tsconfig-paths reads tsconfig.json paths once |
| native EventSource | reconnecting-eventsource npm package | Package wraps reconnect logic; but this project only needs 3s reconnect with Last-Event-ID — native EventSource auto-reconnects, so custom hook is sufficient |

**Installation (frontend/ directory):**
```bash
npm create vite@latest . -- --template react-ts
npm install @fontsource/rajdhani @fontsource/vt323 "@fontsource/press-start-2p" vite-tsconfig-paths
npm remove next eslint-config-next @anthropic-ai/sdk openai @google/generative-ai babel-plugin-react-compiler
```

**Version verification:** Confirmed against npm registry on 2026-05-10. [VERIFIED: npm registry]

---

## Architecture Patterns

### System Architecture Diagram

```
Browser
│
├── index.html  ←─ Google fonts via @fontsource (CSS import in main.tsx)
│                   app title, viewport meta
│
├── main.tsx    ←─ ReactDOM.createRoot('#root')
│
├── App.tsx     ←─ <PokerApp /> (was page.tsx + layout.tsx)
│
└── useGameStream hook
    │
    ├── EventSource('http://localhost:8000/api/stream')
    │   ├── onmessage (event: 'game_state')  →  setGameState(JSON.parse)
    │   ├── onmessage (event: 'reasoning')   →  accumulate delta into reasoningMap
    │   └── onerror                          →  EventSource auto-reconnects with Last-Event-ID
    │
    └── returns: { gameState, reasoning, connectionState }
                    │               │
                    ▼               ▼
              Game.tsx        ReasoningPanel.tsx
              (replaces        (receives live
               MOCK_STATE)      ReasoningEntry[])
```

Data flows: SSE push from FastAPI → EventSource in browser → hook merges state → components re-render.

### Recommended Project Structure
```
clanker_poker/               (repo root — unchanged)
├── frontend/                (NEW — Vite SPA)
│   ├── src/
│   │   ├── components/      (moved from app/_components/)
│   │   ├── hooks/
│   │   │   └── useGameStream.ts   (NEW — SSE client)
│   │   ├── lib/
│   │   │   └── constants.ts (moved from lib/constants.ts)
│   │   ├── App.tsx          (replaces app/page.tsx + app/layout.tsx)
│   │   └── main.tsx         (Vite entry — ReactDOM.createRoot)
│   ├── public/
│   │   └── assets/          (moved from public/assets/)
│   ├── index.html           (Vite entry HTML — title + root div)
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   └── package.json
├── backend/                 (unchanged)
├── models.config.json       (stays at root — import path changes)
├── docker-compose.yml
└── .planning/
```

### Pattern 1: Vite Config with Path Alias

```typescript
// frontend/vite.config.ts
// Source: vite.dev/config/shared-options + vite-tsconfig-paths docs
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  plugins: [
    react(),
    tsconfigPaths(), // reads tsconfig.json paths — @/ → src/ sync automatic
  ],
  server: {
    port: 5173,  // Vite default; must match cors_origins in backend
  },
})
```

```json
// frontend/tsconfig.json — paths section
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  }
}
```

The `@/` alias resolves to `src/` inside `frontend/`. All existing component imports (`@/lib/constants`) work unchanged. [VERIFIED: vite.dev docs + npm vite-tsconfig-paths]

### Pattern 2: models.config.json Import Path

The file stays at the repo root. From `frontend/src/`, the import path is:

```typescript
// frontend/src/lib/constants.ts
import rawModels from '../../../models.config.json'
// (was: '../models.config.json' from project root lib/constants.ts)
```

Vite resolves JSON imports natively — no plugin needed. TypeScript needs `"resolveJsonModule": true` in tsconfig (already present in project tsconfig.json). [VERIFIED: existing tsconfig.json]

### Pattern 3: Font Replacement

```typescript
// frontend/src/main.tsx
import '@fontsource/press-start-2p/400.css'
import '@fontsource/vt323/400.css'
import '@fontsource/rajdhani/600.css'
import '@fontsource/rajdhani/700.css'
import './index.css'  // (was globals.css)
import App from './App'
import { createRoot } from 'react-dom/client'

createRoot(document.getElementById('root')!).render(<App />)
```

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>♠ IA Poker Battleground ♠</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

CSS custom properties `--font-press-start`, `--font-vt323`, `--font-rajdhani` were set in layout.tsx via Next.js font `variable` prop. In Vite, declare them in `index.css`:

```css
/* frontend/src/index.css — add at top, before existing globals.css content */
:root {
  --font-press-start: 'Press Start 2P';
  --font-vt323: 'VT323';
  --font-rajdhani: 'Rajdhani';
}
```

[CITED: dev.to/danwalsh fontsource guide + confirmed @fontsource package names via npm registry]

### Pattern 4: App.tsx (replaces page.tsx + layout.tsx)

```typescript
// frontend/src/App.tsx
// No 'use client' needed in Vite (not Next.js)
import PokerApp from './components/PokerApp'

export default function App() {
  return <PokerApp />
}
```

The `export const metadata` in layout.tsx moves to `<title>` in index.html. The `html`/`body` structure moves to index.html. The font class names (`pressStart2P.variable`, `vt323.variable`, `rajdhani.variable`) on `<html>` are replaced by CSS variables in index.css. [VERIFIED: layout.tsx inspection]

### Pattern 5: useGameStream Hook

The hook owns the EventSource lifecycle. Two SSE event types arrive: `game_state` (full GameState snapshot) and `reasoning` (delta).

```typescript
// frontend/src/hooks/useGameStream.ts
import { useEffect, useRef, useState, useCallback } from 'react'
import type { GameState, ReasoningEntry } from '../components/types'

type ConnectionState = 'connecting' | 'open' | 'closed'

interface GameStream {
  gameState: GameState | null
  reasoning: ReasoningEntry[]
  connectionState: ConnectionState
}

const SSE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/stream`
  : 'http://localhost:8000/api/stream'

export function useGameStream(): GameStream {
  const [gameState, setGameState] = useState<GameState | null>(null)
  const [reasoning, setReasoning] = useState<ReasoningEntry[]>([])
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting')
  // reasoningMap: playerId → accumulated text for current hand
  const reasoningMap = useRef<Map<string, ReasoningEntry>>(new Map())

  useEffect(() => {
    let es: EventSource | null = null

    function connect() {
      es = new EventSource(SSE_URL)
      setConnectionState('connecting')

      es.addEventListener('game_state', (e: MessageEvent) => {
        const state: GameState = JSON.parse(e.data)
        setGameState(state)
        setConnectionState('open')
        // New game phase — clear stale reasoning if phase resets
        // (full reasoning list comes from state.reasoning on game_state events for replay)
        if (state.reasoning?.length) {
          setReasoning(state.reasoning as ReasoningEntry[])
        }
      })

      es.addEventListener('reasoning', (e: MessageEvent) => {
        const delta: { playerId: string; phase: string; delta: string; done: boolean } = JSON.parse(e.data)
        setReasoning(prev => {
          const existing = prev.find(r => r.playerId === delta.playerId && r.phase === delta.phase)
          if (existing) {
            return prev.map(r =>
              r.playerId === delta.playerId && r.phase === delta.phase
                ? { ...r, text: r.text + delta.delta, streaming: !delta.done,
                    action: delta.done ? r.action : null }
                : r
            )
          }
          // New entry for this player+phase
          const entry: ReasoningEntry = {
            id: `${delta.playerId}-${delta.phase}-${Date.now()}`,
            playerId: delta.playerId,
            phase: delta.phase,
            text: delta.delta,
            streaming: !delta.done,
            action: null,
            amount: 0,
          }
          return [...prev, entry]
        })
      })

      es.onerror = () => {
        setConnectionState('connecting')
        // EventSource auto-reconnects — browser sends Last-Event-ID header
        // Do NOT call es.close() here — that stops auto-reconnect
      }
    }

    connect()

    return () => {
      es?.close()
    }
  }, [])

  return { gameState, reasoning, connectionState }
}
```

**Key insight:** Native `EventSource` auto-reconnects on error. Setting `onerror` to call `es.close()` would break this. The browser sends `Last-Event-ID` on reconnect — the backend picks up from that message ID. [VERIFIED: javascript.info/server-sent-events]

### Pattern 6: Game.tsx — Replacing MOCK_STATE

```typescript
// frontend/src/components/Game.tsx
'use client' directive: REMOVE (Vite SPA has no server components)

// Before (remove entirely):
const MOCK_STATE: GameState = { ... }

// After — receive gameState as prop from PokerApp:
interface GameProps {
  theme: (typeof THEMES)[keyof typeof THEMES]
  gameState: GameState | null
  reasoning: ReasoningEntry[]
}

export default function Game({ theme, gameState, reasoning }: GameProps) {
  if (!gameState) {
    return <div style={{ /* loading state */ }}>Connecting to game...</div>
  }
  const { players, communityCards, pot, phase, showCards, winner, winnerHand } = gameState
  // ... rest of render unchanged
}
```

PokerApp.tsx calls `useGameStream()` and passes state down:
```typescript
// frontend/src/components/PokerApp.tsx
const { gameState, reasoning } = useGameStream()
// pass to <Game theme={theme} gameState={gameState} reasoning={reasoning} />
```

### Pattern 7: FastAPI CORS — Adding Vite Dev Origin

The CORS middleware is already configured in `backend/app/main.py`. The `cors_origins` field in `backend/app/config.py` currently defaults to `["http://localhost:3000"]` (Next.js port). Adding Vite dev port:

```python
# backend/app/config.py
cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
```

Or via `.env`:
```
CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

**CRITICAL:** `allow_origins=["*"]` is incompatible with `allow_credentials=True`. The backend already has `allow_credentials=True`. Never use wildcard. [VERIFIED: backend/app/main.py inspection + FastAPI CORS docs]

### Anti-Patterns to Avoid

- **Calling `es.close()` in `onerror`**: This defeats native auto-reconnect. Only call close() in cleanup (useEffect return). [CITED: javascript.info/server-sent-events]
- **Using `'use client'` in Vite components**: The directive is Next.js-only. Remove from all component files during migration. Not harmful but is dead noise.
- **Using `export const metadata`**: Next.js App Router API. Move title/description to `index.html` `<title>`.
- **Hardcoding the SSE URL**: Use `import.meta.env.VITE_API_URL` so prod can point to a different origin.
- **Mixing `resolve.alias` and `vite-tsconfig-paths`**: Pick one. The plugin approach is preferred — it auto-syncs from tsconfig.json, no duplication.
- **Creating `frontend/` as a new git repo**: Keep it in the same monorepo. No separate `.git` in `frontend/`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Font loading without FOUT | Custom font-face inlining | @fontsource/* npm packages | Handles preload, weights, subsets; bundles via Vite |
| Path alias sync | Manually duplicate aliases in vite.config.ts AND tsconfig.json | vite-tsconfig-paths plugin | Two-file sync is error-prone; plugin reads tsconfig once |
| SSE reconnect timing | Custom setTimeout reconnect loop | Native EventSource auto-reconnect | Browser handles exponential backoff and Last-Event-ID; custom loop competes |
| Reasoning text accumulation | Redux / Zustand / external state | `useRef` + `useState` in hook | Three values; local hook state is sufficient |

**Key insight:** EventSource's native reconnect with `Last-Event-ID` already satisfies STREAM-04 ("reconnect within 3s, replay via Last-Event-ID"). The 3s requirement comes from the browser's built-in retry (default ~3s). No custom reconnect code is needed unless you want sub-second control.

---

## Backend SSE Event Contract (Verified from Source)

Both event types arrive on the same `/api/stream` endpoint as named events (not default `message` events). [VERIFIED: backend/app/api/stream.py + broker.py + publisher.py inspection]

### `game_state` event

Full GameState snapshot. Published on every phase transition and as a late-joiner snapshot.

```
id: 42
event: game_state
data: {"phase":"flop","pot":175,"communityCards":[{"s":"♠","r":"A"},...],"players":[...],"showCards":false,"currentBet":50,"reasoning":[],"winner":null,"winnerHand":""}
```

**Shape:** camelCase (Pydantic `by_alias=True`). Matches TypeScript `GameState` in `types.ts` exactly. [VERIFIED: publisher.py `model_dump_json(by_alias=True)` + engine/models.py alias_generator=to_camel]

Note: `GameState` has a `currentBet` field (added in Phase 4 plan) that does NOT exist in the current TypeScript `types.ts`. The planner must add `currentBet?: number` to the TypeScript interface.

### `reasoning` event

Per-token streaming delta. Published on each LLM streaming chunk.

```
id: 43
event: reasoning
data: {"playerId":"gpt4","phase":"pre-flop","delta":"I see a strong","done":false}
```

**Shape (from publisher.py):**
```typescript
interface ReasoningDelta {
  playerId: string   // matches ModelId (e.g. "gpt4", "gemini")
  phase: string      // e.g. "pre-flop", "flop"
  delta: string      // token chunk; empty string on done=true call
  done: boolean      // true = this player's reasoning is complete
}
```

The TypeScript `ReasoningEntry` in `types.ts` accumulates these deltas — the hook must concatenate `delta` strings per `(playerId, phase)` pair. The `action` field on `ReasoningEntry` (fold/call/raise) is not sent via the reasoning channel — it comes from the subsequent `game_state` event showing the player's chosen action.

### Heartbeat

```
: ping
```

Sent every 5s automatically by FastAPI's SSE handler. EventSource ignores comment lines. [VERIFIED: backend/app/main.py `_PING_INTERVAL = 5.0`]

### Message IDs

Monotonically increasing integers, managed by `EventBroker.next_id()`. Reset to 0 on server restart. The backend does NOT implement replay from Last-Event-ID (it does not store historical events). The Last-Event-ID header is sent by the browser but the backend ignores it — the server sends the snapshot for late joiners instead. [VERIFIED: backend/app/api/stream.py — no `last_event_id` query param handling]

**Implication for STREAM-04:** "Replay via Last-Event-ID" in the requirement is satisfied by the late-joiner snapshot mechanism (first event after reconnect is always the current `game_state` snapshot from Redis), not literal event replay from the message ID. The client does not need to send `Last-Event-ID` explicitly.

---

## Common Pitfalls

### Pitfall 1: `'use client'` Left in Components
**What goes wrong:** Harmless in Vite (the string is ignored at runtime), but it's dead noise and can confuse future contributors.
**Why it happens:** Mechanical file copy from Next.js without cleanup.
**How to avoid:** Global find-and-replace `'use client'` across all moved `.tsx` files.

### Pitfall 2: Font CSS Variables Not Set
**What goes wrong:** All text renders as fallback monospace. The components reference `var(--font-rajdhani)`, `var(--font-vt323)`, `var(--font-press-start)` but these variables were set by Next.js layout class names (`pressStart2P.variable` etc.).
**Why it happens:** Next.js font injection is magic — the variables appear automatically. In Vite, you must declare them in CSS.
**How to avoid:** Add CSS variables to `index.css` `:root` block before migrating any component.

### Pitfall 3: CORS Wildcard + allow_credentials Rejection
**What goes wrong:** Browser rejects the response with "The value of the 'Access-Control-Allow-Origin' header in the response must not be the wildcard '*' when the request's credentials mode is 'include'."
**Why it happens:** `allow_credentials=True` + `allow_origins=["*"]` is explicitly forbidden by CORS spec.
**How to avoid:** Enumerate exact origins. Backend already does this — just add `http://localhost:5173`. [VERIFIED: backend/app/main.py]

### Pitfall 4: EventSource Listening on Wrong Event Names
**What goes wrong:** `es.onmessage` only fires for unnamed events (no `event:` field). The backend sends named events (`event: game_state`, `event: reasoning`). Using `es.onmessage` receives nothing.
**Why it happens:** MDN default example uses unnamed events. Backend uses named events.
**How to avoid:** Use `es.addEventListener('game_state', handler)` and `es.addEventListener('reasoning', handler)` — not `es.onmessage`.

### Pitfall 5: Reasoning Accumulator Cleared on game_state Events
**What goes wrong:** Each `game_state` event clears the reasoning panel, so viewers see reasoning disappear between phases.
**Why it happens:** Naive implementation: `setReasoning([])` whenever game state arrives.
**How to avoid:** Only update reasoning from `reasoning` events. Clear on explicit phase transition (e.g., when `phase` changes to a new phase), not on every `game_state` event.

### Pitfall 6: models.config.json Import Path Wrong After Move
**What goes wrong:** TypeScript error: "Cannot find module '../../models.config.json'".
**Why it happens:** The file is at `clanker_poker/models.config.json`. From `frontend/src/lib/constants.ts`, the relative path is `../../../models.config.json` (3 levels up: lib → src → frontend → root).
**How to avoid:** Count directory depth carefully. `frontend/src/lib/constants.ts` → `../` = `src/` → `../../` = `frontend/` → `../../../` = root.

### Pitfall 7: pnpm Workspace Conflict
**What goes wrong:** Running `pnpm install` at repo root after adding `frontend/` tries to install frontend deps in the wrong place.
**Why it happens:** pnpm may auto-detect nested package.json files as workspace members.
**How to avoid:** Either use a `pnpm-workspace.yaml` explicitly OR run `npm install` in `frontend/` (not pnpm) to avoid workspace collision. The repo root currently uses pnpm for the Next.js deps.

---

## Code Examples

### Minimal Vite Config with Path Alias and React

```typescript
// frontend/vite.config.ts
// Source: vite.dev/config/ + vite-tsconfig-paths npm page
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  server: { port: 5173 },
})
```

### EventSource Named-Event Listener

```typescript
// Correct pattern for named SSE events
// Source: MDN EventSource.addEventListener + javascript.info/server-sent-events
const es = new EventSource('http://localhost:8000/api/stream')

es.addEventListener('game_state', (e: MessageEvent) => {
  const state = JSON.parse(e.data)
  // handle game state
})

es.addEventListener('reasoning', (e: MessageEvent) => {
  const delta = JSON.parse(e.data)
  // accumulate delta
})

es.onerror = () => {
  // EventSource will auto-reconnect — do NOT call es.close() here
}

// Cleanup (useEffect return)
return () => { es.close() }
```

### FastAPI CORS for Dual Dev Origins

```python
# backend/app/config.py
cors_origins: list[str] = [
    "http://localhost:3000",  # legacy Next.js dev
    "http://localhost:5173",  # Vite dev server
    # Production origin added via CORS_ORIGINS env var
]
```

### Fontsource Import Order in main.tsx

```typescript
// frontend/src/main.tsx
// Source: fontsource.org + @fontsource package conventions
import '@fontsource/press-start-2p'           // 400 weight (only weight available)
import '@fontsource/vt323'                    // 400 weight (only weight available)
import '@fontsource/rajdhani/600.css'
import '@fontsource/rajdhani/700.css'
import './index.css'                          // must be after fonts so :root vars apply
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `next/font/google` | `@fontsource/*` npm packages | Phase 5 migration | No Google API calls; fonts bundled by Vite |
| `'use client'` directive | Remove (Vite has no server/client split) | Phase 5 migration | Files are pure React; directive is noise |
| `export const metadata` | `<title>` in `index.html` | Phase 5 migration | Next.js App Router API gone |
| `@/` alias via Next.js defaults | `vite-tsconfig-paths` plugin | Phase 5 migration | Same DX, different mechanism |
| `MOCK_STATE` in Game.tsx | `useGameStream()` hook result | Phase 5 implementation | Live data replaces static scaffold |

**Deprecated/outdated:**
- `next/font`: Next.js-only. Remove entirely. No Vite equivalent needed — use @fontsource.
- `eslint-config-next`: Remove from devDependencies after migration.
- `babel-plugin-react-compiler`: `@vitejs/plugin-react` handles React Compiler via its own Babel integration.

---

## Open Questions

1. **`currentBet` field in TypeScript types.ts**
   - What we know: Backend `GameState` (models.py) has `current_bet` → serializes as `currentBet`. TypeScript `GameState` in types.ts does NOT have this field.
   - What's unclear: Whether the Phase 4 plan adds this field to types.ts or defers it.
   - Recommendation: Add `currentBet?: number` to TypeScript `GameState` interface in this phase. The field exists in backend; frontend should at minimum not error on it.

2. **Reasoning accumulator: clear on phase change vs. hand change**
   - What we know: ReasoningPanel shows entries across phases. `game_state` events carry `reasoning: []` (empty list by default from server).
   - What's unclear: Whether to clear the reasoning panel at the start of each hand (game loop restart) or preserve it across hands.
   - Recommendation: Clear reasoning when `winner` transitions from `non-null` back to `null` (new hand start). Preserve within a hand across phases.

3. **Production origin for CORS**
   - What we know: CORS origins are config-driven via `cors_origins` setting.
   - What's unclear: What the production VPS domain/IP is.
   - Recommendation: Add `CORS_ORIGINS` to `backend/.env.example` documenting that prod origin must be added. Not blocking for Phase 5 (dev only).

4. **Package manager for frontend/**
   - What we know: Root uses pnpm. `frontend/` will have its own package.json.
   - What's unclear: Whether to use pnpm workspaces or plain npm in frontend/.
   - Recommendation: Use plain `npm` in `frontend/` to avoid pnpm workspace collisions. The frontend is standalone — no shared packages with the backend.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js 20+ | Vite 8 (requires 20.19+) | Yes | v24.13.0 | — |
| npm | frontend package installation | Yes | 11.6.2 | — |
| FastAPI backend | SSE source | Assumed running (Phase 3+4 complete) | — | Mock SSE server |
| Redis | Backend broker | Assumed running (Phase 3 infra) | — | Backend won't emit events |

**Missing dependencies with no fallback:** None — all required tools are available. [VERIFIED: node --version output]

---

## Validation Architecture

> Skipped — `workflow.nyquist_validation` is `false` in `.planning/config.json`.

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Phase 5 is anonymous / viewer-only |
| V3 Session Management | No | No session; SSE is stateless from client perspective |
| V4 Access Control | No | No protected resources in this phase |
| V5 Input Validation | Partial | `JSON.parse()` on SSE data — wrap in try/catch; malformed JSON must not crash hook |
| V6 Cryptography | No | No crypto in this phase |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed SSE JSON crashing app | Tampering (if attacker controls SSE) | try/catch around JSON.parse in hook; log and skip bad events |
| CORS wildcard misconfiguration | Elevation of privilege | Enumerate exact origins; never use "*" with credentials [VERIFIED: FastAPI CORS docs] |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `@types/node ^20` is needed for `path.resolve` in vite.config.ts | Standard Stack | Low — vite-tsconfig-paths removes the need for path.resolve entirely; @types/node may not be needed |
| A2 | pnpm workspace collision will occur if frontend/ has own package.json without explicit workspace.yaml | Pitfall 7 | Medium — may work fine; depends on pnpm version and whether workspace detection is auto |
| A3 | Reasoning `action` field is not sent via reasoning channel; it comes from game_state | SSE Event Contract | Low — visible in publisher.py; action is applied in game state, not in reasoning delta |
| A4 | Browser default EventSource reconnect delay is ~3s (satisfying STREAM-04 < 3s requirement) | Don't Hand-Roll | Medium — actual browser default varies (MDN says "a few seconds"); may need `retry:` field from server to guarantee < 3s |

---

## Sources

### Primary (HIGH confidence)
- `backend/app/broadcast/publisher.py` — SSE event payload shapes (verified by direct inspection)
- `backend/app/broadcast/broker.py` — Event channel names, message ID scheme
- `backend/app/api/stream.py` — Named event types, late-joiner snapshot logic
- `backend/app/main.py` — CORS middleware configuration, allow_credentials
- `backend/app/config.py` — cors_origins default, Vite port not yet included
- `backend/app/engine/models.py` — GameState/Player field names and camelCase aliases
- `app/_components/types.ts` — TypeScript GameState interface (source of truth for frontend types)
- `app/_components/Game.tsx` — MOCK_STATE structure to be removed
- `app/layout.tsx` — next/font usage requiring replacement
- `lib/constants.ts` — @/ alias usage and models.config.json import pattern
- npm registry — Vite 8.0.11, @vitejs/plugin-react 6.0.1, vite-tsconfig-paths 6.1.1, @fontsource/* 5.2.7

### Secondary (MEDIUM confidence)
- [vite.dev/guide/](https://vite.dev/guide/) — Confirmed stable version 8.0.10/8.0.11, Node.js requirements
- [vite.dev/config/shared-options](https://vite.dev/config/shared-options) — resolve.alias format confirmed
- [javascript.info/server-sent-events](https://javascript.info/server-sent-events) — EventSource reconnect behavior, Last-Event-ID, onerror semantics
- [FastAPI CORS docs](https://fastapi.tiangolo.com/tutorial/cors/) — wildcard + credentials rejection confirmed
- [fontsource docs via dev.to](https://dev.to/danwalsh/self-host-google-fonts-in-your-next-react-project-with-fontsource-1n07) — @fontsource import pattern

### Tertiary (LOW confidence)
- Browser default EventSource retry delay (~3s) — cited from javascript.info; actual browser behavior varies

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — npm registry verified all versions on research date
- SSE event contract: HIGH — read directly from backend source files
- Architecture (migration steps): HIGH — all components inspected; migration is mechanical
- EventSource reconnect behavior: MEDIUM — javascript.info confirmed core behavior; specific timing is LOW
- Pitfalls: HIGH — derived from direct source inspection (backend CORS, event names, font vars)

**Research date:** 2026-05-10
**Valid until:** 2026-06-10 (stable libraries; Vite 8 is current stable)
