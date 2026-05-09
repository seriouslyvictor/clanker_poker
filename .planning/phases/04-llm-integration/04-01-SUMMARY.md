---
phase: 04-llm-integration
plan: "01"
subsystem: backend/app/ai
tags: [llm, archetypes, budget, circuit-breaker, pydantic, game-state]
dependency_graph:
  requires:
    - backend/app/engine/models.py (Player, GameState, ActionType)
    - app/_components/types.ts (ReasoningEntry TypeScript contract)
    - models.config.json (player IDs: gpt4, gemini, deepseek, grok)
  provides:
    - backend/app/ai/__init__.py (package marker)
    - backend/app/ai/archetypes.py (ARCHETYPES list, assign_archetypes)
    - backend/app/ai/budget.py (BudgetTracker, CircuitBreaker)
    - backend/app/ai/models.py (LLMDecisionResponse, ReasoningEntry)
    - GameState.current_bet field (for decision fn access)
  affects:
    - backend/app/ai/decision.py (imports ARCHETYPES, BudgetTracker, CircuitBreaker, LLMDecisionResponse)
    - backend/app/ai/prompt.py (imports ReasoningEntry, Archetype)
    - backend/app/engine/game_loop.py (imports assign_archetypes, BudgetTracker, CircuitBreaker)
tech_stack:
  added:
    - pydantic v2 alias_generator=to_camel (ReasoningEntry camelCase serialization)
    - dataclasses frozen=True (Archetype immutable config)
    - defaultdict (BudgetTracker token accumulation, CircuitBreaker error counting)
  patterns:
    - Frozen dataclass for data-driven archetype config (D-09)
    - Pydantic BaseModel with alias_generator=to_camel (matches TypeScript interface)
    - Per-session circuit breaker: trips at threshold, stays open, resets on new instance
    - TDD: RED (failing test) -> GREEN (implementation) per task
key_files:
  created:
    - backend/app/ai/__init__.py
    - backend/app/ai/archetypes.py
    - backend/app/ai/budget.py
    - backend/app/ai/models.py
    - backend/tests/test_ai_foundation.py
    - backend/tests/test_ai_engine_patch.py
  modified:
    - backend/app/engine/models.py (added current_bet field)
decisions:
  - "ReasoningEntry uses list type annotation on GameState.reasoning (not list[ReasoningEntry]) to avoid circular imports between ai/ and engine/ packages"
  - "CircuitBreaker stays open once tripped — session-scoped, no re-close on success"
  - "Archetype.bluff_freq represents probability of raising regardless of hand (not a threshold like raise_freq)"
  - "current_bet field placed after show_cards in GameState field order to maintain semantic grouping"
metrics:
  duration: "4 minutes 15 seconds"
  completed: "2026-05-08"
  tasks_completed: 2
  tasks_total: 2
  files_created: 6
  files_modified: 1
---

# Phase 4 Plan 01: AI Foundation Package Summary

**One-liner:** Created backend/app/ai/ package with 4-archetype config, session-scoped BudgetTracker + CircuitBreaker, camelCase-serializing ReasoningEntry Pydantic model, and GameState.current_bet field.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create backend/app/ai/ package | e8cc442 | __init__.py, archetypes.py, budget.py, models.py (+ test_ai_foundation.py) |
| 2 | Patch engine/models.py — add current_bet | c85cb3e | engine/models.py (+ test_ai_engine_patch.py) |

TDD commits:
- e2a3009: test(04-01): add failing tests for ai/ package — archetypes, budget, models (RED)
- e8cc442: feat(04-01): create backend/app/ai/ package (GREEN)
- cc3b901: test(04-01): add failing tests for GameState.current_bet field (RED)
- c85cb3e: feat(04-01): patch GameState — add current_bet field with default 0 (GREEN)

## Verification Results

All plan verification commands passed:

```
ALL OK
187 passed, 1 skipped in 4.04s
```

- `len(ARCHETYPES) == 4` — Gunslinger, Rock, Grinder, Chaotic Optimist
- `assign_archetypes(players)` returns unique mapping (len(set(values)) == 4)
- `BudgetTracker().record("openai/gpt-5-nano", 100, 50)` accumulates spend
- `CircuitBreaker(threshold=3)` trips after 3 errors; success does not re-close
- `ReasoningEntry(player_id="gpt4", phase="flop").model_dump(by_alias=True)` contains `playerId` not `player_id`
- `GameState(phase='flop', pot=100).current_bet == 0`
- All 187 existing Phase 2 + Phase 3 tests still green

## Deviations from Plan

None — plan executed exactly as written.

The plan noted circular import risk between `ai/models.py` and `engine/models.py`. The chosen approach keeps `GameState.reasoning: list` (bare, untyped) with a comment noting `list[ReasoningEntry]`. This avoids the circular import without any runtime impact — Pydantic does not validate list element types for the bare `list` annotation.

## Known Stubs

None — all fields are fully implemented. No placeholder data flows to UI rendering.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced in this plan. The `current_bet` field addition to `GameState` is serialized to SSE clients but contains no user-controlled input — it is computed from engine state only.

## Self-Check: PASSED

Files exist:
- FOUND: backend/app/ai/__init__.py
- FOUND: backend/app/ai/archetypes.py
- FOUND: backend/app/ai/budget.py
- FOUND: backend/app/ai/models.py
- FOUND: backend/app/engine/models.py (modified)

Commits exist:
- e2a3009: test RED — ai foundation
- e8cc442: feat GREEN — ai foundation
- cc3b901: test RED — engine patch
- c85cb3e: feat GREEN — engine patch

No unexpected file deletions in any commit.
