@AGENTS.md

# LLM Poker Arena — Project Guide

## Stack
- **Frontend**: Next.js 15 (App Router) — UI only, already built. Do not rebuild UI components.
- **Backend**: Python (FastAPI) — game engine, SSE broadcast, LLM orchestration
- **LLM**: LiteLLM — unified interface for all providers; models are config-driven, not hardcoded
- **Real-time**: Server-Sent Events (SSE) from FastAPI directly to browser
- **Deployment**: VPS only — Vercel/serverless is incompatible with persistent SSE

## Architecture
FastAPI game engine → Redis Pub/Sub → SSE endpoint → Next.js frontend (UI only)

Game state lives in FastAPI. Next.js only renders what SSE pushes.

## Key Rules
- **Never run a game without a viewer** — demand-triggered loop is a hard budget constraint
- **Math in code, not LLMs** — hand strength, pot odds, win probability are computed programmatically and fed to the LLM as structured context
- **Models are config-driven** — player roster defined in env vars / config, not hardcoded; any OpenAI-compatible model works
- **No side pots in v1** — single main pot only; side pots are deferred to v2
- **Read `node_modules/next/dist/docs/`** before writing any Next.js code — this version has breaking changes

## GSD Workflow
Planning docs: `.planning/`
- `PROJECT.md` — project context and decisions
- `REQUIREMENTS.md` — 23 v1 requirements with REQ-IDs
- `ROADMAP.md` — 6 phases
- `research/` — stack, features, architecture, pitfalls, summary

Next step: `/gsd-plan-phase 1`
