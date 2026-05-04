# Phase 2: Game State Machine — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 02-game-state-machine
**Areas discussed:** State model, Decision seam, Card format, Session scope

---

## State model

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic models | `.model_dump()` gives Phase 3 SSE JSON payload for free; already in stack | ✓ |
| Dataclasses | Lighter, stdlib-only; manual `.to_dict()` needed for Phase 3 | |
| You decide | Claude picks based on Phase 3 SSE goal | |

**User's choice:** Pydantic models
**Notes:** Recommended option accepted without hesitation.

---

## Decision seam

| Option | Description | Selected |
|--------|-------------|----------|
| Async from the start | Phase 4 LLM calls are async; seam designed async = zero refactor | ✓ |
| Sync now, async later | Simpler Phase 2 tests; small refactor at Phase 4 | |

**User's choice:** Async from the start
**Notes:** Recommended option accepted.

---

## Card format

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 2 owns it | Add engine/cards.py; GameState stores {s,r} natively; Phase 3 gets correct JSON for free | ✓ |
| Defer to Phase 3 | Engine keeps treys ints; Phase 3 handles conversion at broadcast time | |

**User's choice:** Phase 2 owns it
**Notes:** User asked for clarification on the treys-int vs {s,r} distinction — explained both directions of conversion needed (engine→display and display→engine for hand eval). After clarification, chose recommended option.

---

## Session scope

| Option | Description | Selected |
|--------|-------------|----------|
| Multi-hand with rotation | SC4 explicitly requires 10-hand session; dealer button and blinds rotate | ✓ |
| Single hand only | Smaller scope but technically fails SC4 as written | |

**User's choice:** Multi-hand with rotation
**Notes:** ROADMAP SC4 cited as deciding factor.

---

## Claude's Discretion

- Raise sizing: min raise = big blind, no-limit, all-in treated as partial call (no side pots)
- Module layout: cards.py + models.py + game.py + session.py under engine/
- Test file: backend/tests/test_game_engine.py

## Deferred Ideas

- Pot odds surfacing deferred to Phase 4 LLM context
- Archetype bias deferred to Phase 4
- Re-raise cap complexity deferred to v2
