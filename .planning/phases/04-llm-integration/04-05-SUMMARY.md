---
phase: 04-llm-integration
plan: "05"
subsystem: testing
tags: [pytest, asyncio, unittest-mock, llm, decision, archetype, budget, circuit-breaker, prompt]
dependency_graph:
  requires:
    - backend/app/ai/decision.py (make_llm_decision_fn, _fallback_action, _parse_response, reconstruct_valid_actions — Plan 03)
    - backend/app/ai/archetypes.py (ARCHETYPES, Gunslinger, Rock, Chaotic Optimist — Plan 01)
    - backend/app/ai/budget.py (BudgetTracker, CircuitBreaker — Plan 01)
    - backend/app/ai/prompt.py (build_system_prompt, build_user_prompt — Plan 03)
    - backend/app/engine/models.py (Player, GameState, Card, Action — Phase 2)
  provides:
    - backend/tests/test_llm_decisions.py (27 tests: decision fallback, archetype bias, circuit breaker, budget)
    - backend/tests/test_ai_prompt.py (24 tests: AI-03 field coverage, pot_odds computation, pre-flop edge cases)
  affects:
    - Phase 5 (Frontend Wiring): regression coverage for LLM decision and prompt changes
tech-stack:
  added: []
  patterns:
    - "calculate_equity local-import patch: use app.engine.poker_math.calculate_equity (not app.ai.decision.calculate_equity) since it is imported inside the function body"
    - "D-12 publish_reasoning coverage: pass MagicMock() as redis_client to trigger publish guard in _fallback_action"
    - "Async stream mock: AsyncIterator + _make_chunk factory produces character-level streaming chunks"

key-files:
  created:
    - backend/tests/test_llm_decisions.py
  modified:
    - backend/tests/test_ai_prompt.py

key-decisions:
  - "calculate_equity is imported locally inside llm_decision_fn — patch target must be app.engine.poker_math.calculate_equity, not app.ai.decision.calculate_equity"
  - "D-12 test requires non-None redis_client: _fallback_action guards publish_reasoning with 'if redis_client is not None'; test uses MagicMock() as redis_client"
  - "test_ai_prompt.py merged plan's named tests (test_pot_odds_computed_correctly) with existing fixture-based tests — no test regression"

patterns-established:
  - "Local-import patch pattern: functions using 'from module import X' inside their body require patching the source module, not the importing module"
  - "D-12 coverage pattern: pass mock redis_client to decision fn factory when testing publish_reasoning calls in circuit-open path"

requirements-completed: [AI-01, AI-02, AI-03, AI-04, AI-05, AI-06, INFRA-05]

duration: ~12min
completed: 2026-05-08
---

# Phase 4 Plan 05: LLM Test Suite Summary

**27-test decision suite (fallback/archetype/circuit-breaker/budget) + 24-test prompt suite (AI-03 field coverage) using unittest.mock — zero real LLM API calls; all 263 suite tests green**

## Performance

- **Duration:** ~12 minutes
- **Started:** 2026-05-08
- **Completed:** 2026-05-08
- **Tasks:** 1 (automated) + 1 checkpoint (pending human UAT)
- **Files modified:** 2

## Accomplishments

- Created `test_llm_decisions.py` with 27 tests covering: `reconstruct_valid_actions` (3), `_parse_response` (4), `_fallback_action` (5), `TestArchetypeBias` (1 — Gunslinger delta >= 20pp vs Rock), `TestCircuitBreaker` (4), `TestBudgetTracker` (3), `TestLLMDecisions` (7 integration tests with mocked `acompletion`)
- Updated `test_ai_prompt.py` from 15 to 24 tests: added `test_pot_odds_computed_correctly` (25% assertion), `test_contains_win_probability/pot_odds/hand_strength/available_actions/current_pot/community_cards` standalone tests
- Fixed two bugs in plan's test code: (1) incorrect patch path `app.ai.decision.calculate_equity` — local import requires patching `app.engine.poker_math.calculate_equity`; (2) D-12 test requires non-None redis_client to trigger the `if redis_client is not None` guard in `_fallback_action`

## Task Commits

1. **Task 1: Write test_llm_decisions.py + test_ai_prompt.py** - `7e330b2` (test)

## Files Created/Modified

- `backend/tests/test_llm_decisions.py` — 27 tests across 7 test classes covering AI-04, AI-06, INFRA-05
- `backend/tests/test_ai_prompt.py` — 24 tests covering AI-03 required fields; expanded from TDD RED phase version

## Decisions Made

- Patched `app.engine.poker_math.calculate_equity` (not `app.ai.decision.calculate_equity`) because `decision.py` uses a local import inside the function body — Python's import system means the function looks up `calculate_equity` in `app.engine.poker_math`'s namespace at call time.
- D-12 test `test_fallback_publishes_reasoning_when_circuit_open` uses `MagicMock()` as `redis_client` in the factory call — the `_fallback_action` function guards `publish_reasoning` with `if redis_client is not None and game_state is not None`, so a real (non-None) redis object is required for the assertion to be testable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect patch path for calculate_equity**
- **Found during:** Task 1 (test execution)
- **Issue:** Plan's test code used `patch("app.ai.decision.calculate_equity")` but `calculate_equity` is imported locally inside `llm_decision_fn` via `from app.engine.poker_math import calculate_equity`. Patching `app.ai.decision.calculate_equity` raises `AttributeError: module has no attribute 'calculate_equity'`.
- **Fix:** Changed all 6 patch calls to `patch("app.engine.poker_math.calculate_equity")`. Extracted to module-level `_EQUITY_PATCH` constant for DRY.
- **Files modified:** backend/tests/test_llm_decisions.py
- **Verification:** All 7 TestLLMDecisions tests pass
- **Committed in:** 7e330b2 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed D-12 test: redis_client must be non-None to trigger publish_reasoning**
- **Found during:** Task 1 (test design analysis)
- **Issue:** Plan's `test_fallback_publishes_reasoning_when_circuit_open` passed `redis_client=None` to `make_llm_decision_fn`. Inside `_fallback_action`, the guard `if redis_client is not None and game_state is not None` prevents `publish_reasoning` from being called when `redis_client=None`. The assertion `assert mock_pub.called` would always fail.
- **Fix:** Added `redis_client=MagicMock()` parameter to `_make_archetypes_and_fn()` and passed it in that specific test. The patch on `publish_reasoning` intercepts the call after the guard passes.
- **Files modified:** backend/tests/test_llm_decisions.py
- **Verification:** `test_fallback_publishes_reasoning_when_circuit_open` PASSED; `done_calls` assertion confirmed
- **Committed in:** 7e330b2 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (Rule 1 — bugs in plan's test code)
**Impact on plan:** Both fixes necessary for tests to pass. No scope creep; test behavior matches original intent.

## Known Stubs

None — these are test files only. All production code was wired in Plans 01-04.

## Threat Flags

No new network endpoints, auth paths, or file access patterns. Test mocks are scoped to test context only (T-04-20 accepted per threat model).

## Checkpoint Pending

Human UAT checkpoint awaits approval. See plan's `<task type="checkpoint:human-verify">` for verification steps covering SC-1 through SC-6.

## Next Phase Readiness

- Phase 5 (Frontend Wiring): All Phase 4 LLM infrastructure has test coverage. Safe to proceed with frontend wiring once human checkpoint is approved.
- Re-run: `uv run pytest tests/ -x -q` after any Phase 5 changes to confirm no regressions.

---
*Phase: 04-llm-integration*
*Completed: 2026-05-08*
