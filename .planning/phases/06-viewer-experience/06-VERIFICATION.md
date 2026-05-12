---
phase: 06-viewer-experience
verified: 2026-05-12T16:00:00Z
status: human_needed
score: 12/12 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 11/12
  gaps_closed:
    - "State C (WINNER phase): if prediction was correct, shows ConfettiBurst + GoldCrownChip 'CORRECT!'; if wrong, shows red StakeChip 'WRONG'"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Idle screen full cycle — connect with no game running"
    expected: "Browser shows CONNECTING... briefly, transitions to IdleScreen with IA POKER BATTLEGROUND branding, START A GAME button, and cold-start hint (no last-result callout on fresh deploy)"
    why_human: "Visual appearance and SSE timing cannot be verified programmatically without a running server"
  - test: "Start game flow — click START A GAME"
    expected: "Button label changes to STARTING... and becomes disabled immediately on click; within 5 seconds game begins and UI transitions from IdleScreen to Game view without page reload"
    why_human: "Real-time UI transition via SSE event requires a live browser and server"
  - test: "Idle → game → idle cycle"
    expected: "After a session completes, UI returns to IdleScreen showing last-result callout with winner name, org, and hand (e.g. \"OpenAI's GPT-5 Nano won with Two Pair\")"
    why_human: "Requires completing a full game session with SSE delivering game_status { running: false, lastWinner: {...} }"
  - test: "Prediction widget States A and B"
    expected: "During PRE-FLOP/FLOP/TURN/RIVER: widget shows WHO WINS THIS HAND? with 4 player chips; clicking a chip collapses widget to PREDICTED: + chosen chip; widget disappears at SHOWDOWN"
    why_human: "Live game state progression required; visual confirmation needed"
  - test: "Prediction widget State C — result reveal at WINNER phase"
    expected: "Widget re-appears at WINNER phase (now in PREDICTION_PHASES); if prediction was correct, shows ConfettiBurst + GoldCrownChip CORRECT! + 'You picked {name}'; if wrong, shows red StakeChip WRONG + 'You picked {name}'"
    why_human: "Requires completing a live hand with a prior prediction made; visual and animation behavior needs human confirmation"
  - test: "503 guard behavior — clicking START A GAME when no SSE clients are connected from backend's view"
    expected: "Frontend does not crash on 503; button resets to START A GAME (isStarting false) after error"
    why_human: "Error path behavior in browser required"
---

# Phase 6: Viewer Experience — Verification Report

**Phase Goal:** Viewers always see a meaningful screen (idle or game). Demand gate prevents game running without a viewer. Anonymous prediction widget gives active engagement including result reveal.
**Verified:** 2026-05-12T16:00:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (PREDICTION_PHASES fix in Game.tsx)

---

## Re-verification Summary

**Gap closed:** `PREDICTION_PHASES` in `frontend/src/components/Game.tsx` line 25 now reads:

```typescript
const PREDICTION_PHASES = new Set(['PRE-FLOP', 'FLOP', 'TURN', 'RIVER', 'WINNER'])
```

`'WINNER'` was added, making the PredictionWidget mount at the WINNER phase and allowing State C (result reveal) to execute.

**Score movement:** 11/12 → 12/12. All must-have truths now verified.

**Regressions:** None. No other files were modified by the fix.

---

## Goal Achievement

### Observable Truths

All must-haves are derived from the merged set of ROADMAP success criteria and PLAN frontmatter truths. Plans 06-01, 06-02, and 06-03 contributed truths; ROADMAP Phase 6 SC-1 through SC-4 are the non-negotiable contract.

#### Plan 06-01 Must-Have Truths (Backend Demand Gate)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /api/game/start returns 200 when no game running and at least one viewer connected | VERIFIED | `backend/app/api/game.py` line 23-28: checks `game_running` (409) and `viewer_count < 1` (503), calls `start_event.set()`, returns `{"started": True}` |
| 2 | POST /api/game/start returns 409 when a game is already running | VERIFIED | `backend/app/api/game.py` line 23-24: `if request.app.state.game_running: raise HTTPException(status_code=409)` |
| 3 | POST /api/game/start returns 503 when broker.viewer_count is 0 | VERIFIED | `backend/app/api/game.py` line 25-26: `if request.app.state.broker.viewer_count < 1: raise HTTPException(status_code=503)` |
| 4 | game_status SSE event fires on every connect/reconnect as last item in snapshot sequence | VERIFIED | `backend/app/api/stream.py` lines 74-99: game_status `yield` block appears after game_state snapshot and reasoning_snapshot, before `while True:` drain |
| 5 | game_status fires with running:true when session starts, running:false with lastWinner when session ends | VERIFIED | `backend/app/game_loop.py` lines 65, 115-116: `publish_game_status(broker, redis_client, running=True)` before session; `publish_game_status(broker, redis_client, running=False)` after Redis write |
| 6 | game:last_result Redis key written with winnerName, winnerOrg, winnerHand after each session | VERIFIED | `backend/app/game_loop.py` lines 105-113: `redis_client.set(GAME_LAST_RESULT_KEY, json.dumps({winnerName, winnerOrg, winnerHand}), ex=SNAPSHOT_TTL)` |
| 7 | game_loop.py waits on asyncio.Event rather than auto-looping — no game starts without trigger | VERIFIED | `backend/app/game_loop.py` line 62: `await start_event.wait()` as first statement in the while-True body; `start_event.clear()` on line 63 consumes the signal |

#### Plan 06-02 Must-Have Truths (Frontend IdleScreen)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 8 | When no game is running, app shows IdleScreen (not Game, not blank) | VERIFIED | `frontend/src/components/PokerApp.tsx` line 55-57: `if (gameRunning === false) { return <IdleScreen ... /> }` |
| 9 | When connecting (gameRunning is null), app shows CONNECTING... text at full viewport | VERIFIED | `frontend/src/components/PokerApp.tsx` lines 35-53: `if (gameRunning === null) { return <div ...>CONNECTING...</div> }` |
| 10 | IdleScreen shows project branding, optional last-result callout, and START A GAME button | VERIFIED | `frontend/src/components/IdleScreen.tsx`: branding (`IA POKER BATTLEGROUND`, `WATCH AI MODELS BATTLE IT OUT`), conditional `lastWinner !== null` callout, `bal-btn bal-btn-orange` button |
| 11 | Clicking START A GAME issues POST /api/game/start; button switches to STARTING... and becomes disabled | VERIFIED | `IdleScreen.tsx` line 13-21: `handleStart` sets `isStarting=true`, calls `await onStart()`; `PokerApp.tsx` line 20-30: `handleStart` fetches `/api/game/start` |

#### Plan 06-03 Must-Have Truths (Prediction Widget)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 12 | PredictionWidget renders as floating overlay (bottom-right) during PRE-FLOP, FLOP, TURN, RIVER | VERIFIED | `Game.tsx` line 173: `PREDICTION_PHASES.has(gameState.phase) && <PredictionWidget ...>`; `PredictionWidget.tsx` panelStyle: `position:'absolute', bottom:16, right:16, zIndex:30` |
| 13 | PredictionWidget is not mounted during DEALING or SHOWDOWN phases | VERIFIED | `Game.tsx` line 25: `PREDICTION_PHASES = new Set(['PRE-FLOP', 'FLOP', 'TURN', 'RIVER', 'WINNER'])` — DEALING and SHOWDOWN excluded; WINNER now included to enable State C |
| 14 | State A: four player chips show — clicking one stores prediction in localStorage and collapses to State B | VERIFIED | `PredictionWidget.tsx` lines 71-79: `handlePick` stores via `savePrediction(record)` (localStorage.setItem); State A renders chips with `onClick={() => handlePick(player.id)}` |
| 15 | State B: shows 'PREDICTED:' + the chosen player chip — no further interaction | VERIFIED | `PredictionWidget.tsx` lines 141-153: `if (prediction !== null && pickedPlayer !== null)` returns div with `PREDICTED:` header and StakeChip |
| 16 | State C (WINNER phase): if prediction was correct, shows ConfettiBurst + GoldCrownChip 'CORRECT!'; if wrong, shows red StakeChip 'WRONG' | VERIFIED | `Game.tsx` line 25: `'WINNER'` now in `PREDICTION_PHASES` — widget is mounted at WINNER phase. `PredictionWidget.tsx` lines 53-69: `useEffect` sets `result: 'correct'\|'wrong'` when `gameState.phase === 'WINNER'`. Lines 121-138: State C guard `gameState.phase === 'WINNER' && prediction?.result !== null` renders ConfettiBurst+GoldCrownChip or red StakeChip. Data flow is now live. |
| 17 | localStorage key 'poker_prediction' holds { handId, prediction, result } | VERIFIED | `PredictionWidget.tsx` line 19: `PREDICTION_KEY = 'poker_prediction'`; `PredictionRecord` interface lines 13-17; `savePrediction` writes JSON |
| 18 | Prediction resets for each new hand (winner null-transition detection) | VERIFIED | `PredictionWidget.tsx` lines 40-50: `useEffect` on `gameState.winner`: if prev non-null and current null → `setPrediction(null)` + `localStorage.removeItem(PREDICTION_KEY)` |
| 19 | slideIn animation plays on widget mount | VERIFIED | `PredictionWidget.tsx` line 97: `animation: 'slideIn 0.25s ease-out both'` in panelStyle |

**Score: 12/12 truths verified**

---

### ROADMAP Success Criteria Coverage

| SC | Text | Status | Notes |
|----|------|--------|-------|
| SC-1 | Idle screen with branding, last game result, Start CTA — not blank | VERIFIED | IdleScreen.tsx implements all three elements; PokerApp routes correctly |
| SC-2 | Clicking Start causes game within 5s; button disabled immediately; no double-start | VERIFIED (partial human) | Backend 409 guard + client isStarting disable verified in code; 5s timing requires human |
| SC-3 | Viewer selects AI they predict will win; prediction UI disappears after pick; result shown at showdown | VERIFIED (human needed) | State A (pick), State B (collapse), State C (result reveal) all reachable now that WINNER is in PREDICTION_PHASES. End-to-end behavior requires human confirmation with a live game |
| SC-4 | Idle → game → idle cycle: after showdown UI returns to idle showing last result | VERIFIED (human needed) | Backend writes `game:last_result`, SSE delivers `game_status { running: false, lastWinner }`, PokerApp routes back to IdleScreen; end-to-end timing requires human |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/broadcast/broker.py` | viewer_count property | VERIFIED | Lines 39-43: `@property def viewer_count(self) -> int: return len(self._queues)` |
| `backend/app/broadcast/publisher.py` | publish_game_status() + GAME_LAST_RESULT_KEY | VERIFIED | Line 31: constant; lines 88-116: async function with broker.broadcast() |
| `backend/app/api/game.py` | POST /api/game/start endpoint | VERIFIED | Lines 12-29: @router.post with 409/503/200 guards, start_event.set() |
| `backend/app/game_loop.py` | demand-gated loop using asyncio.Event | VERIFIED | Lines 62-63: await start_event.wait(); start_event.clear() |
| `backend/app/main.py` | app.state.start_event, app.state.game_running, game_router included | VERIFIED | Lines 54-55: asyncio.Event() + False; line 9: import game_router; line 104: include_router |
| `backend/app/api/stream.py` | game_status snapshot in snapshot sequence | VERIFIED | Lines 74-99: game_status yield block, last before while-True drain |
| `frontend/src/components/types.ts` | GameStatus interface export | VERIFIED | Lines 43-46: `export interface GameStatus { running: boolean; lastWinner?... }` |
| `frontend/src/hooks/useGameStream.ts` | gameRunning and lastWinner state from game_status events | VERIFIED | Lines 10-11: interface fields; lines 55-56: useState; lines 110-120: addEventListener |
| `frontend/src/components/IdleScreen.tsx` | IdleScreen with branding, last-result, Start button | VERIFIED | Full implementation present; all required text elements confirmed |
| `frontend/src/components/PokerApp.tsx` | Routing on gameRunning tri-state | VERIFIED | Lines 35-57: null→CONNECTING, false→IdleScreen, true→Game |
| `frontend/src/components/PredictionWidget.tsx` | Floating overlay States A/B/C with localStorage | VERIFIED | All three states reachable — WINNER added to PREDICTION_PHASES in Game.tsx closes the gap |
| `frontend/src/components/StakeChip.tsx` | onClick prop extension | VERIFIED | Lines 7: `onClick?: () => void`; line 29: `cursor: onClick ? 'pointer' : 'default'` |
| `frontend/src/components/Game.tsx` | PredictionWidget rendered inside game layout, WINNER in PREDICTION_PHASES | VERIFIED | Line 25: `new Set(['PRE-FLOP', 'FLOP', 'TURN', 'RIVER', 'WINNER'])`; line 10: import; lines 173-177: conditional render |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/api/game.py` | `app.state.start_event` | `start_event.set()` on POST | WIRED | Line 28: `request.app.state.start_event.set()` |
| `backend/app/game_loop.py` | `backend/app/broadcast/publisher.py` | `publish_game_status(broker, redis_client, running=...)` | WIRED | Lines 65, 115-116 call publish_game_status |
| `backend/app/api/stream.py` | `GAME_LAST_RESULT_KEY` | `redis_client.get(GAME_LAST_RESULT_KEY)` in snapshot | WIRED | Line 24: import; line 77: redis_client.get(GAME_LAST_RESULT_KEY) |
| `frontend/src/hooks/useGameStream.ts` | `frontend/src/components/PokerApp.tsx` | gameRunning and lastWinner returned | WIRED | Line 14: destructure; line 134: return includes both |
| `frontend/src/components/PokerApp.tsx` | `frontend/src/components/IdleScreen.tsx` | `<IdleScreen theme={theme} lastWinner={lastWinner} onStart={handleStart} />` | WIRED | Line 56 |
| `frontend/src/components/IdleScreen.tsx` | POST /api/game/start | `await onStart()` in handleStart | WIRED | PokerApp.tsx handleStart (lines 20-30) fetches `/api/game/start`; IdleScreen calls `await onStart()` (line 16) |
| `frontend/src/components/Game.tsx` | `frontend/src/components/PredictionWidget.tsx` | `PREDICTION_PHASES.has(gameState.phase)` including WINNER | WIRED | Mount gate includes WINNER phase; widget mounted when State C must execute |
| `frontend/src/components/PredictionWidget.tsx` | localStorage | `localStorage.setItem('poker_prediction', ...)` | WIRED | `savePrediction` function (line 30-32) and `localStorage.removeItem` (line 47) |
| `frontend/src/components/PredictionWidget.tsx` | `frontend/src/components/GoldCrownChip.tsx` | `<GoldCrownChip size='md' label='CORRECT!' />` | WIRED | Line 128: GoldCrownChip used in State C — imported and called correctly; State C now reachable |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `IdleScreen.tsx` | `lastWinner` | `useGameStream` → `game_status` SSE event → Redis `game:last_result` | Yes — `game_loop.py` writes real session winner after each session | FLOWING |
| `PokerApp.tsx` | `gameRunning` | `useGameStream` → `game_status` SSE event → `app.state.game_running` | Yes — set by game_loop.py before/after sessions | FLOWING |
| `PredictionWidget.tsx` | `gameState.phase`, `gameState.winner`, `gameState.players` | `useGameStream` → `game_state` SSE event → Redis `game:state:last` | Yes — live game state from real session | FLOWING |
| `PredictionWidget.tsx` | State C result (`prediction.result`) | `gameState.phase === 'WINNER'` useEffect sets result from `gameState.winner` index | Yes — winner index from live game state; result set to 'correct' or 'wrong' by comparison | FLOWING |

---

### Behavioral Spot-Checks

Step 7b: SKIPPED — verification requires a running FastAPI server + Redis. Static code analysis performed instead.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| VIEWER-01 | 06-01, 06-02 | Idle screen with branding, last game result, Start CTA | SATISFIED | IdleScreen.tsx implements all elements; PokerApp routes correctly |
| VIEWER-02 | 06-01, 06-02 | Any viewer can start a game; demand gate enforced server-side | SATISFIED | POST /api/game/start with 409/503 guards; asyncio.Event demand gate; START A GAME button |
| VIEWER-03 | 06-03 | Anonymous prediction before showdown; result shown at showdown | SATISFIED | States A (pick), B (display), and C (result reveal) all implemented and reachable. WINNER phase is now in PREDICTION_PHASES — widget is mounted when State C executes. Human testing needed to confirm visual output. |

---

### Anti-Patterns Found

No blockers. The previously identified blocker (dead `gameState.phase === 'WINNER'` guard in PredictionWidget.tsx) is resolved — the guard is now reachable because Game.tsx mounts the widget during WINNER phase.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | — |

---

### Human Verification Required

#### 1. Idle Screen Visual Transition

**Test:** Open browser to `http://localhost:5173` with backend not running a game
**Expected:** Briefly shows `CONNECTING...` text centered on the table background, then transitions to IdleScreen with "IA POKER BATTLEGROUND" title, "Be the first viewer to start a game" hint, and orange START A GAME button
**Why human:** Visual appearance and SSE event timing cannot be verified without a live server + browser

#### 2. Start Game Button Behavior

**Test:** Click START A GAME with backend and Redis running (at least one SSE viewer connected)
**Expected:** Button immediately shows `STARTING...` and is disabled. Within 5 seconds, UI transitions from IdleScreen to Game view showing a live hand
**Why human:** Real-time SSE-triggered UI transition requires live server interaction; 5-second timing cannot be measured statically

#### 3. Idle → Game → Idle Full Cycle

**Test:** Start a game, let it complete all 10 hands
**Expected:** After session ends, UI automatically returns to IdleScreen showing the last-result callout: "{org}'s {name} won with {hand}"
**Why human:** Requires completing a full game session (~several minutes) with SSE delivering `game_status { running: false, lastWinner: {...} }`

#### 4. Prediction Widget States A and B

**Test:** During PRE-FLOP phase, observe bottom-right corner; click a player chip
**Expected:** Widget shows "WHO WINS THIS HAND?" with 4 player chips. After click, collapses to "PREDICTED:" with single chip. Widget disappears when game reaches SHOWDOWN phase
**Why human:** Visual and interactive behavior requires live game state progression

#### 5. Prediction Widget State C — Result Reveal

**Test:** During PRE-FLOP/FLOP/TURN/RIVER, pick a player. Let the hand play out to WINNER phase.
**Expected:** Widget re-appears at WINNER phase showing either: (a) ConfettiBurst + gold "CORRECT!" chip + "You picked {name}" if the predicted player won, or (b) red "WRONG" chip + "You picked {name}" if they lost.
**Why human:** Requires a live hand with a prior prediction. State C result computation happens via useEffect in the browser — visual and animation output needs human eyes. This is the key closed gap.

#### 6. 503 Error Handling

**Test:** Click START A GAME before any SSE client has subscribed (no viewer count)
**Expected:** Backend returns 503; IdleScreen button resets to `START A GAME` (isStarting reverts to false); no crash
**Why human:** Error path requires network inspection and visual confirmation

---

### Gaps Summary

No gaps remain. The single previously identified gap is closed:

**Gap closed:** State C (prediction result reveal) was unreachable because `'WINNER'` was absent from `PREDICTION_PHASES` in Game.tsx. The fix — adding `'WINNER'` to the Set on line 25 — means the widget is now mounted during WINNER phase. The `useEffect` that computes the result (`correct`/`wrong`) fires when `gameState.phase === 'WINNER'`, and the State C render branch at PredictionWidget.tsx line 122 is now reachable code.

All 12 must-have truths are verified in static analysis. The phase is ready for human verification of visual and real-time behaviors.

---

_Verified: 2026-05-12T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification after gap fix: PREDICTION_PHASES 'WINNER' addition in Game.tsx_
