---
phase: 01-backend-foundation
plan: "03"
subsystem: litellm-wiring
tags: [litellm, env-vars, pytest, provider-agnostic, dotenv]
dependency_graph:
  requires: [01-01]
  provides: [env-example, litellm-connectivity-test]
  affects: [01-02, phase-04]
tech_stack:
  added: []
  patterns: [pytest-skipif-no-env, litellm-completion-pattern, ollama-api-base-generic]
key_files:
  created:
    - backend/.env.example
    - backend/tests/test_litellm_providers.py
  modified:
    - .gitignore
decisions:
  - "Added !backend/.env.example negation to .gitignore — the existing .env* glob on line 34 was silently blocking .env.example from being committed; negation rule overrides glob for this specific file"
  - "Single test_litellm_connectivity function rather than per-provider functions — provider-agnostic: LITELLM_TEST_MODEL or first entry of PLAYER_MODELS drives which model is called"
metrics:
  duration: "~8m"
  completed: "2026-05-03"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
---

# Phase 1 Plan 03: LiteLLM Wiring Summary

Provider-agnostic `.env.example` with `PLAYER_MODELS` as the primary config entry, plus a single `test_litellm_connectivity` test that skips gracefully with no env vars and confirms live LiteLLM wiring when a model is configured.

## What Was Built

### backend/.env.example

Committed to git at `backend/.env.example`. Documents `PLAYER_MODELS` as the first and primary config point — a JSON array of LiteLLM model strings. Provider API keys are listed below as optional add-ons with empty values (no secrets). `OLLAMA_API_BASE` has a default value (`http://localhost:11434`) since it's a URL, not a secret.

```ini
PLAYER_MODELS=["openai/gpt-4o","anthropic/claude-3-5-haiku-20241022","gemini/gemini-2.0-flash","ollama_chat/llama3"]
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
OLLAMA_API_BASE=http://localhost:11434
CORS_ORIGINS=["http://localhost:3000"]
```

Developer workflow: `cp backend/.env.example backend/.env`, then fill in the keys for the providers in `PLAYER_MODELS`.

### backend/tests/test_litellm_providers.py

Single `test_litellm_connectivity` function. Provider-agnostic: reads `LITELLM_TEST_MODEL` first, falls back to first entry of `PLAYER_MODELS`. Skips when neither is set.

Ollama handling is generic: `if _TEST_MODEL.startswith("ollama"): kwargs["api_base"] = ...` — works for any ollama-prefixed model string without naming specific models.

## pytest Output

### test_litellm_providers.py only (no env vars set):

```
============================= test session starts =============================
platform win32 -- Python 3.13.13, pytest-9.0.3, pluggy-1.6.0
collected 1 item

tests/test_litellm_providers.py::test_litellm_connectivity SKIPPED (...) [100%]

============================= 1 skipped in 20.69s =============================
```

Exit code: 0. Confirms CI passes with no env vars configured.

### Full suite (uv run pytest):

```
============================= test session starts =============================
platform win32 -- Python 3.13.13, pytest-9.0.3, pluggy-1.6.0
collected 1 item

tests/test_litellm_providers.py::test_litellm_connectivity SKIPPED (...) [100%]

============================= 1 skipped in 3.51s ==============================
```

Exit code: 0. No regressions. (Note: test_poker_math.py is added in Plan 02 which runs in parallel in wave 2.)

## Running with a Real Model

To test live connectivity with a specific model:

```bash
# Option A: Set LITELLM_TEST_MODEL directly
export LITELLM_TEST_MODEL="openai/gpt-4o"
export OPENAI_API_KEY="sk-..."
cd backend && uv run pytest tests/test_litellm_providers.py -v

# Option B: Use PLAYER_MODELS (first entry is tested)
# Copy .env.example to .env, fill in OPENAI_API_KEY (or whichever provider's key)
cp backend/.env.example backend/.env
# Edit backend/.env — set OPENAI_API_KEY=sk-... (or ANTHROPIC_API_KEY, GEMINI_API_KEY, etc.)
cd backend && uv run pytest tests/test_litellm_providers.py -v

# Any LiteLLM-supported provider works — just set the correct env var for the prefix
# See: https://docs.litellm.ai/docs/providers
```

For Ollama (local, no API key):
```bash
# Start Ollama first: ollama serve
# Then pull a model: ollama pull llama3
export LITELLM_TEST_MODEL="ollama_chat/llama3"
# OLLAMA_API_BASE defaults to http://localhost:11434 if not set
cd backend && uv run pytest tests/test_litellm_providers.py -v
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Added !backend/.env.example negation to .gitignore**
- **Found during:** Task 1
- **Issue:** The `.gitignore` contained `.env*` (line 34) which matched `backend/.env.example`. Without a negation, `.env.example` would be silently gitignored and impossible to commit — the plan's must-have "`.env.example` is committed to git" would have been violated.
- **Fix:** Added `!backend/.env.example` in the Python backend section of `.gitignore`, immediately after `backend/.env`. The negation overrides the `.env*` glob specifically for the example file.
- **Files modified:** `.gitignore`
- **Commit:** 220431a

## Security Review (Threat Model Compliance)

| Threat | Disposition | Status |
|--------|-------------|--------|
| T-03-01: backend/.env in git | mitigate | VERIFIED — `backend/.env` is gitignored; `git status backend/.env` shows nothing |
| T-03-02: API keys in test output | mitigate | DONE — test only asserts `response.choices[0].message.content is not None`; no key logging |
| T-03-03: LiteLLM test consuming API budget | accept | DONE — `max_tokens=5` cap; test only runs when dev sets LITELLM_TEST_MODEL or PLAYER_MODELS |
| T-03-04: Ollama endpoint not authenticated | accept | Accepted — localhost only in Phase 1 |

## Known Stubs

None — this plan creates infrastructure and a skipping test. No UI rendering, no data flows, no placeholder values.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundary crossings introduced.

## Self-Check

- [x] `backend/.env.example` exists and contains `PLAYER_MODELS=` as first config entry
- [x] `backend/.env.example` contains `OPENAI_API_KEY=`, `ANTHROPIC_API_KEY=`, `GEMINI_API_KEY=`, `OLLAMA_API_BASE=http://localhost:11434`, `CORS_ORIGINS=`
- [x] All provider key values in .env.example are empty (no real secrets)
- [x] `backend/.env` is gitignored — `git status backend/.env` returns nothing
- [x] `backend/.env.example` is NOT gitignored — `!backend/.env.example` negation added
- [x] `backend/tests/test_litellm_providers.py` exists with exactly 1 test function: `test_litellm_connectivity`
- [x] File contains `_get_test_model()`, `LITELLM_TEST_MODEL`, `PLAYER_MODELS`, `pytest.mark.skipif`, `startswith("ollama")`, `api_base`
- [x] File does NOT contain `test_openai_provider`, `test_anthropic_provider`, `test_gemini_provider`, `test_ollama_provider`
- [x] `uv run pytest tests/test_litellm_providers.py -v` exits 0 with 1 skip — confirmed
- [x] `uv run pytest` full suite exits 0 — confirmed
- [x] Commits 220431a and f29f32d exist in git log

## Self-Check: PASSED
