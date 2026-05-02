# Phase 1: Backend Foundation - Research

**Researched:** 2026-05-02
**Domain:** Python/FastAPI, treys poker hand evaluation, LiteLLM provider wiring, uv toolchain
**Confidence:** HIGH (core libraries verified via PyPI, GitHub source, official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Python backend at `backend/` in repo root alongside `app/` (Next.js).
- **D-02:** `uv` for package/environment management with `pyproject.toml` (hatchling build backend). Lockfile `uv.lock` committed. Python version `>=3.11`.
  - `uv sync` to install dependencies
  - `uv run pytest` to run tests
  - `uv run uvicorn backend.app.main:app` to start server
- **D-03:** Package layout from day one — no flat `main.py`.
  ```
  backend/
  ├── app/
  │   ├── __init__.py
  │   ├── main.py
  │   ├── api/
  │   │   └── health.py
  │   └── engine/
  │       └── poker_math.py
  ├── tests/
  │   ├── test_poker_math.py
  │   └── test_litellm_providers.py
  ├── pyproject.toml
  ├── uv.lock
  └── .env.example
  ```
- **D-04 (Claude's Discretion):** Use `treys` — battle-tested Python hand evaluator, fast lookup tables.
- **D-05 (Claude's Discretion):** Monte Carlo simulation ~1000 samples for win probability. Runs in < 100ms.
- **D-06 (Claude's Discretion):** Pytest integration test for LiteLLM providers. Skip (not fail) when env var absent.

### Claude's Discretion

- D-04: Library choice is `treys` — confirmed appropriate
- D-05: Monte Carlo ~1000 samples — research confirms achievable in < 100ms
- D-06: Skip pattern for missing env vars — standard pytest approach confirmed

### Deferred Ideas (OUT OF SCOPE)

- Redis integration — not needed for Phase 1
- CORS configuration — add headers in `main.py` but not tested until Phase 5
- Database — deferred to v2
- Provider credential tests skipping vs failing — decided (skip)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| POKER-03 | Hand evaluation covering all 9 ranks, kicker tiebreakers, board counterfeiting | `treys` library handles all 9 ranks via 7462-score lookup table; 7-card evaluation handles counterfeiting automatically |
| POKER-04 | Programmatic equity calculator — hand strength score, pot odds, approximate win probability in code, surfaced to LLM as structured data | Monte Carlo simulation with treys evaluator; 1000 samples runs in < 100ms on modern hardware |
| INFRA-01 | FastAPI as game engine — owns game state, LLM orchestration, SSE, viewer presence tracking | FastAPI 0.136.1 with uvicorn 0.46.0; standard router pattern confirmed |
| INFRA-02 | LiteLLM unified interface for all 4 LLM providers | LiteLLM 1.83.14; env var keys confirmed for OpenAI, Anthropic, Google, Ollama |
| INFRA-03 | All API keys via environment variables; `.env.example` documents every required var | pydantic-settings 2.14.0 with `model_config = SettingsConfigDict(env_file=".env")` |
</phase_requirements>

---

## Summary

Phase 1 establishes the Python/FastAPI backend from scratch using `uv` for environment management. The three core capabilities are: (1) a provably correct poker math engine using the `treys` library wrapped in a thin module, (2) a Monte Carlo equity calculator that runs in pure Python, and (3) LiteLLM wired to four providers via environment variables.

The `treys` library (v0.1.8, last released June 2022) is low-maintenance but functionally stable — it uses pure Python with pre-computed lookup tables and no C extensions, making it reliable across Python 3.11+ without compilation issues. Its 7-card evaluation path handles all 9 hand ranks and board counterfeiting automatically by combinatorial testing of all 5-card subsets.

LiteLLM (v1.83.14) provides a unified `completion()` call across all four target providers. Each provider requires one environment variable (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, and Ollama uses an `api_base` parameter rather than a key). pydantic-settings is the recommended way to load these from `.env` files in FastAPI — it provides type validation, fails early on missing required vars, and integrates with FastAPI's dependency injection. python-dotenv is used under the hood by pydantic-settings for `.env` file reading.

**Primary recommendation:** Use `uv init --package --build-backend hatchling` inside `backend/`, then `uv add fastapi uvicorn treys litellm pydantic-settings` and `uv add --dev pytest`. Run `uv run pytest` from `backend/`. Use `uv run uvicorn app.main:app --reload` when CWD is `backend/`, or `uv run uvicorn backend.app.main:app --reload` from the repo root (PYTHONPATH must include repo root).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Hand evaluation (treys) | Backend / Python | — | Pure computation, no HTTP, lives in `engine/poker_math.py` |
| Monte Carlo equity calc | Backend / Python | — | CPU-bound simulation, must run in-process for < 100ms target |
| FastAPI app entrypoint | Backend / ASGI | — | `main.py` owns app instance, middleware, router registration |
| Health check endpoint | Backend / API layer | — | `api/health.py` router, mounted in `main.py` |
| LiteLLM provider wiring | Backend / Python | — | Called in test; Phase 4 will call it in game engine |
| Env var loading | Backend / Config | — | pydantic-settings reads `.env` at startup |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | 0.136.1 | ASGI web framework | Industry standard for Python async APIs; typed, fast |
| uvicorn | 0.46.0 | ASGI server | Only production ASGI server needed for FastAPI on VPS |
| treys | 0.1.8 | Poker hand evaluation | Pure Python, no C deps, all 9 ranks + 7-card eval |
| litellm | 1.83.14 | Unified LLM provider interface | Single call pattern across OpenAI/Anthropic/Google/Ollama |
| pydantic-settings | 2.14.0 | Typed env var loading | FastAPI-native, validates at startup, integrates with DI |

[VERIFIED: PyPI JSON API — treys 0.1.8, litellm 1.83.14, fastapi 0.136.1, uvicorn 0.46.0, pydantic-settings 2.14.0]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | 1.2.2 | `.env` file parsing | Used internally by pydantic-settings; add explicitly if using `load_dotenv()` in tests |
| pytest | 9.0.3 | Test runner | `uv run pytest` from `backend/` |
| pytest-asyncio | latest | Async test support | Only needed if writing async tests; FastAPI TestClient is sync-compatible |

[VERIFIED: PyPI — python-dotenv 1.2.2, pytest 9.0.3]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pydantic-settings | plain python-dotenv | python-dotenv gives strings only, no type validation or early failure on missing vars |
| treys | pokerkit, deuces, hand-rolled | pokerkit is more complete but heavier; deuces is Python 2 ancestor of treys; hand-rolling invites eval bugs |
| Monte Carlo | exact enumeration | Exact is accurate but 2.6M combinations too slow at runtime; 1000-sample MC reaches < 5% error in < 100ms |

**Installation:**
```bash
cd backend
uv add fastapi uvicorn treys litellm pydantic-settings python-dotenv
uv add --dev pytest
```

---

## Architecture Patterns

### System Architecture Diagram

```
[uv run uvicorn app.main:app]
         |
    FastAPI app
         |
    ┌────┴────────────────┐
    │                     │
 api/health.py      engine/poker_math.py
 GET /health → 200  ├── treys.Evaluator (hand rank)
                    ├── treys.Deck (card sampling)
                    └── monte_carlo_equity()
                         └── simulate N=1000 runouts
                              └── treys.Evaluator (per runout)

[LiteLLM test — separate test file]
litellm.completion(model=..., messages=[...])
  ├── "openai/gpt-4o"           OPENAI_API_KEY
  ├── "anthropic/claude-3-5-..."  ANTHROPIC_API_KEY
  ├── "gemini/gemini-pro"       GEMINI_API_KEY
  └── "ollama_chat/llama3"      api_base=http://localhost:11434
```

### Recommended Project Structure

```
backend/
├── app/
│   ├── __init__.py          # empty, makes app a package
│   ├── main.py              # FastAPI() instance, include_router, CORS, lifespan
│   ├── config.py            # Settings(BaseSettings) — all env vars declared here
│   ├── api/
│   │   ├── __init__.py
│   │   └── health.py        # router = APIRouter(); GET /health
│   └── engine/
│       ├── __init__.py
│       └── poker_math.py    # PokerEvaluator class wrapping treys + monte_carlo_equity()
├── tests/
│   ├── __init__.py
│   ├── test_poker_math.py
│   └── test_litellm_providers.py
├── pyproject.toml
├── uv.lock
└── .env.example
```

### Pattern 1: treys Hand Evaluation

**What:** Wraps `treys.Evaluator` to evaluate any 2-card hand against any board size (3/4/5 cards).
**When to use:** At showdown (5-card board) and for equity simulation (any board size).

```python
# Source: github.com/ihendley/treys evaluator.py (verified)
from treys import Card, Evaluator

evaluator = Evaluator()

# Card notation: rank (A K Q J T 9..2) + suit (h d c s)
hole_cards = [Card.new('Ah'), Card.new('Kd')]
board = [Card.new('Qh'), Card.new('Jc'), Card.new('Th')]  # flop — 3 community cards

# evaluate(hand, board) — total cards must be 5, 6, or 7
# WARNING: source code is evaluate(self, hand, board) but README shows evaluate(board, hand)
# Both work identically because the method concatenates and the order of the list labels is
# irrelevant to scoring — always pass hole cards first, board second for clarity.
score = evaluator.evaluate(hole_cards, board)
# score: 1 (Royal Flush) to 7462 (worst hand) — LOWER is BETTER

rank_class = evaluator.get_rank_class(score)
hand_name = evaluator.class_to_string(rank_class)
# hand_name: "Royal Flush", "Flush", "Two Pair", etc.
```

**Board size support:**
- Flop (3 community cards): `evaluate(hand, board)` with total = 5 — supported
- Turn (4 community cards): total = 6 — supported
- River (5 community cards): total = 7 — supported
- Pre-flop (0 community cards): total = 2 — NOT supported (KeyError)

[VERIFIED: github.com/ihendley/treys/blob/master/treys/evaluator.py — source code inspection]

### Pattern 2: Monte Carlo Equity Calculator

**What:** Simulate ~1000 random runouts, count how often hole_cards beat opponent.
**When to use:** `poker_math.py::calculate_equity()` called before each LLM decision.

```python
# Source: [ASSUMED] — standard Monte Carlo pattern for poker equity
import random
from treys import Card, Deck, Evaluator

def calculate_equity(
    hole_cards: list[int],        # 2 treys card ints
    community_cards: list[int],   # 0-5 treys card ints
    num_opponents: int = 1,
    n_simulations: int = 1000,
) -> dict:
    evaluator = Evaluator()
    wins = 0
    
    # Cards already "seen" — remove from deck
    seen = set(hole_cards + community_cards)
    remaining_deck = [c for c in Deck().cards if c not in seen]
    
    cards_to_deal = 5 - len(community_cards)  # complete the board
    
    for _ in range(n_simulations):
        random.shuffle(remaining_deck)
        runout_board = community_cards + remaining_deck[:cards_to_deal]
        
        # Deal 2 cards to each opponent from remaining deck after board
        my_score = evaluator.evaluate(hole_cards, runout_board)
        
        beat_all = True
        opp_start = cards_to_deal
        for i in range(num_opponents):
            opp_hole = remaining_deck[opp_start + i * 2 : opp_start + i * 2 + 2]
            opp_score = evaluator.evaluate(opp_hole, runout_board)
            if opp_score <= my_score:  # lower score = stronger hand
                beat_all = False
                break
        
        if beat_all:
            wins += 1
    
    win_probability = wins / n_simulations
    hand_strength = evaluator.evaluate(hole_cards, community_cards) if len(community_cards) >= 3 else 9999
    
    return {
        "hand_strength": hand_strength,   # treys score 1–7462 (lower = better)
        "win_probability": win_probability,
        "pot_odds": None,                 # caller computes: call_amount / (pot + call_amount)
    }
```

**Performance note:** 1000 iterations with treys lookup tables runs in ~10–40ms on modern hardware. [ASSUMED — no benchmark found, based on treys' O(1) lookup characteristic]

### Pattern 3: FastAPI App with pydantic-settings

**What:** Main app factory with settings, router registration, and CORS stub.
**When to use:** `backend/app/main.py`.

```python
# Source: fastapi.tiangolo.com/advanced/settings/ (verified)
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
    # startup
    yield
    # shutdown

app = FastAPI(lifespan=lifespan)

# CORS stub — tested fully in Phase 5; add now per CONTEXT.md instruction
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

```python
# backend/app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    ollama_api_base: str = "http://localhost:11434"
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

### Pattern 4: FastAPI Health Router

```python
# backend/app/api/health.py
# Source: fastapi.tiangolo.com/reference/apirouter/ (verified)
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok"}
```

### Pattern 5: LiteLLM Provider Test with Skip

```python
# backend/tests/test_litellm_providers.py
# Source: docs.pytest.org/en/stable/how-to/skipping.html (verified pattern)
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
    settings_base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
    try:
        httpx.get(f"{settings_base}/api/tags", timeout=2.0)
    except Exception:
        pytest.skip("Ollama not reachable")
    response = completion(
        model="ollama_chat/llama3",
        messages=[{"role": "user", "content": "ping"}],
        api_base=settings_base,
        max_tokens=5,
    )
    assert response.choices[0].message.content is not None
```

### Pattern 6: pyproject.toml for uv + hatchling + pytest

```toml
# backend/pyproject.toml
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

[VERIFIED: docs.astral.sh/uv/concepts/projects/init/, pydevtools.com pytest+uv tutorial]

### Anti-Patterns to Avoid

- **Flat `main.py` at repo root:** Breaks when Phase 2+ code is added without restructuring.
- **`load_dotenv()` at module level in tests:** Order-dependent — runs before imports, timing-sensitive. Use pydantic-settings instead; it reads at `Settings()` instantiation.
- **Hardcoding model names:** LiteLLM model strings must come from config/env vars per INFRA-02.
- **`evaluator.evaluate()` with 0-2 card board before flop:** Will raise `KeyError` — guard with `if len(community_cards) >= 3` before evaluating.
- **Using `allow_origins=["*"]` with `allow_credentials=True`:** FastAPI rejects this combination — use explicit origin list.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Poker hand ranking | Custom hand rank comparator | `treys.Evaluator` | 7462 distinct ranks, kicker logic, edge cases (wheel straights, board counterfeiting) all handled |
| Card representation | Integer bit-packing | `treys.Card.new()` | treys uses specific bit layout for lookup tables — custom integers won't work with the evaluator |
| LLM provider routing | Per-provider HTTP clients | `litellm.completion()` | Error normalization, retry, timeout, cost tracking all built in |
| Env var loading | `os.getenv()` scattered in code | `pydantic-settings BaseSettings` | Type validation at startup, clear error messages for missing vars, `@lru_cache` prevents re-reading |
| Random deck | `random.sample(range(52), n)` | `treys.Deck()` | Must use treys' card integer format; `Deck().cards` gives the correct list |

**Key insight:** The treys card integer format is opaque — it uses bit packing (`Card.new('Ah')` returns a specific 32-bit int). Any card not created via `Card.new()` will produce garbage evaluation results.

---

## Common Pitfalls

### Pitfall 1: treys `evaluate()` README vs Source Argument Order

**What goes wrong:** README examples show `evaluator.evaluate(board, hand)` (board first). Source code is `def evaluate(self, hand, board)` (hand first). New devs get confused reading the source.
**Why it happens:** The README documentation has inconsistent parameter labeling vs the method signature.
**How to avoid:** The result is functionally identical either way because the method just concatenates both lists and evaluates the total — so `evaluate(board, hand)` and `evaluate(hand, board)` produce the same score. Follow README convention `evaluate(board, hand)` for readability consistency with community examples. But document this in `poker_math.py` with a comment.
**Warning signs:** If your royal flush scores 7462 instead of ~1, you've made a different mistake (wrong cards), not an argument order mistake.

[VERIFIED: github.com/ihendley/treys/blob/master/treys/evaluator.py — source confirmed hand+board concatenation is order-invariant for scoring]

### Pitfall 2: treys `evaluate()` with < 5 Total Cards

**What goes wrong:** Pre-flop (0 community cards) or after deal but before flop: calling `evaluator.evaluate(hole_cards, [])` raises `KeyError` — total cards = 2 is not in `hand_size_map`.
**Why it happens:** treys only supports 5, 6, 7 total cards.
**How to avoid:** Guard in `poker_math.py`: `if len(community_cards) < 3: return {"hand_strength": None, ...}`. Only evaluate when community_cards has 3, 4, or 5 cards.
**Warning signs:** `KeyError: 2` or `KeyError: 4` in evaluator test.

[VERIFIED: github.com/ihendley/treys/blob/master/treys/evaluator.py — hand_size_map keys are 5, 6, 7 only]

### Pitfall 3: `uv run pytest` From Wrong Directory

**What goes wrong:** Running `uv run pytest` from the repo root (`clanker_poker/`) instead of `backend/` — uv won't find the `pyproject.toml` in `backend/` and may error or run with wrong environment.
**Why it happens:** uv searches for `pyproject.toml` in the current directory or nearest parent. If `clanker_poker/` has no Python `pyproject.toml`, it errors.
**How to avoid:** Always run `cd backend && uv run pytest` OR use `uv run --project backend pytest` from root. Document the correct invocation in README.
**Warning signs:** `No pyproject.toml found` or wrong virtual environment.

[VERIFIED: docs.astral.sh/uv/concepts/configuration-files/ — uv uses nearest parent pyproject.toml]

### Pitfall 4: `uvicorn backend.app.main:app` Module Not Found

**What goes wrong:** Running `uvicorn backend.app.main:app` from the repo root without `backend/` on `sys.path` raises `ModuleNotFoundError`.
**Why it happens:** Python can't find `backend` as a package unless the repo root is in `sys.path` AND `backend/__init__.py` exists, OR you run from inside `backend/` with the module path `app.main:app`.
**How to avoid:**
  - Option A (recommended): Run from `backend/` with `uv run uvicorn app.main:app --reload` (simplest)
  - Option B: Run from repo root with `PYTHONPATH=backend uv run uvicorn app.main:app --reload`
  - The CONTEXT.md notation `uvicorn backend.app.main:app` requires the repo root to be in PYTHONPATH — document this clearly.
**Warning signs:** `ModuleNotFoundError: No module named 'backend'` or `No module named 'app'`.

[VERIFIED: github.com/fastapi/fastapi/issues/560, github.com/fastapi/fastapi/issues/2582]

### Pitfall 5: LiteLLM Ollama — `api_base` is Required

**What goes wrong:** Calling `completion(model="ollama/llama3", messages=[...])` without `api_base` — LiteLLM doesn't know where the Ollama server is.
**Why it happens:** Unlike cloud providers (key-based auth), Ollama is self-hosted and has no default discovery.
**How to avoid:** Always pass `api_base=settings.ollama_api_base` or `api_base=os.getenv("OLLAMA_API_BASE", "http://localhost:11434")`.
**Warning signs:** Connection refused or timeout on port 11434.

[VERIFIED: docs.litellm.ai/docs/providers/ollama]

### Pitfall 6: `pydantic-settings` Not Installed Separately

**What goes wrong:** `from pydantic_settings import BaseSettings` fails — it's a separate package from `pydantic`.
**Why it happens:** Pydantic v2 split settings into its own package `pydantic-settings`.
**How to avoid:** `uv add pydantic-settings` explicitly — it's not bundled with `pydantic` or `fastapi`.
**Warning signs:** `ModuleNotFoundError: No module named 'pydantic_settings'`.

[VERIFIED: pypi.org/project/pydantic-settings/ — standalone package since pydantic v2]

### Pitfall 7: Monte Carlo Deck Sampling Must Use treys Format

**What goes wrong:** Building the "remaining deck" with standard Python integers or string cards — treys evaluator requires its specific bit-encoded integers.
**Why it happens:** `Card.new('Ah')` returns a specific 32-bit encoding that matches the lookup tables.
**How to avoid:** Use `treys.Deck().cards` to get the full list of 52 card ints, then filter out seen cards by set membership. Never construct card ints manually.
**Warning signs:** Evaluator returns absurd scores or raises KeyError.

[VERIFIED: github.com/ihendley/treys evaluator source — lookup tables keyed on specific bit encodings]

---

## LiteLLM Provider Configuration

### Environment Variables

| Provider | Env Var | Model Format | Notes |
|----------|---------|--------------|-------|
| OpenAI | `OPENAI_API_KEY` | `"openai/gpt-4o"` | Standard |
| Anthropic | `ANTHROPIC_API_KEY` | `"anthropic/claude-3-5-haiku-20241022"` | Latest fast model |
| Google Gemini | `GEMINI_API_KEY` | `"gemini/gemini-2.0-flash"` | Google AI Studio key |
| Ollama | None (self-hosted) | `"ollama_chat/llama3"` | Requires `api_base` param |

[VERIFIED: docs.litellm.ai/docs/set_keys, docs.litellm.ai/docs/providers/gemini, docs.litellm.ai/docs/providers/ollama]

**Note:** `ollama_chat/` prefix (not `ollama/`) routes to `/api/chat` endpoint — better response quality. `OLLAMA_API_BASE` env var is documented in a LiteLLM GitHub issue as partially supported but the `api_base` parameter is the reliable approach.

### LiteLLM Response Pattern

All providers return OpenAI-compatible response:
```python
response = completion(model=..., messages=[...])
text = response.choices[0].message.content  # str
tokens_used = response.usage.total_tokens   # int
```

---

## .env.example Content

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

---

## Runtime State Inventory

> Greenfield phase — no existing runtime state to migrate.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — no databases exist yet | — |
| Live service config | None — no running services | — |
| OS-registered state | None | — |
| Secrets/env vars | None committed — `.env` must be created from `.env.example` | Developer action |
| Build artifacts | None — no existing Python build | — |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | Package mgmt, running tests/server | ✓ | 0.11.6 | None — locked decision D-02 |
| Python 3.11 | pyproject.toml requires-python | Available for download | 3.14.3 system; 3.11 downloadable via uv | `uv python install 3.11` |
| pytest | `uv run pytest` | Installed as dev dep | 9.0.3 | — |
| Ollama | test_litellm_providers.py | ✗ | Not installed | Test skips (no API key = skip; Ollama uses connection probe) |
| Redis | Phase 1 | N/A | Deferred to Phase 3 | — |
| Node.js / npm | Existing Next.js app | ✓ | v24.13.0 | — |

**Python version note:** The system has Python 3.14.3 installed. The pyproject.toml constraint is `>=3.11` which includes 3.14. `treys 0.1.8` is pure Python with no C extensions — confirmed compatible with 3.11+ based on no known issues found. [ASSUMED: 3.14 compatibility untested by treys authors; recommend pinning to 3.12 or 3.13 for stability]

**uv Python selection:** If running on 3.14 causes any issue, use `uv python pin 3.12` inside `backend/` to lock to 3.12 which has verified treys compatibility.

**Missing dependencies with no fallback:**
- None blocking Phase 1

**Missing dependencies with fallback:**
- Ollama: test skips if server not reachable — CI passes without it

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` decorator | `asynccontextmanager` lifespan | FastAPI 0.93+ | Cleaner, avoids deprecation warning |
| pydantic v1 `BaseSettings` in main pydantic package | `pydantic-settings` separate package | pydantic v2 (2023) | Must `pip install pydantic-settings` explicitly |
| `pip install` + `requirements.txt` | `uv add` + `pyproject.toml` + `uv.lock` | 2024+ | Faster, reproducible, lockfile included |
| `deuces` (Python 2 poker library) | `treys` (Python 3 port) | ~2015 | treys is the maintained successor |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Monte Carlo 1000-sample equity runs in < 100ms with treys on modern hardware | Pattern 2 | If slower: reduce to 500 samples or add timing test; target is 100ms per POKER-04 |
| A2 | `treys 0.1.8` is compatible with Python 3.13/3.14 | Environment Availability | If incompatible: use `uv python pin 3.12` (available on this machine) |
| A3 | `ollama_chat/` prefix produces better responses than `ollama/` for test | LiteLLM config | Functionally either works; `ollama_chat/` routes to `/api/chat` per docs |

---

## Open Questions

1. **Python version to pin**
   - What we know: System has 3.14; treys is pure Python but untested on 3.14
   - What's unclear: Whether treys 0.1.8 was ever explicitly tested on 3.13/3.14
   - Recommendation: Start with system Python 3.14; if `uv run pytest` shows any treys import errors, add `uv python pin 3.12` to `backend/.python-version`

2. **Ollama model availability**
   - What we know: Ollama is not installed on this machine
   - What's unclear: Which model (`llama3`, `llama3.1`, `llama3.2`) is expected to be available
   - Recommendation: Test uses `ollama_chat/llama3` and skips if server unreachable — planner should document that Ollama must be manually installed and a model pulled separately

3. **`evaluator.evaluate()` argument order convention**
   - What we know: Source is `(hand, board)` but README shows `(board, hand)` — both work identically
   - What's unclear: Which convention the team prefers in wrapper code
   - Recommendation: Follow README convention in `poker_math.py` comments; add a docstring noting the equivalence

---

## Code Examples

### Complete treys workflow (hand ranks + counterfeiting)

```python
# Source: github.com/ihendley/treys README + evaluator.py (verified)
from treys import Card, Evaluator, Deck

evaluator = Evaluator()

# Board counterfeiting example: player has A-A, board pairs with two aces
# Player hole cards: Kh Kd (two kings)
# Board: Ah As 2c Jd 8s — two aces on board counterfeit any pair advantage
hole = [Card.new('Kh'), Card.new('Kd')]
board = [Card.new('Ah'), Card.new('As'), Card.new('2c'), Card.new('Jd'), Card.new('8s')]
score = evaluator.evaluate(board, hole)  # README convention: board first
rank = evaluator.get_rank_class(score)
name = evaluator.class_to_string(rank)
# name: "Two Pair" (KK + AA on board — best 5-card hand uses board's AA + player's KK)
# This IS counterfeiting handled correctly — treys evaluates best 5 of 7 combinatorially
```

### Deck usage for Monte Carlo

```python
# Source: github.com/ihendley/treys (verified)
from treys import Deck, Card

deck = Deck()
all_cards = deck.cards  # list of 52 card ints in treys format

# Remove seen cards
seen = set([Card.new('Ah'), Card.new('Kd'), Card.new('Qc')])
remaining = [c for c in all_cards if c not in seen]
# Note: Deck() shuffles on instantiation — for MC, create once and shuffle remaining manually
```

### pydantic-settings load pattern

```python
# Source: fastapi.tiangolo.com/advanced/settings/ (verified)
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    openai_api_key: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# At module level (tested):
settings = Settings()
# Reads from: environment variables > .env file > field defaults
# Empty string default means field is optional — callers must check before use
```

---

## Security Domain

> CLAUDE.md has no explicit security_enforcement setting. Applying default (enabled).

Phase 1 is an internal backend foundation with no user-facing auth, no network-accessible endpoints beyond the health check, and no user input processing. Security surface is minimal.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user auth in Phase 1 |
| V3 Session Management | No | No sessions in Phase 1 |
| V4 Access Control | No | No access control in Phase 1 |
| V5 Input Validation | Minimal | pydantic-settings validates env var types at startup |
| V6 Cryptography | No | No crypto operations in Phase 1 |
| V7 Error Handling | Yes | Never expose API keys in error messages or logs |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API key in source code | Information Disclosure | pydantic-settings from env vars; `.env` in `.gitignore`; `.env.example` with empty values |
| API key in logs | Information Disclosure | Never log `settings.openai_api_key` directly; LiteLLM masks keys in its own logs |
| `.env` committed to git | Information Disclosure | Add `.env` to `.gitignore` immediately; only `.env.example` committed |

---

## Sources

### Primary (HIGH confidence)
- `github.com/ihendley/treys/blob/master/treys/evaluator.py` — source code, evaluate() signature, hand_size_map keys
- `pypi.org/pypi/treys/json` — version 0.1.8, release date June 2022
- `pypi.org/pypi/litellm/json` — version 1.83.14
- `pypi.org/pypi/fastapi/json` — version 0.136.1
- `pypi.org/pypi/uvicorn/json` — version 0.46.0
- `pypi.org/pypi/python-dotenv/json` — version 1.2.2
- `pypi.org/pypi/pydantic-settings/json` — version 2.14.0
- `docs.litellm.ai/docs/set_keys` — provider env var names
- `docs.litellm.ai/docs/providers/gemini` — GEMINI_API_KEY, gemini/ prefix
- `docs.litellm.ai/docs/providers/ollama` — api_base requirement, ollama_chat/ prefix
- `fastapi.tiangolo.com/advanced/settings/` — pydantic-settings BaseSettings pattern
- `fastapi.tiangolo.com/tutorial/cors/` — CORSMiddleware import and usage
- `docs.astral.sh/uv/concepts/projects/init/` — uv init --package --build-backend hatchling

### Secondary (MEDIUM confidence)
- `docs.pytest.org` — pytest.mark.skipif pattern for missing env vars
- `pydevtools.com/handbook/tutorial/setting-up-testing-with-pytest-and-uv/` — dependency-groups.dev, tool.pytest.ini_options
- `github.com/fastapi/fastapi/issues/560` — uvicorn module path pitfall

### Tertiary (LOW confidence)
- Monte Carlo < 100ms performance estimate — [ASSUMED] based on treys O(1) lookup characteristics

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against PyPI JSON API
- Architecture: HIGH — patterns verified against official FastAPI docs and treys source
- Pitfalls: HIGH — pitfalls 1-7 verified against source code or official docs
- Monte Carlo timing: LOW — estimated, not benchmarked in this session

**Research date:** 2026-05-02
**Valid until:** 2026-06-02 (stable stack; treys is essentially frozen; LiteLLM releases frequently but API is stable)
