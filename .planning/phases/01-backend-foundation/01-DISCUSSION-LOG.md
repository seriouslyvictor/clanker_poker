# Phase 1: Backend Foundation — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 01-backend-foundation
**Areas discussed:** Backend directory layout, Python toolchain, FastAPI app structure

---

## Backend Directory Layout

| Option | Description | Selected |
|--------|-------------|----------|
| `backend/` | At repo root alongside `app/`. Clear separation for mixed frontend/backend monorepo. | ✓ |
| `server/` | Common full-stack convention but less explicit about Python. | |
| `api/` | Short but ambiguous — conflicts with Next.js `app/api/` convention. | |

**User's choice:** `backend/`
**Notes:** None

---

## Python Toolchain

| Option | Description | Selected |
|--------|-------------|----------|
| `uv + pyproject.toml` | Fast installs, lockfile, PEP 517 packaging. Modern best practice. | ✓ |
| `requirements.txt + venv` | Universal, zero learning curve, works everywhere. | |
| `Poetry + pyproject.toml` | Mature lockfile, slower than uv. | |

**User's choice:** `uv + pyproject.toml` with hatchling build backend
**Notes:** None

---

## FastAPI App Structure

| Option | Description | Selected |
|--------|-------------|----------|
| Package layout from day one | `app/`, `api/`, `engine/`, `tests/` modules. Future phases fit in cleanly. | ✓ |
| Flat for Phase 1, restructure later | Single `main.py` now, reorganize later. Risks mid-project disruption. | |

**User's choice:** Package layout from day one
**Notes:** None

---

## Claude's Discretion

- **Hand evaluation library:** `treys` (specified in ROADMAP.md Phase 1 notes)
- **Equity calculator:** Monte Carlo ~1000 samples, pure Python, <100ms
- **Provider test approach:** pytest integration, skip (not fail) when env vars absent

## Deferred Ideas

- None raised during discussion
