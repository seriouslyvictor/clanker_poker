---
phase: 04-llm-integration
plan: "03"
subsystem: backend/app/ai
tags: [llm, prompts, decision, archetypes, fallback, circuit-breaker, streaming, tdd]
dependency_graph:
  requires:
    - backend/app/ai/archetypes.py (ARCHETYPES list, Archetype dataclass)
    - backend/app/ai/budget.py (BudgetTracker, CircuitBreaker)
    - backend/app/ai/models.py (LLMDecisionResponse, ReasoningEntry)
    - backend/app/broadcast/publisher.py (publish_reasoning)
    - backend/app/engine/models.py (Action action_type field, GameState.current_bet, DecisionFn)
    - backend/app/engine/cards.py (new_card for unicode->treys conversion)
    - backend/app/engine/poker_math.py (calculate_equity)
    - models.config.json (player_id -> litellmModel mapping)
  provides:
    - backend/app/ai/prompt.py (build_system_prompt, build_user_prompt)
    - backend/app/ai/decision.py (make_llm_decision_fn closure, reconstruct_valid_actions, _fallback_action)
  affects:
    - backend/app/engine/game_loop.py (Plan 04 wires make_llm_decision_fn as decision_fn)
    - Plans 04+05 (game loop wiring and integration tests)
tech_stack:
  added:
    - litellm.acompletion with stream=True (streaming LLM calls)
    - litellm.exceptions.Timeout (aliased as APITimeoutError — litellm version lacks APITimeoutError)
    - asyncio.wait_for dual-layer timeout pattern
  patterns:
    - Factory/closure pattern: make_llm_decision_fn captures archetypes/redis/budget/circuit; returned fn matches DecisionFn exactly
    - D-04 system+user message split (stable system, volatile user)
    - Fallback pyramid: raise (if win_prob >= raise_freq) > call (>= hand_looseness) > check > fold
    - _append_reasoning_to_state: append ReasoningEntry before returning so publish() snapshot captures it (OQ-3 fix)
    - reconstruct_valid_actions: GameState.current_bet reconstruction (no BettingRoundState access)
    - TDD: RED (failing test) -> GREEN (implementation) per task
key_files:
  created:
    - backend/app/ai/prompt.py
    - backend/app/ai/decision.py
    - backend/tests/test_ai_prompt.py
    - backend/tests/test_ai_decision.py
  modified: []
decisions:
  - "litellm.exceptions.Timeout aliased as APITimeoutError — installed litellm version does not export APITimeoutError directly; Timeout is the correct exception class"
  - "new_card(c.r, c.s) used instead of card_to_treys() — cards.py exposes new_card(); card_to_treys() does not exist in the codebase"
  - "publish_reasoning() guarded by redis_client is not None — allows decision.py to be unit-tested without a Redis connection"
  - "_get_model() reads models.config.json at call time from 4 levels up (worktree-root/models.config.json); Plan 04 will replace with player_models dict injection into make_llm_decision_fn"
  - "test_circuit_open_returns_fallback uses dynamic path resolution for models.config.json (project root vs worktree root) to work in both environments"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-08"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 0
---

# Phase 4 Plan 03: LLM Prompt Builder + Decision Function Summary

**One-liner:** build_system_prompt()/build_user_prompt() assemble persona+hand-state prompts with computed pot_odds; make_llm_decision_fn() factory returns an archetype-biased streaming LLM decision closure that never raises to callers.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Failing tests for prompt.py | b10bc92 | tests/test_ai_prompt.py |
| 1 GREEN | Create backend/app/ai/prompt.py | 2f8387e | app/ai/prompt.py |
| 2 RED | Failing tests for decision.py | 39018cf | tests/test_ai_decision.py |
| 2 GREEN | Create backend/app/ai/decision.py | 26d951a | app/ai/decision.py |

TDD commits:
- b10bc92: test(04-03): add failing tests for prompt.py — system/user prompt builders (RED)
- 2f8387e: feat(04-03): create backend/app/ai/prompt.py (GREEN)
- 39018cf: test(04-03): add failing tests for decision.py — fallback, reconstruct, factory (RED)
- 26d951a: feat(04-03): create backend/app/ai/decision.py (GREEN)

## Verification Results

All plan verification commands passed:

```
system ok: True
Gunslinger: raise (expect raise)
Rock: fold (expect fold)
233 passed in 4.53s
```

- `build_system_prompt()` contains player.name, archetype.name, archetype.description, fenced JSON format block
- `build_user_prompt()` contains Win probability (72%), Pot odds (25% for call=40/pot=120), Hand strength, Available actions, Pot, Opponents
- Pre-flop edge case: hand_strength=None → "n/a (pre-flop)" in output
- Empty board edge case: community_cards=[] → "Board: [none]" (no crash)
- `_fallback_action(Gunslinger, win_prob=0.45)` → raise (>= raise_freq=0.40)
- `_fallback_action(Rock, win_prob=0.45)` → fold (< hand_looseness=0.65)
- `make_llm_decision_fn({}, ...)` returns async callable (asyncio.iscoroutinefunction=True)
- `grep "Action(type=" backend/app/ai/decision.py` → 0 matches
- CancelledError always re-raised in both try blocks in `_call_llm_streaming`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] litellm.exceptions.APITimeoutError import failure**
- **Found during:** Task 2 implementation (first test run)
- **Issue:** `from litellm.exceptions import APITimeoutError` raised ImportError — installed litellm version does not export `APITimeoutError`; the class is named `Timeout`
- **Fix:** `from litellm.exceptions import Timeout as APITimeoutError` — same semantics, correct class
- **Files modified:** backend/app/ai/decision.py line 31
- **Commit:** 26d951a (same GREEN commit)

**2. [Rule 3 - Blocking] card_to_treys() does not exist in cards.py**
- **Found during:** Task 2 read phase (pre-implementation)
- **Issue:** Plan action code imports `from app.engine.cards import card_to_treys` — this function does not exist. cards.py exposes `new_card(r, s)` for unicode→treys conversion.
- **Fix:** Used `from app.engine.cards import new_card` and `new_card(c.r, c.s)` inline. No separate helper needed.
- **Files modified:** backend/app/ai/decision.py (import section and llm_decision_fn body)
- **Commit:** 26d951a

**3. [Rule 2 - Missing Critical Functionality] publish_reasoning() guarded by redis_client check**
- **Found during:** Task 2 implementation
- **Issue:** Original plan calls `publish_reasoning()` unconditionally in `_call_llm_streaming`. In unit tests (no Redis), this would crash.
- **Fix:** Added `if redis_client is not None:` guard before every `publish_reasoning()` call in `_call_llm_streaming` and `_fallback_action`. This follows the established pattern in publisher.py.
- **Files modified:** backend/app/ai/decision.py
- **Commit:** 26d951a

**4. [Rule 2 - Missing Critical Functionality] Test path resolution for models.config.json**
- **Found during:** Task 2 RED test execution in worktree
- **Issue:** `test_circuit_open_returns_fallback` used `Path(__file__).parent.parent.parent / "models.config.json"` — resolves to the worktree root, but models.config.json is in the project root (3 levels above worktree root in `.claude/worktrees/` hierarchy)
- **Fix:** Added dynamic path resolution: try worktree root first, fall back to project root. Ensures test works in both environments.
- **Files modified:** backend/tests/test_ai_decision.py
- **Commit:** 26d951a

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| Task 1 RED | b10bc92 | PASS — import fails on missing module |
| Task 1 GREEN | 2f8387e | PASS — 23/23 tests pass |
| Task 2 RED | 39018cf | PASS — import fails on missing module |
| Task 2 GREEN | 26d951a | PASS — 23/23 tests pass (233 total) |

## Known Stubs

None — all fields are fully implemented. The `_get_model()` function reads `models.config.json` at call time; this is a temporary approach documented in Plan 04's interface note. It is not a stub — it produces correct model strings for the 4 configured players. Plan 04 will replace it with closure injection for efficiency.

## Threat Flags

No new network endpoints or auth paths introduced. The files implement:
- T-04-08 mitigation: `_parse_response()` regex extraction + Pydantic validation; invalid actions trigger fallback; raise amounts clamped to player.chips
- T-04-09 mitigation: `asyncio.wait_for(2s)` + `timeout=` on acompletion dual-layer; circuit breaker (3 errors trips)
- T-04-12 mitigation: `max_tokens=300` on every call; `BudgetTracker.record()` called after every success
- T-04-13 mitigation: no user-supplied text enters prompts; all data is server-side engine state

No new threats beyond the plan's threat model.

## Self-Check: PASSED

Files exist:
- FOUND: backend/app/ai/prompt.py
- FOUND: backend/app/ai/decision.py
- FOUND: backend/tests/test_ai_prompt.py
- FOUND: backend/tests/test_ai_decision.py

Commits exist:
- b10bc92: test RED — prompt.py tests
- 2f8387e: feat GREEN — prompt.py
- 39018cf: test RED — decision.py tests
- 26d951a: feat GREEN — decision.py

No unexpected file deletions in any commit.
