---
status: diagnosed
phase: 06-viewer-experience
source: [06-VERIFICATION.md]
started: 2026-05-12T00:00:00Z
updated: 2026-05-14T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Idle screen visual transition
expected: Browser briefly shows CONNECTING... then transitions to IdleScreen with Balatro branding, felt texture, and START A GAME button
result: pass

### 2. Start game button behavior
expected: Clicking START A GAME changes button to STARTING... (disabled); once game_status {running:true} arrives via SSE, PokerApp switches to Game view automatically
result: pass

### 3. Idle → game → idle full cycle
expected: After a 10-hand session completes, SSE delivers game_status {running:false, lastWinner:{...}}, PokerApp switches back to IdleScreen and the last-result callout shows winner info
result: pass

### 4. Prediction widget States A and B
expected: During PRE-FLOP, FLOP, TURN, or RIVER — widget appears bottom-right with "WHO WINS THIS HAND?" and 4 player chips. Clicking a chip collapses to "PREDICTED:" + single chip (State B). localStorage.getItem('poker_prediction') returns JSON with prediction set.
result: issue
reported: "I see nothing and json returns nothing"
severity: major

### 5. Prediction widget State C result reveal
expected: At WINNER phase — widget shows ConfettiBurst + GoldCrownChip "CORRECT!" if predicted player won, or red StakeChip "WRONG" if not. Sub-label "You picked {name}" visible. This was the gap fixed by adding WINNER to PREDICTION_PHASES.
result: blocked
blocked_by: prior-phase
reason: "Widget not visible in State A/B (test 4 failed) — State C cannot be verified until widget rendering is fixed"

### 6. 503 error handling on Start click
expected: Clicking START A GAME when no SSE connection is active returns 503 from backend; button resets to "START A GAME" (not permanently frozen); no crash in console
result: skipped
reason: "Could not isolate the exact path (no-SSE-client + click START). Adjacent behavior confirmed correct: game survives viewer disconnect mid-session (by design — demand gate only applies to starting, not stopping). SSE late-joiner reconnect also verified working. 503 path itself untested."

## Summary

total: 6
passed: 3
issues: 1
blocked: 1
skipped: 1

## Gaps

- truth: "PredictionWidget visible bottom-right during PRE-FLOP/FLOP/TURN/RIVER with WHO WINS THIS HAND? and 4 player chips; clicking a chip collapses to PREDICTED: + single chip; localStorage.getItem('poker_prediction') returns JSON"
  status: failed
  reason: "User reported: I see nothing and json returns nothing"
  severity: major
  test: 4
  root_cause: "Tweaks button in PokerApp.tsx is position:fixed, bottom:16, right:16, zIndex:400 — same viewport coordinates as PredictionWidget (position:absolute, bottom:16, right:16, zIndex:30). Tweaks button (zIndex 400) completely covers the widget (zIndex 30). Removing the Tweaks button relic fixes both gaps."
  artifacts: [frontend/src/components/PokerApp.tsx]
  missing: []

- truth: "No stale UI controls visible — Tweaks button is a brainstorm relic and must be removed from the UI"
  status: failed
  reason: "User reported: there is a 'tweaks' button in the UI that is a relic from brainstorm and should be removed"
  severity: minor
  test: observed
  root_cause: "TweaksPanel and its toggle button remain in PokerApp.tsx. Removing them (same fix as above) clears the stale control and also unblocks the PredictionWidget."
  artifacts: [frontend/src/components/PokerApp.tsx]
  missing: []

- truth: "Server logs a line when a viewer connects or disconnects (broker.viewer_count change visible in server output)"
  status: failed
  reason: "User reported: broker.viewer_count apparently did not update or if it updated we failed to spot it — should be logged by the server every time a viewer appears or disconnects"
  severity: minor
  test: observed
  root_cause: "broker.subscribe() and broker.unsubscribe() update _queues but never call logger.info. Adding logger.info in both methods makes viewer count changes visible in server output."
  artifacts: [backend/app/broadcast/broker.py]
  missing: []
