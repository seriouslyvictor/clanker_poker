---
status: partial
phase: 06-viewer-experience
source: [06-VERIFICATION.md]
started: 2026-05-12T00:00:00Z
updated: 2026-05-12T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Idle screen visual transition
expected: Browser briefly shows CONNECTING... then transitions to IdleScreen with Balatro branding, felt texture, and START A GAME button
result: [pending]

### 2. Start game button behavior
expected: Clicking START A GAME changes button to STARTING... (disabled); once game_status {running:true} arrives via SSE, PokerApp switches to Game view automatically
result: [pending]

### 3. Idle → game → idle full cycle
expected: After a 10-hand session completes, SSE delivers game_status {running:false, lastWinner:{...}}, PokerApp switches back to IdleScreen and the last-result callout shows winner info
result: [pending]

### 4. Prediction widget States A and B
expected: During PRE-FLOP, FLOP, TURN, or RIVER — widget appears bottom-right with "WHO WINS THIS HAND?" and 4 player chips. Clicking a chip collapses to "PREDICTED:" + single chip (State B). localStorage.getItem('poker_prediction') returns JSON with prediction set.
result: [pending]

### 5. Prediction widget State C result reveal
expected: At WINNER phase — widget shows ConfettiBurst + GoldCrownChip "CORRECT!" if predicted player won, or red StakeChip "WRONG" if not. Sub-label "You picked {name}" visible. This was the gap fixed by adding WINNER to PREDICTION_PHASES.
result: [pending]

### 6. 503 error handling on Start click
expected: Clicking START A GAME when no SSE connection is active returns 503 from backend; button resets to "START A GAME" (not permanently frozen); no crash in console
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
