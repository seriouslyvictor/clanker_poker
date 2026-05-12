---
title: Frozen game screen when server dies or connection is severed
area: frontend
priority: high
phase_context: 05-gap
created: 2026-05-11
---

## Problem

When the backend dies or the SSE connection is severed, both browsers show a frozen game screen at the last known state. The `onerror` handler sets `connectionState` to `'connecting'` but `Game.tsx` only checks `if (!gameState)` — once gameState is non-null it never goes back to the loading/reconnecting state.

## Expected

When connection is lost, the UI should visually indicate it is reconnecting (e.g. overlay or badge: "Reconnecting...") rather than showing a frozen stale state. On reconnect, the game resumes normally.

## Fix direction

1. In `Game.tsx`: check `connectionState` prop (pass it through from PokerApp) — render a "Reconnecting..." overlay when `connectionState === 'connecting'` AND `gameState !== null` (i.e. we had a connection before).
2. `PokerApp.tsx`: destructure `connectionState` from `useGameStream()` and pass to `<Game>`.
3. `GameProps`: add `connectionState: ConnectionState` prop.
