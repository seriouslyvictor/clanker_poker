---
status: complete
phase: 05-frontend-wiring
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md]
started: 2026-05-11T00:00:00Z
updated: 2026-05-11T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Graceful loading state
expected: Open http://localhost:5173 with FastAPI stopped. Browser shows "Connecting to game..." centered — no crash, no blank page, no JS errors in DevTools console.
result: pass

### 2. CORS no errors
expected: Run Vite (5173) + FastAPI (8000) simultaneously. Open Vite app, check DevTools console — no CORS errors, EventSource shows 200 status, no "Access-Control-Allow-Origin" violations.
result: pass

### 3. Live game rendering
expected: Player cards, community cards, chip counts, and pot all update in real time without page refresh. Phase indicator changes (PRE-FLOP → FLOP → TURN → RIVER → SHOWDOWN). Winner overlay appears at showdown.
result: pass

### 4. ReasoningPanel populates during play
expected: ReasoningPanel on the left shows reasoning entries appearing as each AI player thinks. Text streams in token-by-token during decision phases.
result: pass

### 5. Reconnecting overlay on disconnect
expected: Kill the FastAPI backend (or use DevTools → Network → Offline) while a game is visible. A semi-transparent "Reconnecting..." overlay appears on top of the frozen game state — the game content is still visible behind it. The frozen frame is NOT shown silently.
result: pass

### 6. Auto-reconnect resumes game
expected: After the reconnecting overlay appears (test 5), bring the backend back up (or go back Online). Within ~3 seconds the overlay disappears and the game resumes from current state — no manual refresh required.
result: issue
reported: "Partially — pot reset to initial value on reconnect, but chips, play order, and other state were consistent."
severity: major

### 7. Reasoning snapshot on reconnect
expected: During a live game with reasoning visible in ReasoningPanel, disconnect and reconnect (test 5→6 flow). After reconnect, the reasoning entries that existed before the disconnect are still present in ReasoningPanel — no entries lost, no entries duplicated.
result: pass

### 8. Mid-hand join sees reasoning
expected: With a game running and past the pre-flop phase, open a second browser tab to http://localhost:5173. The ReasoningPanel in the new tab shows reasoning accumulated so far this hand — it is NOT empty.
result: pass

## Summary

total: 8
passed: 7
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "After reconnect, game resumes from current state with no state inconsistencies"
  status: fixed
  reason: "User reported: pot reset to initial value on reconnect, but chips, play order, and other state were consistent."
  severity: major
  test: 6
  root_cause: "game.py run_betting_round only updates game_state.pot via _collect_bets_to_pot at round end. Per-action broadcasts fired with stale round-start pot (0 at pre-flop start). Redis snapshot captured mid-round showed pot=0."
  fix: "Track _pot_at_round_start before betting loop. Compute live pot = _pot_at_round_start + sum(p.bet) before each broadcast, restore to _pot_at_round_start after so _collect_bets_to_pot is not double-counted."
  artifacts: [backend/app/engine/game.py]
