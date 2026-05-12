---
title: Reasoning panel empty when joining mid-game
area: frontend+backend
priority: high
phase_context: 05-gap
created: 2026-05-11
---

## Problem

ReasoningPanel is empty for any viewer who joins mid-game. The `reasoning_snapshot` event is only populated if the current hand is still in a decision phase with active `rpush` calls — but each call to `publish()` (phase transition) deletes `REASONING_SNAPSHOT_KEY`, so late joiners connecting after a phase boundary see nothing.

Code review WR-03 flagged this: snapshot is cleared on every phase transition, not at hand start.

## Expected

A viewer connecting at any point during a hand should see all reasoning accumulated so far for the current hand — across all players and phases.

## Fix direction

1. In `publisher.py`: change the `delete(REASONING_SNAPSHOT_KEY)` from `publish()` (phase transition) to only trigger when phase is `"dealing"` or `"pre_flop"` (new hand start). This way reasoning accumulates across all phases of a hand and is only cleared when the next hand begins.
2. Alternatively: use a separate `HAND_REASONING_KEY` that accumulates for the full hand and only clears on new hand deal.
