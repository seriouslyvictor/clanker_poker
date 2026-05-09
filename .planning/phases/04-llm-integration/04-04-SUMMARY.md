---
phase: 04-llm-integration
plan: "04"
subsystem: backend/app/engine
tags: [llm, litellm, game-engine, session, broadcast, budget, circuit-breaker, sse, config-driven]
dependency_graph:
  requires:
    - backend/app/ai/decision.py (make_llm_decision_fn factory — Plan 03)
    - backend/app/ai/archetypes.py (assign_archetypes — Plan 01)
    - backend/app/ai/budget.py (BudgetTracker, CircuitBreaker — Plan 01)
    - backend/app/broadcast/publisher.py (publish — Phase 3)
    - backend/app/engine/models.py (GameState.current_bet — Plan 01)
    - models.config.json (player roster — Quick Task 260503-01)
  provides:
    - backend/app/engine/session.py (config-driven player init; player_models dict)
    - backend/app/engine/game.py (per-action broadcast D-03; current_bet sync)
    - backend/app/game_loop.py (LLM decision fn wired; BudgetTracker + CircuitBreaker per session)
  affects:
    - Phase 5 (frontend wiring — game loop now emits per-action SSE events)
    - Phase 6 (viewer experience — game loop runs; demand-gate deferred to Phase 6)
tech-stack:
  added:
    - json + pathlib for models.config.json loading (session.py)
    - Two-path config resolution: worktree root + project root fallback
  patterns:
    - Config-driven player init: session.py reads models.config.json; player_models dict on GameSession
    - Parallel dict pattern: Player (Pydantic, no litellm_model) + player_models dict (str->str)
    - Per-action broadcast: run_betting_round() calls broadcast_fn after each player action (D-03)
    - current_bet sync: game_state.current_bet = betting_state.current_bet on init + after each action
    - Per-session budget reset: BudgetTracker + CircuitBreaker created fresh per GameSession
    - Optional player_models in make_llm_decision_fn: dict lookup > _get_model() fallback
key-files:
  created: []
  modified:
    - backend/app/engine/session.py (replaced _make_players with _load_players_from_config; added player_models)
    - backend/app/engine/game.py (run_betting_round: broadcast_fn param; current_bet sync; per-action broadcast)
    - backend/app/game_loop.py (full LLM wiring: archetypes, budget, circuit, player_models, decision_fn)
    - backend/app/ai/decision.py (make_llm_decision_fn: player_models param added, optional for backward compat)
    - backend/tests/test_session.py (SC9 tests updated from mock IDs to config-driven IDs; 2 new tests added)
key-decisions:
  - "Player.litellm_model NOT added to Pydantic model — would break validation; stored in parallel player_models dict on GameSession instead"
  - "run_betting_round() gains broadcast_fn param (Optional) so per-action SSE broadcast is inside betting loop, not just at phase transitions"
  - "game_state.current_bet synced twice per action: on BettingRoundState init and after each action (raise updates current_bet)"
  - "player_models param in make_llm_decision_fn is Optional with fallback to _get_model() for backward compat with Plan 03 tests"
  - "_find_models_config() uses two-path resolution: worktree root first, then project root 3 levels above (for .claude/worktrees/ layout)"
  - "Viewer presence check deferred to Phase 6 — game loop runs unconditionally in Phase 4 for dev purposes"
patterns-established:
  - "Config path resolution: try worktree root (parent^4 of session.py), then project root (worktree_root.parent.parent.parent)"
  - "Per-action broadcast pattern: broadcast_fn flows from game_loop -> session.run -> run_hand -> run_betting_round"
requirements-completed: [AI-01, AI-02, AI-03, INFRA-05]
duration: ~15min
completed: 2026-05-08
---

# Phase 4 Plan 04: LLM Engine Wiring Summary

**Config-driven player init from models.config.json; per-action SSE broadcast wired into run_betting_round(); game_loop.py constructs BudgetTracker + CircuitBreaker + archetype map + LLM decision closure per session.**

## Performance

- **Duration:** ~15 minutes
- **Started:** 2026-05-08
- **Completed:** 2026-05-08
- **Tasks:** 2
- **Files modified:** 5 (session.py, game.py, game_loop.py, decision.py, test_session.py)

## Accomplishments

- Replaced mock `_make_players()` with `_load_players_from_config()` reading `models.config.json`; `GameSession.player_models` dict maps player_id to LiteLLM model string
- `game.py run_betting_round()` now accepts `broadcast_fn`, syncs `game_state.current_bet` from `betting_state.current_bet` on init and after each action, and calls `await broadcast_fn(game_state)` after every player action (D-03 per-action broadcast)
- `game_loop.py` fully wires LLM integration: `assign_archetypes`, `BudgetTracker`, `CircuitBreaker`, `make_llm_decision_fn(player_models=...)`, `budget.summary()` logged at session end; `CancelledError` propagated
- `make_llm_decision_fn()` extended with optional `player_models` param — uses dict lookup over `_get_model()` fallback for efficiency and correctness

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace session.py _make_players() with config-driven init** - `a245d99` (feat)
2. **Task 2: Patch game.py (current_bet sync + per-action broadcast) + wire game_loop.py** - `4069409` (feat)

## Files Created/Modified

- `backend/app/engine/session.py` — Replaced mock init with `_load_players_from_config()`; added `_find_models_config()` two-path resolver; added `player_models: dict[str, str]` on `GameSession`
- `backend/app/engine/game.py` — `run_betting_round()` gains `broadcast_fn: Optional[BroadcastFn]` param; `game_state.current_bet` synced on init and per-action; `await broadcast_fn(game_state)` inside betting loop; all 4 call sites updated
- `backend/app/game_loop.py` — Full replacement: archetypes, budget, circuit, player_models, decision_fn constructed per session; `budget.summary()` logged; `CancelledError` propagated
- `backend/app/ai/decision.py` — `make_llm_decision_fn()` gains `player_models: dict[str, str] | None = None`; closure uses `(player_models or {}).get(player.id) or _get_model(player)`
- `backend/tests/test_session.py` — SC9 tests updated from mock player assertions to config-driven values; `test_player_models_dict` and `test_n_players_cap_respected` added

## Decisions Made

- `player_models` stored as a separate dict on `GameSession` rather than adding `litellm_model` field to `Player` Pydantic model — adding it would break SSE serialization validation and violate the Player contract used by game.py, tests, and the TypeScript frontend.
- `run_betting_round()` receives `broadcast_fn` as an optional parameter (default `None`) — this preserves backward compatibility with all Phase 2/3 tests that call it without a broadcast fn.
- `game_state.current_bet` is synced twice: once at `BettingRoundState` init (for pre-flop vs post-flop starting value), and again after each action inside the loop (to pick up raise updates). This ensures `reconstruct_valid_actions()` in `decision.py` always sees the correct value.
- `_find_models_config()` uses a two-step path search (worktree root, then project root 3 levels up) to work in both local dev and git worktree environments where `models.config.json` is untracked and lives only in the project root.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added broadcast_fn parameter to run_betting_round()**
- **Found during:** Task 2 (game.py patch)
- **Issue:** The plan's action said to add `await broadcast_fn(game_state)` inside `run_betting_round()`, but the function signature did not include `broadcast_fn` as a parameter. Without the parameter, broadcast_fn would be unresolvable at call time.
- **Fix:** Added `broadcast_fn: Optional[BroadcastFn] = None` to `run_betting_round()` signature and updated all 4 call sites in `run_hand()` to pass `broadcast_fn=broadcast_fn`.
- **Files modified:** backend/app/engine/game.py
- **Verification:** All 235 tests pass; `await broadcast_fn(game_state)` confirmed present in game.py
- **Committed in:** 4069409 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — missing critical functionality)
**Impact on plan:** Required for D-03 per-action broadcast to function at all. No scope creep.

## Issues Encountered

None — aside from the deviation above (missing broadcast_fn param in run_betting_round signature), execution matched the plan exactly.

## Known Stubs

None — all wiring is real. `_get_model()` fallback in decision.py reads models.config.json at call time (from Plan 03); Plan 04 replaces it with the `player_models` dict lookup which takes priority. No placeholder data flows to UI rendering.

## Threat Flags

No new network endpoints or auth paths. Per-action broadcast (D-03) increases Redis publish frequency (up to 4x per street vs Phase 3's 1x); the existing QueueFull guard in broker.py protects slow clients (T-04-14 mitigated as designed). BudgetTracker + CircuitBreaker(threshold=3) protect against cost runaway (T-04-15 mitigated).

## Next Phase Readiness

- Phase 5 (Frontend Wiring): SSE now emits per-action state updates with `current_bet` populated; frontend can render real-time chip/action changes within a betting round
- Phase 6 (Viewer Experience): Game loop runs unconditionally — demand-gate ("Start a Game" button / viewer presence check) deferred to Phase 6 as planned

---
*Phase: 04-llm-integration*
*Completed: 2026-05-08*
