# Retrospective — LLM Poker Arena

## Milestone: v0.5 — MVP

**Shipped:** 2026-05-14
**Phases:** 6 | **Plans:** 24

### What Was Built

1. FastAPI backend scaffold with poker math engine (treys hand evaluator + Monte Carlo equity)
2. Complete Texas Hold'em game state machine — correct betting order, BB-option, chip conservation
3. Redis pub/sub SSE broadcast pipeline — late-joiner snapshot, heartbeat, message IDs
4. LLM integration — 4 archetype-biased players, streaming reasoning, fallback on timeout/malformed
5. Vite SPA migration from Next.js — real-time SSE hook, MOCK_STATE removed
6. Viewer experience — idle screen, demand-gated start, anonymous prediction widget

### What Worked

- **GSD phase structure** — planning each phase before execution prevented scope drift and kept context manageable. Phase summaries made milestone archival fast.
- **Test-first game engine** — writing 35 tests for the game state machine (Phase 2) gave confidence when adding LLM calls and SSE broadcast in later phases. The BB-option bug was caught by a test before any UI existed.
- **Mock decision seam** — designing the `DecisionFn` type alias in Phase 2 meant Phase 4 LLM wiring was a clean drop-in with zero engine changes.
- **Sequential LLM calls** — simpler than parallel, and the 45s global timeout was sufficient for v0.5. No race conditions to debug.
- **SSE over WebSockets** — EventSource's native reconnect + late-joiner snapshot from Redis eliminated almost all reconnect complexity from the client.
- **Vite migration** — deciding to migrate from Next.js during Phase 5 (rather than discovering it was wrong sooner) was still low-cost because all components were already pure React. No SSR logic to remove.

### What Was Inefficient

- **Timeout tuning** — the 8s global timeout in the plan was too aggressive for real LLM APIs; bumped to 45s mid-execution. This should have been discovered during Phase 1 provider testing.
- **Phase string case mismatch** — frontend was sending uppercase phase strings, backend expected lowercase. Caught in Phase 6 UAT but should have been a contract test in Phase 3.
- **models.config.json cross-root import** — `server.fs.allow` needed for Vite to import the config file from outside the frontend root. Discovered late in Phase 5. Could have been in the Vite scaffold step.
- **Tweaks relic** — a leftover Tweaks component from the pre-existing UI caused a zIndex conflict in Phase 6. Discovered in UAT.

### Patterns Established

- `broadcast_fn` callback seam pattern — injectable broadcast callbacks on game engine functions allow SSE wiring without engine changes
- `asyncio.Event` demand gate — `game_ready_event` controls game loop start; viewer presence checked server-side before releasing
- `reasoning_snapshot` event — on reconnect, full reasoning history replayed via a single SSE event; clients don't lose context
- Per-module singleton evaluator — treys `Evaluator()` initialized once at module level, not per-call
- `make_llm_decision_fn` factory — returns a closure capturing player context; clean seam between AI module and engine

### Key Lessons

1. **Define cross-layer contracts early** — phase string format, JSON envelope structure, and SSE event names should be documented as shared contracts in Phase 3, not discovered in Phase 6 UAT.
2. **Test timeouts with real providers** — the LiteLLM provider test in Phase 1 should measure actual p95 response time, not just connectivity. 8s was wrong for production models.
3. **Vite + external file imports** — when the frontend needs to read config files from the monorepo root, `server.fs.allow` must be in the Vite scaffold step, not discovered during wiring.
4. **UAT scripts in advance** — Phase 6 UAT discovered bugs that could have been spec'd as acceptance criteria in the plan (zIndex, result latch timing). Writing UAT scripts before execution would have caught these in the plan review.

### Cost Observations

- Sessions: 6 major planning + execution sessions over 13 days
- Model: Claude Sonnet 4.6 throughout
- Notable: Each phase was planned and executed in a single session; no mid-phase context resets required

---

## Cross-Milestone Trends

| Milestone | Phases | Plans | Days | UAT Issues Found |
|-----------|--------|-------|------|-----------------|
| v0.5 MVP | 6 | 24 | 13 | 4 bugs fixed (BB-option, phase case, zIndex, result latch) |
