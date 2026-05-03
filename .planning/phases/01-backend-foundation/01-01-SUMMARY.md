---
phase: 01-backend-foundation
plan: "01"
subsystem: backend-scaffold
tags: [fastapi, uvicorn, pydantic-settings, uv, python, cors, health-check]
dependency_graph:
  requires: []
  provides: [backend-package-structure, fastapi-app, health-endpoint, settings-class]
  affects: [01-02, 01-03]
tech_stack:
  added: [fastapi==0.136.1, uvicorn==0.46.0, treys==0.1.8, litellm==1.83.14, pydantic-settings==2.14.0, python-dotenv==1.2.2, pytest==9.0.3, httpx==0.28.1]
  patterns: [asynccontextmanager-lifespan, pydantic-settings-lru-cache, cors-explicit-origins, uv-hatchling-pyproject]
key_files:
  created:
    - backend/pyproject.toml
    - backend/uv.lock
    - backend/app/__init__.py
    - backend/app/config.py
    - backend/app/main.py
    - backend/app/api/__init__.py
    - backend/app/api/health.py
    - backend/app/engine/__init__.py
    - backend/tests/__init__.py
  modified:
    - .gitignore
decisions:
  - "Used Python 3.13.13 (system default via uv) — treys 0.1.8 is pure Python, installed and imported cleanly on 3.13, so uv python pin 3.12 was not needed"
  - "config.py is provider-agnostic: player_models list[str] holds LiteLLM model strings; no per-provider API key fields; LiteLLM reads keys from os.environ directly"
metrics:
  duration: "2m 16s"
  completed: "2026-05-03"
  tasks_completed: 2
  files_created: 9
  files_modified: 1
---

# Phase 1 Plan 01: FastAPI Scaffold Summary

FastAPI backend scaffold at `backend/` with uv/hatchling project config, provider-agnostic pydantic-settings, CORSMiddleware, and GET /health endpoint — runnable via `uv run uvicorn app.main:app`.

## What Was Built

### Directory Structure

```
backend/
├── app/
│   ├── __init__.py          # package marker
│   ├── config.py            # Settings(BaseSettings) — player_models, cors_origins, llm_timeout_seconds
│   ├── main.py              # FastAPI app, asynccontextmanager lifespan, CORSMiddleware, health router
│   ├── api/
│   │   ├── __init__.py      # package marker
│   │   └── health.py        # GET /health → {"status": "ok"}
│   └── engine/
│       └── __init__.py      # package marker (poker_math.py added in Plan 02)
├── tests/
│   └── __init__.py          # package marker (tests added in Plan 02)
├── pyproject.toml           # uv + hatchling config, all 6 runtime deps + dev deps
└── uv.lock                  # committed lockfile (65 packages)
```

### How to Start the Server

From `backend/` directory:
```bash
cd backend
uv run uvicorn app.main:app --reload
```

From repo root:
```bash
uv run --project backend uvicorn app.main:app --reload
# OR
cd backend && uv run uvicorn app.main:app --reload
```

Server starts on `http://127.0.0.1:8000`. Health check: `curl http://localhost:8000/health` returns `{"status":"ok"}`.

### Python Version

No pin applied. `uv` selected Python 3.13.13 (system default). `treys 0.1.8` installed and imported cleanly — the conditional pin to 3.12 was not needed.

## Decisions Made

1. **Python 3.13.13 used without pinning** — treys is pure Python with no C extensions; it installed and imported correctly on 3.13. The contingency `uv python pin 3.12` was not needed.

2. **Provider-agnostic Settings** — `config.py` has no `openai_api_key`, `anthropic_api_key`, `gemini_api_key`, or `ollama_api_base` fields. `player_models: list[str]` holds LiteLLM model strings. LiteLLM reads provider keys from `os.environ` directly. Adding a new provider requires only updating `PLAYER_MODELS` in `.env`.

3. **`extra="ignore"` in SettingsConfigDict** — prevents startup errors from provider keys (e.g., `OPENAI_API_KEY`) that appear in the environment but are not declared in Settings. This is required for the provider-agnostic design.

## Deviations from Plan

None — plan executed exactly as written. The pyproject.toml, config.py, main.py, and health.py match the interface specs verbatim. The Python version conditional (pin 3.12 if treys fails on 3.14) was not triggered.

## Security Review (Threat Model Compliance)

| Threat | Disposition | Status |
|--------|-------------|--------|
| T-01-01: .env in git | mitigate | DONE — `backend/.env` added to `.gitignore` in Task 1 |
| T-01-02: provider keys in config.py | mitigate | DONE — Settings has no provider key fields; `extra="ignore"` prevents unknown vars from surfacing |
| T-01-03: request logging | accept | No request logging added; FastAPI default logs don't include request bodies |
| T-01-04: /health tampering | accept | Static response, no user input |
| T-01-05: uv.lock in git | accept | uv.lock committed (standard practice, no secrets) |

## Known Stubs

None — this plan creates infrastructure only. No UI rendering, no data flows, no placeholder values that reach user-visible output.

## Self-Check

- [x] `backend/pyproject.toml` exists with `requires-python = ">=3.11"`, `pythonpath = ["."]`, all 6 runtime deps
- [x] `backend/uv.lock` exists (65 packages, committed)
- [x] All `__init__.py` files exist
- [x] `backend/app/config.py` has `Settings(BaseSettings)` with `player_models`, `llm_timeout_seconds`, `cors_origins`; NO provider key fields
- [x] `backend/app/main.py` uses asynccontextmanager, CORSMiddleware with `_settings.cors_origins`, includes health router
- [x] `backend/app/api/health.py` returns `{"status": "ok"}`
- [x] `uv run python -c "from app.main import app"` exits 0
- [x] `GET /health` returns `{"status":"ok"}` HTTP 200
- [x] `.gitignore` contains `backend/.env`; does NOT contain `backend/.env.example`
- [x] Commits `a993ccc` and `63f5415` exist in git log

## Self-Check: PASSED
