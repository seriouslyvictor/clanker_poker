# Phase 2: Game State Machine — Pattern Map

**Mapped:** 2026-05-03
**Files analyzed:** 5 new files
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/engine/cards.py` | utility | transform | `backend/app/engine/poker_math.py` | role-match (same engine dir, same treys API) |
| `backend/app/engine/models.py` | model | transform | `backend/app/config.py` | role-match (Pydantic BaseModel/BaseSettings, same stack) |
| `backend/app/engine/game.py` | service | event-driven | `backend/app/engine/poker_math.py` | role-match (primary engine analog, treys usage) |
| `backend/app/engine/session.py` | service | event-driven | `backend/app/engine/poker_math.py` | role-match (engine layer, async context) |
| `backend/tests/test_game_engine.py` | test | batch | `backend/tests/test_poker_math.py` | exact (same test file structure, same runner) |

---

## Pattern Assignments

### `backend/app/engine/cards.py` (utility, transform)

**Analog:** `backend/app/engine/poker_math.py`

**Imports pattern** (`poker_math.py` lines 21-23):
```python
import random
from treys import Card, Deck, Evaluator
```
For `cards.py`, import only what is needed:
```python
from treys import Card as TreysCard
```

**Core pattern** (`poker_math.py` lines 28-52 — function signature + guard + return dict):
```python
def evaluate_hand(hole_cards: list[int], community_cards: list[int]) -> dict:
    if len(community_cards) < 3:
        return {"hand_strength": None, "hand_name": None}
    score = _evaluator.evaluate(community_cards, hole_cards)
    rank_class = _evaluator.get_rank_class(score)
    hand_name = _evaluator.class_to_string(rank_class)
    return {"hand_strength": score, "hand_name": hand_name}
```
Cards.py follows the same structure: module-level constants, plain functions (no class), return `dict`.

**Module-level constant pattern** (`poker_math.py` line 25):
```python
_evaluator = Evaluator()  # single instance — lookup tables loaded once at import
```
Apply same convention: underscore-prefixed module-level dicts for rank/suit maps, initialized once at import.

**Docstring convention** (`poker_math.py` lines 1-20):
```python
"""
poker_math.py — thin wrapper around treys for hand evaluation and equity calculation.

treys card integer format: Card.new('Ah') returns a specific 32-bit int.
Never construct card ints manually — they must come from Card.new() to match
the treys lookup tables. ...
"""
```
`cards.py` must include an equivalent module-level docstring explaining the treys ↔ `{s, r}` boundary contract and the unicode-vs-char encoding rule.

---

### `backend/app/engine/models.py` (model, transform)

**Analog:** `backend/app/config.py`

**Imports pattern** (`config.py` lines 1-7):
```python
import json
import pathlib
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
```
For `models.py`, swap `pydantic_settings` for core pydantic:
```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Optional, Literal
```

**Pydantic model config pattern** (`config.py` lines 16-22):
```python
class Settings(BaseSettings):
    player_models: list[str] = Field(default_factory=_default_player_models)
    llm_timeout_seconds: int = 8
    cors_origins: list[str] = ["http://localhost:3000"]
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```
For `models.py`, use `ConfigDict` with `alias_generator`:
```python
class Player(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    chips: int
    hole_cards: list[Card]   # → holeCards in JSON via alias_generator
    is_folded: bool = False  # → isFolded
```
The `populate_by_name=True` setting is required so code can construct models using Python snake_case field names even when aliases are set.

**TypeScript JSON contract** (`app/_components/types.ts` lines 1-48):
```typescript
export type Card = { s: string; r: string };
export type ActionType = 'fold' | 'call' | 'raise' | 'check';

export interface Player {
  id: ModelId;
  name: string;
  org: string;
  color: string;
  deck: string;
  chips: number;
  holeCards: Card[];
  action: ActionType | null;
  bet: number;
  isFolded: boolean;
  isActive: boolean;
  isWinner: boolean;
}

export interface GameState {
  phase: string;
  pot: number;
  communityCards: Card[];
  players: Player[];
  showCards: boolean;
  reasoning: ReasoningEntry[];
  winner: number | null;
  winnerHand: string;
}
```
Every Python field name must either be an exact camelCase match or must alias to one. The `alias_generator=to_camel` on `GameState` and `Player` models ensures `community_cards` → `communityCards`, `hole_cards` → `holeCards`, `is_folded` → `isFolded`, etc.

Fields that are already camelCase-safe single words (`phase`, `pot`, `chips`, `name`, `color`, `deck`, `bet`, `org`) need no aliasing. `Card` model has only single-char fields `s` and `r` — no aliasing needed; do NOT add `alias_generator` to `Card`.

---

### `backend/app/engine/game.py` (service, event-driven)

**Analog:** `backend/app/engine/poker_math.py`

**Imports pattern** (`poker_math.py` lines 21-23):
```python
import random
from treys import Card, Deck, Evaluator
```
`game.py` will extend this pattern — same treys imports plus Pydantic models and the cards/poker_math modules:
```python
from dataclasses import dataclass, field
from treys import Deck
from app.engine.cards import new_card, card_display
from app.engine.models import GameState, Player, Card, Action, ActionType
from app.engine.poker_math import evaluate_hand
from typing import Callable, Awaitable
```

**Function signature convention** (`poker_math.py` lines 28-29, 55-60):
```python
def evaluate_hand(hole_cards: list[int], community_cards: list[int]) -> dict:
def calculate_equity(
    hole_cards: list[int],
    community_cards: list[int],
    num_opponents: int = 1,
    n_simulations: int = 1000,
) -> dict:
```
`game.py` follows the same convention: typed function signatures, default arguments, return type annotations. Async functions use `async def` and return `GameState` or equivalent.

**Deck lifecycle pattern** (`poker_math.py` lines 85-86):
```python
remaining_deck = [c for c in Deck().cards if c not in seen]
```
In `game.py`, a fresh `Deck()` is created inside `run_hand()`, NOT at module or class level. This is consistent with how `poker_math.py` creates a disposable `Deck()` for each equity simulation.

**Guard/early-return pattern** (`poker_math.py` lines 44-47):
```python
if len(community_cards) < 3:
    return {"hand_strength": None, "hand_name": None}
```
`game.py` applies the same guard pattern for early-termination conditions (all-but-one folded → skip showdown, deal to showdown only if 2+ active players).

**`async def` entry point** (`main.py` lines 9-12):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup — Phase 3 will add Redis connection here
    yield
```
The async context in `main.py` confirms that `async def` coroutines are the project standard. `game.py`'s `run_hand(...)` function should be `async def` to match the decision seam's `async def make_decision(...)`.

---

### `backend/app/engine/session.py` (service, event-driven)

**Analog:** `backend/app/engine/poker_math.py` (structure) + `backend/app/main.py` (async pattern)

**Module-level singleton pattern** (`poker_math.py` line 25):
```python
_evaluator = Evaluator()  # single instance — lookup tables loaded once at import
```
`session.py` uses a class (`GameSession`) rather than a module-level singleton, but follows the same principle: expensive initialization (player list, starting chip stacks) happens once at construction, not per call.

**Async function pattern** (`main.py` lines 9-12):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
```
`session.py`'s `run(n_hands)` method is `async def`. The async lifecycle in `main.py` confirms this is idiomatic in this project.

**Import pattern** (`main.py` lines 1-6):
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.health import router as health_router
```
`session.py` follows the same `from app.engine.*` absolute import convention (not relative imports).

---

### `backend/tests/test_game_engine.py` (test, batch)

**Analog:** `backend/tests/test_poker_math.py`

**File-level docstring** (`test_poker_math.py` lines 1-6):
```python
"""
Tests for backend/app/engine/poker_math.py

Covers POKER-03 (all 9 hand ranks, kicker tiebreakers, board counterfeiting)
and POKER-04 (equity calculator speed and correctness).
"""
```
`test_game_engine.py` must begin with a similar docstring naming the requirements it covers (POKER-01, POKER-02, POKER-05) and the 5 success criteria.

**Import block** (`test_poker_math.py` lines 7-10):
```python
import time
import pytest
from treys import Card
from app.engine.poker_math import evaluate_hand, calculate_equity
```
`test_game_engine.py` extends this pattern — same `pytest` import, same `from app.engine.*` absolute import style:
```python
import asyncio
import pytest
from treys import Card
from app.engine.models import GameState, Player, Card as CardModel, Action
from app.engine.game import run_hand
from app.engine.session import GameSession
```

**Class-based test organization** (`test_poker_math.py` lines 13-123):
```python
class TestEvaluateHand:
    def test_returns_none_preflop(self):
        hole = [Card.new("Ah"), Card.new("Kd")]
        result = evaluate_hand(hole, [])
        assert result["hand_strength"] is None
```
One class per logical group. `test_game_engine.py` should use the same structure: `TestSingleHand`, `TestBettingOrder`, `TestShowdown`, `TestSession`, `TestChipConservation`.

**Arrange-Act-Assert pattern** (`test_poker_math.py` lines 26-30):
```python
def test_royal_flush_scores_lowest(self):
    hole = [Card.new("Ah"), Card.new("Kh")]
    board = [Card.new("Qh"), Card.new("Jh"), Card.new("Th")]
    result = evaluate_hand(hole, board)
    assert result["hand_strength"] == 1, f"Expected 1 (Royal Flush), got {result['hand_strength']}"
```
Same 3-phase structure: build inputs → call function → assert with descriptive failure message. All assertions include the f-string message showing actual value.

**Sync wrapper pattern for async** (no existing async tests, but `test_poker_math.py` tests are all sync):
The project currently has no `@pytest.mark.asyncio` tests. The RESEARCH.md recommends using sync `asyncio.run()` wrappers for full session tests (no decorator needed) and `@pytest.mark.asyncio` only where the decision seam must be awaited directly. `pyproject.toml` currently does NOT include `asyncio_mode` — this setting must be added for async tests to work.

**`pytest.mark.skipif` pattern** (`test_litellm_providers.py` lines 37-40):
```python
@pytest.mark.skipif(
    not _TEST_MODEL,
    reason="No test model configured — set LITELLM_TEST_MODEL or PLAYER_MODELS",
)
```
Tests that require external resources use `skipif`. Game engine tests require no external resources — skip this pattern entirely for `test_game_engine.py`.

---

## Shared Patterns

### Treys Card Integer Boundary
**Source:** `backend/app/engine/poker_math.py` lines 1-20 (module docstring), lines 22-23
**Apply to:** `cards.py`, `game.py`
```python
from treys import Card, Deck, Evaluator
# Cards MUST come from Card.new('Ah') — never construct card ints manually.
# Card.new() takes 2-char string: rank char + suit char ('h','s','d','c').
# Do NOT pass unicode suit symbols directly — they raise errors in treys 0.1.8.
```
`cards.py` is the single conversion boundary. `game.py` calls `new_card(r, s)` from `cards.py`; it never calls `TreysCard.new()` directly.

### Absolute Import Convention
**Source:** `backend/app/main.py` lines 5-6, `backend/tests/test_poker_math.py` lines 9-10
**Apply to:** All new files
```python
# main.py style:
from app.config import get_settings
from app.api.health import router as health_router

# test_poker_math.py style:
from app.engine.poker_math import evaluate_hand, calculate_equity
```
Never use relative imports (`from . import ...`). Always use `from app.engine.*` absolute paths. This works because `pyproject.toml` sets `pythonpath = ["."]`.

### Pydantic `ConfigDict` + `alias_generator`
**Source:** `backend/app/config.py` lines 16-22
**Apply to:** `models.py` — `Player` and `GameState` classes only (NOT `Card` or `Action`)
```python
from pydantic_settings import BaseSettings, SettingsConfigDict
# ...
model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```
In `models.py`, use `ConfigDict` (not `SettingsConfigDict`) with `alias_generator=to_camel` and `populate_by_name=True`. Only the models with camelCase-mapped fields need this — `Card` (fields `s`, `r`) and `Action` do not.

### Function Return Dict Convention
**Source:** `backend/app/engine/poker_math.py` lines 47, 52, 113-117
**Apply to:** `cards.py`
```python
return {"hand_strength": None, "hand_name": None}
return {"hand_strength": score, "hand_name": hand_name}
return {
    "hand_strength": hand_eval["hand_strength"],
    "win_probability": wins / n_simulations,
    "pot_odds": None,
}
```
`card_display()` returns a plain `dict` (not a `Card` Pydantic model) to keep `cards.py` dependency-free from `models.py`. The Pydantic `Card` model is constructed in `game.py` from the `card_display()` dict.

### pyproject.toml asyncio_mode
**Source:** `backend/pyproject.toml` lines 25-27 (current state — missing `asyncio_mode`)
**Apply to:** `pyproject.toml` modification task in PLAN.md
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
# Must add:
asyncio_mode = "strict"
```
Without `asyncio_mode`, async tests decorated with `@pytest.mark.asyncio` silently skip instead of running. The planner must include updating `pyproject.toml` as an explicit task before writing async tests.

---

## No Analog Found

No files are entirely without analog. All files have at least a role-match analog in the codebase.

| File | Analog Gap | Resolution |
|---|---|---|
| `game.py` — state machine loop | No existing event-driven state machine | Use RESEARCH.md Pattern 3 (BettingRoundState) + Pattern 4 (action order arithmetic) directly |
| `session.py` — multi-hand loop | No existing session management | Use RESEARCH.md architecture diagram (GameSession.run loop) as blueprint |
| `models.py` — `alias_generator=to_camel` | `config.py` uses `SettingsConfigDict`, not `ConfigDict` | RESEARCH.md Pattern 2 provides exact Pydantic v2 syntax; confirmed against local pydantic 2.12.5 |

---

## Metadata

**Analog search scope:** `backend/app/`, `backend/tests/`, `app/_components/`
**Files scanned:** 7 (poker_math.py, config.py, main.py, types.ts, test_poker_math.py, test_litellm_providers.py, pyproject.toml)
**Pattern extraction date:** 2026-05-03
