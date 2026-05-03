---
phase: 02-game-state-machine
plan: "02"
subsystem: backend/game-engine
tags: [pydantic, models, game-state, camelcase, type-aliases]
dependency_graph:
  requires:
    - "backend/app/engine/poker_math.py (Phase 1)"
    - "app/_components/types.ts (TypeScript contract)"
  provides:
    - "backend/app/engine/models.py — all game state types"
  affects:
    - "backend/app/engine/game.py (Wave 2, plan 02-03)"
    - "backend/app/engine/session.py (Wave 3, plan 02-04)"
    - "backend/app/engine/cards.py (Wave 1, plan 02-01)"
tech_stack:
  added: []
  patterns:
    - "Pydantic BaseModel with ConfigDict(alias_generator=to_camel) for camelCase JSON serialization"
    - "Pydantic Field(default_factory=list) for mutable list defaults in BaseModel"
    - "Python dataclass with field(default_factory=set) for mutable set defaults"
    - "Callable[[Player, GameState], Awaitable[Action]] type alias for async plug-in seam"
key_files:
  created:
    - backend/app/engine/models.py
    - backend/tests/test_models.py
  modified: []
decisions:
  - "Used Pydantic Field(default_factory=list) for BaseModel mutable defaults (not dataclass field())"
  - "alias_generator=to_camel applied ONLY to Player and GameState — not Card or Action"
  - "BettingRoundState is a plain dataclass (not Pydantic) — internal engine state, never serialized"
  - "from __future__ import annotations enables forward references in DecisionFn type alias"
metrics:
  duration: "~4 minutes"
  completed: "2026-05-03"
  tasks_total: 1
  tasks_completed: 1
  files_created: 2
  files_modified: 0
---

# Phase 02 Plan 02: Pydantic Game State Models Summary

**One-liner:** Pydantic v2 models (Card, Action, Player, GameState) with alias_generator=to_camel matching types.ts contract, plus BettingRoundState dataclass and DecisionFn type alias for the async decision seam.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| RED  | Failing tests for models.py | f41f227 | backend/tests/test_models.py |
| GREEN | Implement backend/app/engine/models.py | 22a19eb | backend/app/engine/models.py |

## What Was Built

`backend/app/engine/models.py` — 114 lines, 7 exports:

- **Card**: BaseModel with `s` (suit unicode) and `r` (rank string) — no alias_generator; fields already match JSON contract
- **ActionType**: `Literal['fold', 'call', 'raise', 'check']` — Pydantic validates against this at construction time
- **Action**: BaseModel with `action_type: ActionType` and `amount: int = 0`
- **Player**: BaseModel with `ConfigDict(alias_generator=to_camel)` — `hole_cards` → `holeCards`, `is_folded` → `isFolded`, `is_active` → `isActive`, `is_winner` → `isWinner`
- **GameState**: BaseModel with `ConfigDict(alias_generator=to_camel)` — `community_cards` → `communityCards`, `show_cards` → `showCards`, `winner_hand` → `winnerHand`
- **BettingRoundState**: `@dataclass` with `current_bet`, `last_raise_size`, `aggressor_seat`, `has_acted: set` — internal engine state, not serialized
- **DecisionFn**: `Callable[[Player, GameState], Awaitable[Action]]` — async plug-in seam; Phase 4 LLM replaces Phase 2 mock without refactor

## Verification Results

```
models.py OK
```

- Inline verification command: exits 0, prints "models.py OK"
- `grep -c "model_config = ConfigDict(alias_generator=to_camel"` returns 2 (Player + GameState only)
- 33/33 tests pass in `backend/tests/test_models.py`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used Pydantic Field() instead of dataclass field() for Pydantic models**
- **Found during:** GREEN phase implementation
- **Issue:** Plan's code snippet used `field(default_factory=list)` (dataclass import) inside Pydantic BaseModel classes. While `from dataclasses import field` is imported, using it in Pydantic models does not work — Pydantic v2 has its own field mechanism.
- **Fix:** Used `Field(default_factory=list)` from `pydantic` for `Player.hole_cards`, `GameState.community_cards`, `GameState.players`, and `GameState.reasoning`. The dataclass `field(default_factory=set)` remains correct for `BettingRoundState.has_acted` (a genuine dataclass).
- **Files modified:** backend/app/engine/models.py
- **Commit:** 22a19eb

## Known Stubs

None — models.py is pure type definitions. No data flows, no placeholder text, no wired components needed at this stage. All fields have correct defaults (`[]`, `False`, `None`, `""`) that match the TypeScript contract.

## Threat Flags

No new security-relevant surface introduced. models.py is pure type definitions with no network endpoints, auth paths, or file access.

**T-02-03 (mitigate):** `Player.show_cards` boolean — implemented as `GameState.show_cards: bool = False`. game.py (Wave 2) sets it `True` only at showdown phase.

**T-02-04 (mitigate):** `Action.action_type: Literal['fold','call','raise','check']` — Pydantic validates at model construction; any invalid value raises `ValidationError` before reaching game logic.

**T-02-05 (accept):** `GameState.reasoning: list` — empty in Phase 2; Phase 4 will bound length before SSE broadcast.

## TDD Gate Compliance

- RED commit: f41f227 (`test(02-02): add failing tests for models.py (RED phase)`) — 33 tests, all failing
- GREEN commit: 22a19eb (`feat(02-02): implement backend/app/engine/models.py (GREEN phase)`) — 33 tests, all passing
- REFACTOR: not needed — implementation is clean on first pass

## Self-Check: PASSED

- backend/app/engine/models.py: EXISTS (114 lines)
- backend/tests/test_models.py: EXISTS (293 lines)
- RED commit f41f227: EXISTS
- GREEN commit 22a19eb: EXISTS
- Inline verification: PASSED (prints "models.py OK")
- 33/33 tests pass
