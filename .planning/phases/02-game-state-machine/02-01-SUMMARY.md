---
phase: 02-game-state-machine
plan: "01"
subsystem: backend/engine
tags: [cards, treys, conversion, asyncio, tdd]
dependency_graph:
  requires: []
  provides:
    - backend/app/engine/cards.py (new_card, card_display)
    - asyncio_mode=strict in pyproject.toml
    - pytest-asyncio>=1.3.0 in dev dependencies
  affects:
    - backend/app/engine/game.py (Wave 2 — imports new_card, card_display)
    - backend/tests/test_game_engine.py (Wave 4 — uses asyncio_mode=strict)
tech_stack:
  added:
    - pytest-asyncio 1.3.0 (dev — async test support for decision seam)
  patterns:
    - Module-level mapping dicts for bidirectional encoding
    - Single-boundary pattern: TreysCard.new() called only inside new_card()
    - TDD: RED (import failure) → GREEN (19/19 pass) → no refactor needed
key_files:
  created:
    - backend/app/engine/cards.py
    - backend/tests/test_cards.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
decisions:
  - "asyncio_mode=strict chosen over auto — explicit decorator required, prevents silent async test bypass"
  - "cards.py is single TreysCard.new() boundary — encoding bugs contained, never spread to game.py or session.py"
  - "pytest-asyncio>=1.3.0 added to dev group alongside asyncio_mode patch"
metrics:
  duration: "3m 25s"
  completed: "2026-05-03"
  tasks_completed: 2
  files_created: 2
  files_modified: 2
  tests_added: 19
  tests_passing: 19
---

# Phase 02 Plan 01: Cards Conversion Boundary and asyncio_mode Patch — Summary

**One-liner:** asyncio_mode=strict patch + treys-int ↔ {s,r} unicode conversion boundary via new_card()/card_display() in cards.py with KeyError enforcement on invalid suit symbols.

## Tasks Completed

| # | Task | Commit | Type | Files |
|---|------|--------|------|-------|
| 1 | Add asyncio_mode=strict to pyproject.toml | 4196709 | chore | backend/pyproject.toml |
| 2 (RED) | Failing tests for cards.py | eae3f38 | test | backend/tests/test_cards.py |
| 2 (GREEN) | Create cards.py treys conversion boundary | 411cd4c | feat | backend/app/engine/cards.py |
| — | Update uv.lock for pytest-asyncio | a78b096 | chore | backend/uv.lock |

## What Was Built

**Task 1 — pyproject.toml patch:**
- Added `asyncio_mode = "strict"` to `[tool.pytest.ini_options]` — async tests using `@pytest.mark.asyncio` now run correctly; without this they fail silently
- Added `pytest-asyncio>=1.3.0` to dev dependency group — required for the async decision seam tests in Wave 4

**Task 2 — cards.py (TDD):**
- `new_card(r: str, s: str) -> int` — converts unicode suit symbol ('♥', '♠', '♦', '♣') to ASCII suit char ('h', 's', 'd', 'c') before calling `TreysCard.new()`. Raises `KeyError` on invalid symbol — fail loud at boundary (STRIDE T-02-01 mitigated).
- `card_display(treys_int: int) -> dict` — extracts rank_int and suit_int via `TreysCard.get_rank_int()` / `get_suit_int()`, maps to `{r: str, s: unicode_symbol}` matching `types.ts Card` exactly.
- Three module-level mapping dicts: `_RANK_INT_TO_STR`, `_SUIT_INT_TO_SYMBOL`, `_SUIT_SYMBOL_TO_CHAR`
- Module docstring includes explicit encoding warnings: NEVER pass unicode to TreysCard.new(); NEVER call TreysCard.new() outside this module.

**TDD Gate Compliance:**
- RED commit `eae3f38`: `test(02-01)` — 19 tests collected, 1 collection error (ModuleNotFoundError, cards.py absent)
- GREEN commit `411cd4c`: `feat(02-01)` — 19/19 tests pass
- REFACTOR: not needed — implementation is minimal and clean as specified

## Verification Results

```
cards.py OK         ← inline verification from plan
round-trip OK       ← new_card(**card_display(TreysCard.new('Kd'))) == TreysCard.new('Kd')
19 passed in 0.05s  ← full test suite
```

**Acceptance criteria checklist:**
- [x] `asyncio_mode = "strict"` present in `[tool.pytest.ini_options]`
- [x] Line appears after pythonpath line — confirmed by grep
- [x] No other lines modified in pyproject.toml (git diff: +2 lines only)
- [x] backend/app/engine/cards.py exists
- [x] Contains `def new_card(r: str, s: str) -> int:`
- [x] Contains `def card_display(treys_int: int) -> dict:`
- [x] Contains `_SUIT_SYMBOL_TO_CHAR`, `_SUIT_INT_TO_SYMBOL`, `_RANK_INT_TO_STR`
- [x] Does NOT import Deck or Evaluator
- [x] TreysCard.new() called only inside new_card() function
- [x] Inline verification prints "cards.py OK"
- [x] Round-trip for Kd passes

## Deviations from Plan

**1. [Rule 2 - Missing critical functionality] Added pytest-asyncio to pyproject.toml**
- **Found during:** Task 1
- **Issue:** The RESEARCH.md explicitly states pytest-asyncio was added during research but noted it may not be in pyproject.toml. The plan's action section only mentions asyncio_mode. Without pytest-asyncio in pyproject.toml, `uv run pytest` in a fresh environment would fail to install it.
- **Fix:** Added `"pytest-asyncio>=1.3.0"` to the `[dependency-groups] dev` section alongside the asyncio_mode line.
- **Files modified:** backend/pyproject.toml, backend/uv.lock
- **Commits:** 4196709 (pyproject.toml), a78b096 (uv.lock)

## Known Stubs

None — cards.py is a pure conversion utility with no data sources or UI rendering.

## Threat Flags

None — cards.py introduces no new network endpoints, auth paths, file access, or schema changes. The KeyError boundary for invalid suit symbols mitigates T-02-01 as planned.

## Self-Check: PASSED

- [x] backend/app/engine/cards.py exists
- [x] backend/tests/test_cards.py exists
- [x] Commit 4196709 exists (pyproject.toml patch)
- [x] Commit eae3f38 exists (RED test)
- [x] Commit 411cd4c exists (GREEN implementation)
- [x] Commit a78b096 exists (uv.lock update)
- [x] 19/19 tests pass
- [x] Inline verification passes
