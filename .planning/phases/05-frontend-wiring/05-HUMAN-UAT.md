---
status: partial
phase: 05-frontend-wiring
source: [05-VERIFICATION.md]
started: 2026-05-10T00:00:00Z
updated: 2026-05-10T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live game rendering
expected: Player cards, community cards, chip counts, and pot all update in real time without any page refresh. Phase indicator changes. Pot accumulates. Winner overlay appears at showdown.
result: [pending]

**Setup:** `docker compose up -d redis` → `cd backend && uv run uvicorn app.main:app --reload` → start a game → open http://localhost:5173

### 2. Auto-reconnect within 3 seconds
expected: Client reconnects automatically within ~3 seconds after network interruption. Game state is current (not stale). No manual refresh required.
result: [pending]

**Setup:** With UI connected, use browser DevTools Network tab to go offline for 4 seconds, then back online.

### 3. Reasoning survives reconnect
expected: Reasoning text accumulated before the disconnect is still visible in ReasoningPanel after reconnect. No entries lost. No entries duplicated.
result: [pending]

**Setup:** During live game with reasoning streaming, disconnect and reconnect as in test 2. Inspect ReasoningPanel.

### 4. Graceful loading state
expected: Browser shows "Connecting to game..." centered on screen when backend is not running. No crash, no blank page, no unhandled JS errors in DevTools console.
result: [pending]

**Setup:** Open http://localhost:5173 with FastAPI backend stopped.

### 5. CORS no errors
expected: No CORS errors in DevTools console. EventSource connection shows 200 status. No "Access-Control-Allow-Origin" violations.
result: [pending]

**Setup:** Run Vite (port 5173) and FastAPI (port 8000) simultaneously. Open Vite app. Check DevTools console.

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
