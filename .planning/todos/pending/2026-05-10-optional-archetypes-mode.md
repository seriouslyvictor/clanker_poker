---
created: 2026-05-10T00:00:00Z
title: Optional archetypes mode for sessions
area: backend
files:
  - backend/app/game_loop.py:48
  - backend/app/config.py
  - backend/app/ai/archetypes.py
---

## Problem

Archetypes are always assigned at session start. There's no way to run a neutral game where all players use only raw LLM judgment without archetype bias — useful for A/B comparisons, debugging prompt behavior, or just preferring the "pure" LLM experience.

## Solution

Add `use_archetypes: bool = True` to `Settings` (env var `USE_ARCHETYPES`). In `game_loop.py`, conditionally call `assign_archetypes()`: if `settings.use_archetypes` is False, pass an empty dict as `archetypes` to `make_llm_decision_fn()`. The decision function already handles missing archetype keys — fallback uses a neutral archetype or skips persona injection in the prompt.
