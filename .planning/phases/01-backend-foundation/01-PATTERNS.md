# Phase 1: Backend Foundation - Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 11
**Analogs found:** 0 / 11 (greenfield Python backend — no existing Python code in repo)

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `backend/pyproject.toml` | config | — | None — new file | no analog |
| `backend/.env.example` | config | — | None — new file | no analog |
| `backend/app/__init__.py` | config | — | None — new file | no analog |
| `backend/app/main.py` | entrypoint | request-response | None — new file | no analog |
| `backend/app/api/__init__.py` | config | — | None — new file | no analog |
| `backend/app/api/health.py` | route | request-response | None — new file | no analog |
| `backend/app/engine/__init__.py` | config | — | None — new file | no analog |
| `backend/app/engine/poker_math.py` | utility | transform | None — new file | no analog |
| `backend/tests/__init__.py` | config | — | None — new file | no analog |
| `backend/tests/test_poker_math.py` | test | transform | None — new file | no analog |
| `backend/tests/test_litellm_providers.py` | test | request-response | None — new file | no analog |

**Note on analog search:** The repo contains only a Next.js frontend at `app/`. There is no Python code anywhere in the codebase. The frontend's `_components/types.ts` provides the canonical `GameState`, `Player`, `Card`, `ReasoningEntry` TypeScript interfaces that Phase 3+ backend responses must serialize to match — but these are not code analogs for Phase 1 files. All patterns below are sourced from verified references in RESEARCH.md.

---

## Pattern Assignments

### `backend/pyproject.toml` (config)

**Source:** RESEARCH.md Pattern 6 — verified against docs.astral.sh/uv and pydevtools.com pytest+uv tutorial

**Complete file pattern:**
```toml
[project]
name = "clanker-poker-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.136.1",
    "uvicorn>=0.46.0",
    "treys>=0.1.8",
    "litellm>=1.83.0",
    "pydantic-settings>=2.14.0",
    "python-dotenv>=1.2.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "pytest>=9.0.0",
    "httpx>=0.27.0",  # for TestClient and Ollama probe
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]   # adds backend/ to sys.path so "from app.xxx" imports work

[tool.hatch.build.targets.wheel]
packages = ["app"]
```

**Key constraint:** `pythonpath = ["."]` under `[tool.pytest.ini_options]` is essential — it adds `backend/` to `sys.path` so `from app.config import Settings` resolves when pytest runs from the `backend/` directory. Without it, all test imports fail.

---

### `backend/.env.example` (config)

**Source:** RESEARCH.md section ".env.example Content" — verified against LiteLLM provider docs

**Complete file pattern:**
```ini
# OpenAI
OPENAI_API_KEY=

# Anthropic
ANTHROPIC_API_KEY=

# Google Gemini (AI Studio)
GEMINI_API_KEY=

# Ollama (local; default shown)
OLLAMA_API_BASE=http://localhost:11434

# CORS (comma-separated; Next.js dev port)
CORS_ORIGINS=["http://localhost:3000"]
```

**Security note:** `.env` (with real keys) must be in `.gitignore`. Only `.env.example` (empty values) is committed. Never log `settings.*_api_key` values.

---

### `backend/app/__init__.py` (config)

**Pattern:** Empty file. Makes `app` a Python package so `from app.main import app` resolves correctly.

```python
# intentionally empty
```

---

### `backend/app/main.py` (entrypoint, request-response)

**Source:** RESEARCH.md Pattern 3 — verified against fastapi.tiangolo.com/advanced/settings/ and fastapi.tiangolo.com/tutorial/cors/

**Note on `app/config.py`:** RESEARCH.md recommends creating `backend/app/config.py` to hold the `Settings` class. This file is not in CONTEXT.md's explicit file list but is required for `main.py` to work — it should be created alongside `main.py`.

**Complete `main.py` pattern:**
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from functools import lru_cache

from app.config import Settings
from app.api.health import router as health_router


@lru_cache
def get_settings() -> Settings:
    return Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup — Phase 3 will add Redis connection here
    yield
    # shutdown — Phase 3 will add Redis cleanup here


app = FastAPI(lifespan=lifespan)

# CORS stub — tested fully in Phase 5; present from day one per CONTEXT.md D-98
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
```

**`app/config.py` pattern** (create alongside `main.py`):
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    ollama_api_base: str = "http://localhost:11434"
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

**Anti-patterns to avoid:**
- Do NOT use `@app.on_event("startup")` — deprecated since FastAPI 0.93+; use `asynccontextmanager` lifespan
- Do NOT use `allow_origins=["*"]` with `allow_credentials=True` — FastAPI rejects this combination; use explicit origin list from settings
- Do NOT scatter `os.getenv()` calls — centralize in `Settings(BaseSettings)`

---

### `backend/app/api/__init__.py` (config)

**Pattern:** Empty file. Makes `api` a subpackage so `from app.api.health import router` resolves.

```python
# intentionally empty
```

---

### `backend/app/api/health.py` (route, request-response)

**Source:** RESEARCH.md Pattern 4 — verified against fastapi.tiangolo.com/reference/apirouter/

**Complete file pattern:**
```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}
```

**Response contract:** Returns `{"status": "ok"}` with HTTP 200. This endpoint will be called in Phase 5 CORS validation tests from the Next.js frontend.

---

### `backend/app/engine/__init__.py` (config)

**Pattern:** Empty file. Makes `engine` a subpackage so `from app.engine.poker_math import calculate_equity` resolves in Phase 2.

```python
# intentionally empty
```

---

### `backend/app/engine/poker_math.py` (utility, transform)

**Source:** RESEARCH.md Patterns 1 and 2, plus Code Examples section — verified against github.com/ihendley/treys source

**Complete file pattern:**
```python
"""
poker_math.py — thin wrapper around treys for hand evaluation and equity calculation.

treys card integer format: Card.new('Ah') returns a specific 32-bit int.
Never construct card ints manually — they must come from Card.new() to match lookup tables.

evaluator.evaluate() note: source signature is evaluate(self, hand, board) but README
shows evaluate(board, hand). Both produce identical scores (method concatenates both lists).
This module follows README convention: evaluate(board, hand) for consistency with
community examples. See RESEARCH.md Pitfall 1 for full explanation.
"""
import random
from treys import Card, Deck, Evaluator


_evaluator = Evaluator()  # single instance — lookup tables loaded once at import


def evaluate_hand(hole_cards: list[int], community_cards: list[int]) -> dict:
    """
    Evaluate hand strength for a given board state.

    Args:
        hole_cards: list of 2 treys card ints (from Card.new())
        community_cards: list of 3, 4, or 5 treys card ints

    Returns:
        dict with hand_strength (int 1-7462, lower=better) and hand_name (str)
        Returns {"hand_strength": None, "hand_name": None} if community_cards < 3
        (treys does not support evaluation with fewer than 5 total cards)
    """
    if len(community_cards) < 3:
        # Pre-flop guard: treys hand_size_map only supports 5, 6, 7 total cards
        # Calling evaluate() with 2 total cards raises KeyError
        return {"hand_strength": None, "hand_name": None}

    score = _evaluator.evaluate(community_cards, hole_cards)  # README convention: board first
    rank_class = _evaluator.get_rank_class(score)
    hand_name = _evaluator.class_to_string(rank_class)
    return {"hand_strength": score, "hand_name": hand_name}


def calculate_equity(
    hole_cards: list[int],
    community_cards: list[int],
    num_opponents: int = 1,
    n_simulations: int = 1000,
) -> dict:
    """
    Monte Carlo equity calculator. Simulates ~1000 random runouts.

    Args:
        hole_cards: list of 2 treys card ints
        community_cards: list of 0-5 treys card ints
        num_opponents: number of opponents to simulate
        n_simulations: number of Monte Carlo iterations (default 1000, ~10-40ms)

    Returns:
        {
            "hand_strength": int | None,  # treys score 1-7462 (lower=better); None if pre-flop
            "win_probability": float,      # 0.0-1.0
            "pot_odds": None,              # caller computes: call_amount / (pot + call_amount)
        }
    """
    wins = 0

    # Remove seen cards from the deck
    seen = set(hole_cards + community_cards)
    remaining_deck = [c for c in Deck().cards if c not in seen]

    cards_to_deal = 5 - len(community_cards)  # complete the board to 5 community cards

    for _ in range(n_simulations):
        random.shuffle(remaining_deck)
        runout_board = community_cards + remaining_deck[:cards_to_deal]

        my_score = _evaluator.evaluate(runout_board, hole_cards)

        beat_all = True
        opp_start = cards_to_deal
        for i in range(num_opponents):
            opp_hole = remaining_deck[opp_start + i * 2 : opp_start + i * 2 + 2]
            opp_score = _evaluator.evaluate(runout_board, opp_hole)
            if opp_score <= my_score:  # lower score = stronger hand; ties count as loss
                beat_all = False
                break

        if beat_all:
            wins += 1

    hand_eval = evaluate_hand(hole_cards, community_cards)

    return {
        "hand_strength": hand_eval["hand_strength"],
        "win_probability": wins / n_simulations,
        "pot_odds": None,  # caller computes: call_amount / (pot + call_amount)
    }
```

**Critical pitfalls to guard against (from RESEARCH.md):**
1. `evaluate()` with < 5 total cards raises `KeyError` — guard with `if len(community_cards) < 3`
2. Card ints must come from `Card.new()` — never construct manually
3. `Deck().cards` must be used for the full deck — never use `range(52)` or similar

---

### `backend/tests/__init__.py` (config)

**Pattern:** Empty file. Makes `tests` a package so pytest can discover tests reliably.

```python
# intentionally empty
```

---

### `backend/tests/test_poker_math.py` (test, transform)

**Source:** RESEARCH.md Code Examples section — treys workflow verified against github.com/ihendley/treys

**Pattern to follow:**
```python
"""
Tests for backend/app/engine/poker_math.py

Covers:
- Hand evaluation for all board sizes (flop/turn/river)
- Pre-flop guard (< 3 community cards returns None)
- Board counterfeiting (treys handles combinatorially)
- Monte Carlo equity returns valid probability range
- Kicker tiebreaker (treys 7462-score distinguishes kickers)
"""
import pytest
from treys import Card
from app.engine.poker_math import evaluate_hand, calculate_equity


class TestEvaluateHand:
    def test_returns_none_preflop(self):
        hole = [Card.new('Ah'), Card.new('Kd')]
        result = evaluate_hand(hole, [])
        assert result["hand_strength"] is None
        assert result["hand_name"] is None

    def test_returns_none_with_two_community_cards(self):
        hole = [Card.new('Ah'), Card.new('Kd')]
        board = [Card.new('Qh'), Card.new('Jc')]
        result = evaluate_hand(hole, board)
        assert result["hand_strength"] is None

    def test_royal_flush_scores_lowest(self):
        hole = [Card.new('Ah'), Card.new('Kh')]
        board = [Card.new('Qh'), Card.new('Jh'), Card.new('Th')]
        result = evaluate_hand(hole, board)
        assert result["hand_strength"] == 1  # treys: 1 = Royal Flush
        assert result["hand_name"] == "Royal Flush"

    def test_board_counterfeiting(self):
        # Player has KK; board has AA AA — player's best hand is KK + AA (Two Pair)
        # treys evaluates best 5 of 7 combinatorially
        hole = [Card.new('Kh'), Card.new('Kd')]
        board = [Card.new('Ah'), Card.new('As'), Card.new('2c'), Card.new('Jd'), Card.new('8s')]
        result = evaluate_hand(hole, board)
        assert result["hand_name"] == "Two Pair"

    def test_turn_evaluation(self):
        hole = [Card.new('Ah'), Card.new('Kd')]
        board = [Card.new('Qh'), Card.new('Jc'), Card.new('Th'), Card.new('2s')]
        result = evaluate_hand(hole, board)
        assert result["hand_strength"] is not None
        assert 1 <= result["hand_strength"] <= 7462


class TestCalculateEquity:
    def test_returns_valid_probability(self):
        hole = [Card.new('Ah'), Card.new('As')]
        board = [Card.new('Kh'), Card.new('Qd'), Card.new('Jc')]
        result = calculate_equity(hole, board)
        assert 0.0 <= result["win_probability"] <= 1.0

    def test_strong_hand_high_equity(self):
        # Pocket aces on neutral flop should win > 50% of the time
        hole = [Card.new('Ah'), Card.new('As')]
        board = [Card.new('2h'), Card.new('7d'), Card.new('Tc')]
        result = calculate_equity(hole, board, n_simulations=500)
        assert result["win_probability"] > 0.5

    def test_pot_odds_is_none(self):
        # pot_odds is caller responsibility — must be None from this function
        hole = [Card.new('Ah'), Card.new('Kd')]
        board = [Card.new('Qh'), Card.new('Jc'), Card.new('Th')]
        result = calculate_equity(hole, board)
        assert result["pot_odds"] is None

    def test_preflop_hand_strength_is_none(self):
        hole = [Card.new('Ah'), Card.new('Kd')]
        result = calculate_equity(hole, [], n_simulations=100)
        assert result["hand_strength"] is None
        assert 0.0 <= result["win_probability"] <= 1.0
```

---

### `backend/tests/test_litellm_providers.py` (test, request-response)

**Source:** RESEARCH.md Pattern 5 — verified against docs.pytest.org skipif pattern and docs.litellm.ai provider docs

**Complete file pattern:**
```python
"""
Integration tests for LiteLLM provider connectivity.

Each test is SKIPPED (not failed) when the corresponding env var is absent.
This allows CI to pass with zero API keys configured.

To run with real keys:
  cp .env.example .env
  # fill in keys
  uv run pytest tests/test_litellm_providers.py -v
"""
import os
import pytest
from litellm import completion


@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
def test_openai_provider():
    response = completion(
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=5,
    )
    assert response.choices[0].message.content is not None


@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
def test_anthropic_provider():
    response = completion(
        model="anthropic/claude-3-5-haiku-20241022",
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=5,
    )
    assert response.choices[0].message.content is not None


@pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
def test_gemini_provider():
    response = completion(
        model="gemini/gemini-2.0-flash",
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=5,
    )
    assert response.choices[0].message.content is not None


def test_ollama_provider():
    """Ollama has no API key — skip if server not reachable."""
    import httpx
    api_base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
    try:
        httpx.get(f"{api_base}/api/tags", timeout=2.0)
    except Exception:
        pytest.skip("Ollama not reachable")
    response = completion(
        model="ollama_chat/llama3",
        messages=[{"role": "user", "content": "ping"}],
        api_base=api_base,
        max_tokens=5,
    )
    assert response.choices[0].message.content is not None
```

**Pattern notes:**
- `ollama_chat/` prefix (not `ollama/`) routes to `/api/chat` endpoint — better response quality
- Ollama test uses an HTTP probe rather than env var check because Ollama has no API key
- `httpx` is already in dev dependencies (needed for both Ollama probe and FastAPI TestClient)
- All 4 providers return `response.choices[0].message.content` — OpenAI-compatible response shape

---

## Shared Patterns

### pydantic-settings Config Loading
**Source:** RESEARCH.md Pattern 3, Code Examples "pydantic-settings load pattern"
**Apply to:** `main.py`, any future service that needs settings
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    some_key: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Cached singleton — prevents re-reading .env on every call
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()
```
**Why:** Type validation at startup, early failure on misconfigured vars, integrates with FastAPI DI in Phase 4. Empty string defaults make keys optional — callers must check before use.

### treys Card Integer Format
**Source:** RESEARCH.md "Don't Hand-Roll" section, Pitfall 7
**Apply to:** `poker_math.py`, all future code that touches cards
```python
# ALWAYS use Card.new() — never construct ints manually
hole_cards = [Card.new('Ah'), Card.new('Kd')]
# ALWAYS use Deck().cards for the full deck
all_cards = Deck().cards  # list of 52 treys-format ints
# Card notation: rank (A K Q J T 9..2) + suit (h d c s), uppercase rank
```
**Why:** treys uses specific bit-packing; any int not from `Card.new()` produces garbage evaluation results or KeyError.

### Pre-flop Guard for treys evaluate()
**Source:** RESEARCH.md Pitfall 2
**Apply to:** `poker_math.py`, any future evaluation calls
```python
# treys hand_size_map only supports 5, 6, 7 total cards
# evaluate(board, hole) with len(board) < 3 raises KeyError
if len(community_cards) < 3:
    return {"hand_strength": None, ...}
```
**Why:** `evaluator.evaluate()` raises `KeyError: 2` or `KeyError: 4` when total cards < 5.

### Pytest Skip Pattern for Optional Infrastructure
**Source:** RESEARCH.md Pattern 5, Pitfall on provider tests
**Apply to:** `test_litellm_providers.py`, future tests for Redis/Ollama/optional services
```python
# For key-based providers:
@pytest.mark.skipif(not os.getenv("SOME_API_KEY"), reason="SOME_API_KEY not set")
def test_some_provider():
    ...

# For connection-based services (no key):
try:
    httpx.get(f"{base_url}/health", timeout=2.0)
except Exception:
    pytest.skip("Service not reachable")
```
**Why:** CI passes with zero external dependencies configured. Tests become integration-level validators when keys are present.

---

## No Analog Found

All 11 files have no codebase analog — this is a greenfield Python backend. The repo contains only a Next.js frontend (`app/`). All patterns are sourced from RESEARCH.md verified references.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/pyproject.toml` | config | — | No Python project configuration exists |
| `backend/.env.example` | config | — | No environment config files exist |
| `backend/app/__init__.py` | config | — | No Python packages exist |
| `backend/app/main.py` | entrypoint | request-response | No Python servers exist |
| `backend/app/api/__init__.py` | config | — | No Python packages exist |
| `backend/app/api/health.py` | route | request-response | No Python API routes exist |
| `backend/app/engine/__init__.py` | config | — | No Python packages exist |
| `backend/app/engine/poker_math.py` | utility | transform | No Python computation modules exist |
| `backend/tests/__init__.py` | config | — | No Python tests exist |
| `backend/tests/test_poker_math.py` | test | transform | No Python tests exist |
| `backend/tests/test_litellm_providers.py` | test | request-response | No Python tests exist |

**Frontend contract note:** `app/_components/types.ts` defines the TypeScript interfaces (`GameState`, `Player`, `Card`, `ReasoningEntry`) that Phase 3+ backend JSON responses must match. Phase 1 does not produce game state, but the planner should reference this file when planning Phase 3 SSE output serialization.

---

## Unlisted File — Required Dependency

RESEARCH.md Pattern 3 shows `backend/app/config.py` is required by `main.py` but is absent from CONTEXT.md's explicit file list. The planner should include it as an additional file in Phase 1's plan:

| Unlisted File | Role | Data Flow | Pattern Source |
|---------------|------|-----------|----------------|
| `backend/app/config.py` | config | — | RESEARCH.md Pattern 3, pydantic-settings load pattern |

---

## Metadata

**Analog search scope:** `app/` (Next.js frontend), repo root
**Files scanned:** 14 frontend files, 1 package.json, 1 CLAUDE.md
**Python files found:** 0
**Pattern sources:** RESEARCH.md (6 verified patterns + 7 pitfalls + code examples)
**Pattern extraction date:** 2026-05-02
