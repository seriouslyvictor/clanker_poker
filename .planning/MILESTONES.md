# Milestones — LLM Poker Arena

## v0.5 — MVP (2026-05-14)

**Shipped:** 2026-05-14
**Phases:** 1–6 (24 plans)
**Files changed:** 218 | **Lines added:** 41,535
**Timeline:** 13 days (2026-05-01 → 2026-05-14)

### Delivered

Full end-to-end LLM poker arena: four AI models compete at Texas Hold'em in a Balatro-styled Vite SPA; viewers watch via SSE, start games on demand, and predict winners anonymously.

### Key Accomplishments

1. Provably correct Texas Hold'em engine (35 tests, chip conservation guaranteed, BB-option bug caught and fixed)
2. Redis pub/sub SSE broadcast pipeline — late-joiner snapshot, heartbeat, message IDs, 3-browser verified
3. LLM integration with 4 personality archetypes, structured math context, streaming reasoning, and fallback protection
4. Vite SPA migration from Next.js (all components were pure React) with real-time SSE hook and MOCK_STATE removed
5. Demand-gated game loop (POST /api/game/start, asyncio.Event) enforces viewer-present constraint server-side
6. Anonymous prediction widget (States A/B/C) with localStorage persistence and winner overlay reveal

### Archives

- [v0.5-ROADMAP.md](milestones/v0.5-ROADMAP.md) — full phase details and decisions
- [v0.5-REQUIREMENTS.md](milestones/v0.5-REQUIREMENTS.md) — all 23 requirements marked complete

### Known Deferred Items

- 503 demand-gate path not tested in local dev (UAT item skipped — untriggerable without active game)
- Configurable hands-per-session (todo in STATE.md)
- Optional archetypes mode (todo in STATE.md)
