---
created: 2026-05-10T00:00:00Z
title: Configurable number of hands per session
area: backend
files:
  - backend/app/game_loop.py:71
  - backend/app/config.py
---

## Problem

`n_hands` is hardcoded to 10 in `game_loop.py` (`await session.run(n_hands=10, ...)`). There's no way to configure session length without editing code. Useful for dev (shorter sessions), demos (longer), and future viewer-triggered sessions with a chosen length.

## Solution

Add `n_hands_per_session: int = 10` to `Settings` in `config.py` (env var `N_HANDS_PER_SESSION`). Pass `settings.n_hands_per_session` to `session.run()` in `game_loop.py`. No other changes needed — `GameSession.run()` already accepts `n_hands` as a parameter.
