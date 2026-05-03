---
phase: 01-backend-foundation
reviewed: 2026-05-02T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - backend/app/config.py
  - backend/app/main.py
  - backend/app/api/health.py
  - backend/app/engine/poker_math.py
  - backend/tests/test_poker_math.py
  - backend/tests/test_litellm_providers.py
  - backend/.env.example
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-05-02
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Seven backend scaffold files reviewed. The FastAPI application scaffold (`main.py`, `health.py`, `config.py`) is clean — CORS wiring is correct, settings are properly cached, and the lifespan stub is well-structured for future Redis integration. The LiteLLM integration test is appropriately guarded against missing env vars.

The poker math engine (`poker_math.py`) is the only file with substantive issues. Three input validation gaps exist in `calculate_equity`: a division-by-zero on `n_simulations=0`, silent wrong results on `num_opponents=0`, and unchecked deck indexing when `num_opponents` exceeds a safe maximum. None of these are reachable in the normal game flow (1 opponent, 1000 simulations), but they represent unguarded public function contracts that could cause hard-to-debug failures if called incorrectly from future game engine code.

---

## Warnings

### WR-01: Division by zero when `n_simulations=0` in `calculate_equity`

**File:** `backend/app/engine/poker_math.py:116`
**Issue:** `wins / n_simulations` raises `ZeroDivisionError` with no guard. The parameter has a default of 1000 but is exposed in the public signature, so any caller passing `n_simulations=0` crashes at the return statement.
**Fix:**
```python
if n_simulations <= 0:
    raise ValueError(f"n_simulations must be >= 1, got {n_simulations}")
```
Add this at the top of `calculate_equity`, before the deck construction.

---

### WR-02: Silent wrong result when `num_opponents=0` in `calculate_equity`

**File:** `backend/app/engine/poker_math.py:98-109`
**Issue:** When `num_opponents=0`, the inner `for` loop never executes, `beat_all` remains `True`, and every simulation increments `wins`. The function returns `win_probability=1.0` for any hand regardless of strength. This is a semantically wrong result with no error raised.
**Fix:**
```python
if num_opponents <= 0:
    raise ValueError(f"num_opponents must be >= 1, got {num_opponents}")
```
Add alongside the `n_simulations` guard at the top of `calculate_equity`.

---

### WR-03: No bounds check before slicing opponent hole cards from remaining deck

**File:** `backend/app/engine/poker_math.py:99-101`
**Issue:** Opponent cards are taken from `remaining_deck[opp_start + i*2 : opp_start + i*2 + 2]`. Python slice syntax returns an empty list (or a single-element list) without raising an exception if the index exceeds the list length. When `num_opponents` is large enough that the required cards (`cards_to_deal + num_opponents * 2`) exceed `len(remaining_deck)`, `opp_hole` silently becomes `[]` or `[card]`. Passing fewer than 2 hole cards to `_evaluator.evaluate()` will either raise an opaque treys error or produce a garbage score that corrupts the win probability.

The current default game scenario (1 opponent, flop/turn/river) is never affected — `remaining_deck` is always large enough. But the function's contract does not document a maximum `num_opponents`, and `test_multiway_equity` only covers 3 opponents.

**Fix:** Add a pre-loop bounds check:
```python
cards_needed = cards_to_deal + num_opponents * 2
if cards_needed > len(remaining_deck):
    raise ValueError(
        f"Not enough cards in deck: need {cards_needed} "
        f"({cards_to_deal} runout + {num_opponents} opponents * 2), "
        f"have {len(remaining_deck)}"
    )
```
Insert this after `cards_to_deal` is computed (line 89) and before the simulation loop.

---

## Info

### IN-01: `evaluate_hand` does not validate hole card count

**File:** `backend/app/engine/poker_math.py:28-52`
**Issue:** The function accepts any `list[int]` for `hole_cards` but expects exactly 2 cards. Passing 0 or 1 cards does not raise a descriptive error — treys will either raise an opaque `KeyError` from its lookup tables or return a nonsensical score.
**Fix:**
```python
if len(hole_cards) != 2:
    raise ValueError(f"hole_cards must contain exactly 2 cards, got {len(hole_cards)}")
```
Add at the top of `evaluate_hand` (and optionally `calculate_equity`).

---

### IN-02: `env_file=".env"` is resolved relative to process cwd, not the config file

**File:** `backend/app/config.py:17`
**Issue:** `SettingsConfigDict(env_file=".env")` resolves `.env` relative to wherever `uvicorn` is invoked, not relative to `config.py`. Running the server from the repo root works correctly. Running from any other directory silently skips `.env` loading with no warning — pydantic-settings ignores missing env files by default.
**Fix:** Consider using an absolute path derived from the file's location to make the config location explicit:
```python
from pathlib import Path
_BASE_DIR = Path(__file__).resolve().parent.parent.parent  # repo root

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_BASE_DIR / ".env"),
        extra="ignore",
    )
```
Alternatively, document in the project README that the server must be started from the repo root.

---

_Reviewed: 2026-05-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
