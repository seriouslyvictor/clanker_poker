---
phase: 01-backend-foundation
plan: "02"
subsystem: testing
tags: [treys, poker, monte-carlo, pytest, hand-evaluation, equity]
dependency_graph:
  requires:
    - phase: 01-01
      provides: backend-package-structure (pyproject.toml, app/engine/__init__.py, tests/__init__.py)
  provides:
    - poker-math-engine (evaluate_hand, calculate_equity)
    - pytest-coverage-all-9-ranks
  affects: [01-03, phase-2-game-state-machine]
tech_stack:
  added: []
  patterns:
    - singleton-evaluator (_evaluator = Evaluator() at module level — lookup tables loaded once)
    - pre-flop-guard (if len(community_cards) < 3: return None — guards treys KeyError)
    - board-first-evaluate (README convention: _evaluator.evaluate(community_cards, hole_cards))
    - monte-carlo-deck-filter (Deck().cards filtered by seen set — never range(52))
    - ties-as-loss (opp_score <= my_score counts as loss — conservative equity)
key_files:
  created:
    - backend/app/engine/poker_math.py
    - backend/tests/test_poker_math.py
  modified: []
key_decisions:
  - "evaluate_hand uses board-first convention (README style) with module docstring explaining argument order equivalence"
  - "calculate_equity uses opp_score <= my_score (ties count as loss) — conservative equity estimate matching RESEARCH.md pattern"
  - "100ms timing target met by wide margin: 21 tests complete in 0.25s total; 1000-sim MC subset well under 100ms"
  - "No n_simulations reduction needed — 1000-sim MC on treys lookup tables is very fast (~O(1) per evaluate call)"
patterns_established:
  - "Card ints always from Card.new() — never manual construction; module docstring enforces this"
  - "Deck().cards for full deck in MC — never range(52) or manual int ranges"
  - "Pre-flop guard before every evaluate() call — len(community_cards) < 3 check"
requirements_completed: [POKER-03, POKER-04]
duration: 2min
completed: "2026-05-03"
---

# Phase 1 Plan 02: Poker Math Engine Summary

**treys-backed hand evaluator and Monte Carlo equity calculator — all 9 ranks, kicker tiebreakers, and board counterfeiting verified by 21 pytest tests passing in 0.25s**

## Performance

- **Duration:** 1m 57s
- **Started:** 2026-05-03T00:37:29Z
- **Completed:** 2026-05-03T00:39:26Z
- **Tasks:** 2 (TDD: RED then GREEN)
- **Files created:** 2

## Accomplishments

- `evaluate_hand()` wraps treys Evaluator with pre-flop guard, board-first evaluate convention, and singleton instance for O(1) lookup reuse
- `calculate_equity()` implements Monte Carlo with 1000 simulations, proper deck filtering (Deck().cards minus seen set), and conservative tie-as-loss counting
- 21 pytest tests cover all 9 hand ranks (Royal Flush through High Card), kicker tiebreakers (K vs Q kicker on pair-of-aces board), board counterfeiting (KK vs AA-on-board = Two Pair), pre-flop guard returning None, equity speed (< 100ms for 1000 sims), multiway equity (3 opponents), and pot_odds=None contract

## Test Results

```
21 passed in 0.25s
```

All 9 hand ranks explicitly tested and passing:
- Royal Flush: `test_royal_flush_scores_lowest` (hand_strength == 1)
- Straight Flush: `test_straight_flush`
- Four of a Kind: `test_four_of_a_kind`
- Full House: `test_full_house`
- Flush: `test_flush`
- Straight: `test_straight`
- Three of a Kind: `test_three_of_a_kind`
- Two Pair: `test_two_pair` and `test_board_counterfeiting`
- Pair: `test_one_pair`

## Timing

- `test_completes_in_under_100ms` passed: 1000-simulation MC completed well under 0.1s
- Full 21-test suite: 0.25s total
- No n_simulations reduction needed (1000 samples are fine on modern hardware with treys O(1) lookups)

## Function Signatures (for Phase 2 planner reference)

```python
def evaluate_hand(
    hole_cards: list[int],      # 2 treys card ints from Card.new()
    community_cards: list[int], # 0-5 treys card ints from Card.new()
) -> dict:
    # Returns {"hand_strength": int | None, "hand_name": str | None}
    # hand_strength: 1-7462 (lower=better, 1=Royal Flush, 7462=worst High Card)
    # Returns None for both fields if len(community_cards) < 3

def calculate_equity(
    hole_cards: list[int],          # 2 treys card ints from Card.new()
    community_cards: list[int],     # 0-5 treys card ints from Card.new()
    num_opponents: int = 1,
    n_simulations: int = 1000,
) -> dict:
    # Returns {"hand_strength": int | None, "win_probability": float, "pot_odds": None}
    # hand_strength: None if len(community_cards) < 3 (pre-flop)
    # win_probability: 0.0-1.0 (Monte Carlo estimate, ties count as loss)
    # pot_odds: always None — caller computes call_amount / (pot + call_amount)
```

## Task Commits

TDD cycle (RED then GREEN):

1. **Task 1: test_poker_math.py — RED phase** - `142accc` (test)
2. **Task 2: poker_math.py — GREEN phase** - `1a969dd` (feat)

**Plan metadata:** (see final commit below)

## Files Created

- `backend/app/engine/poker_math.py` — treys wrapper: evaluate_hand() and calculate_equity(); singleton _evaluator; pre-flop guard; Monte Carlo loop
- `backend/tests/test_poker_math.py` — 21 pytest tests in TestEvaluateHand (15) and TestCalculateEquity (6)

## Decisions Made

1. **Board-first evaluate() convention** — Module follows README convention (`evaluate(board, hole)`) rather than source signature (`evaluate(hand, board)`). Both produce identical scores (method concatenates lists). Documented in module docstring per T-02-01 mitigation.

2. **Ties count as loss** — `opp_score <= my_score` in the win condition means a tie (equal scores) is treated as a loss, producing a conservative equity estimate. This matches the RESEARCH.md pattern comment.

3. **1000 simulations kept as default** — No reduction needed; timing target met with room to spare. The `test_completes_in_under_100ms` test passed first try.

4. **No additional Python pinning needed** — Python 3.13.13 from Plan 01 continues to work; treys 0.1.8 operates cleanly.

## Deviations from Plan

None — plan executed exactly as written. TDD RED/GREEN cycle followed. All acceptance criteria met on first implementation attempt. No fallbacks (no n_simulations reduction, no Python pin) were needed.

## Security Review (Threat Model Compliance)

| Threat | Disposition | Status |
|--------|-------------|--------|
| T-02-01: Card ints from Card.new() only | mitigate | DONE — module docstring explicitly warns; tests use Card.new() exclusively |
| T-02-02: Monte Carlo DoS | accept | n_simulations not user-controlled in Phase 1; noted for Phase 4 |
| T-02-03: calculate_equity in logs | accept | Returns probabilities (0.0-1.0) and score (1-7462); no PII or secrets |

## Known Stubs

None — poker_math.py produces real computation results. No hardcoded values, no placeholder probabilities, no mock data.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. poker_math.py is a pure computation module with no I/O.

## TDD Gate Compliance

- RED gate: commit `142accc` `test(01-02): add failing test suite for poker_math — RED phase`
- GREEN gate: commit `1a969dd` `feat(01-02): implement poker_math.py — treys wrapper + Monte Carlo equity (GREEN)`

Both gates present in correct order. No REFACTOR gate needed (implementation is clean as written).

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. treys is a pure Python library installed via uv.

## Next Phase Readiness

- `evaluate_hand()` and `calculate_equity()` are ready for Phase 2 game state machine import: `from app.engine.poker_math import evaluate_hand, calculate_equity`
- The singleton `_evaluator` pattern ensures fast startup (lookup tables loaded once at import)
- Pre-flop guard handles 0/1/2 community card states that the game state machine will encounter
- pot_odds=None contract is established — Phase 2 game engine will compute pot odds from call_amount and pot_size

---
*Phase: 01-backend-foundation*
*Completed: 2026-05-03*
