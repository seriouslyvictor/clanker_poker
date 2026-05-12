# Phase 6: Viewer Experience — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-12
**Phase:** 06-viewer-experience
**Areas discussed:** Idle state detection, Game trigger & demand gate, Prediction widget, Last game result

---

## Idle State Detection

| Option | Description | Selected |
|--------|-------------|----------|
| Frontend heuristic | `connectionState === 'open' && gameState === null` → idle. Zero backend changes. | |
| Backend game_status event | Backend sends explicit `event: game_status { running: false/true }`. More authoritative. | ✓ |
| Idle game state snapshot | Backend sends placeholder GameState with `phase: 'IDLE'`. | |

**User's choice:** Backend game_status event

---

| Option | Description | Selected |
|--------|-------------|----------|
| On connect + session transitions | Send on every SSE connect AND on each session start/end. Late joiners always know state. | ✓ |
| Only on session transitions | Send only when game starts/ends. Late joiners during idle get no signal. | |

**User's choice:** On connect + session transitions (Recommended)

---

## Game Trigger & Demand Gate

| Option | Description | Selected |
|--------|-------------|----------|
| asyncio.Event + POST endpoint | `game_loop` waits on asyncio.Event; POST /api/game/start sets it with viewer count check. | ✓ |
| Polling loop | game_loop polls broker.viewer_count and auto-starts when > 0. | |
| WebSocket for coordination | Dedicated WebSocket channel for game control. More complex. | |

**User's choice:** asyncio.Event + POST endpoint (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Require ≥1 viewer | POST /api/game/start returns 400 if no viewers connected (bot-proofs the demand gate). | ✓ |
| Allow any click | Any click starts a game; only prevents double-starts. | |

**User's choice:** Require ≥1 viewer (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Show live game immediately | Second viewer gets live game snapshot; no idle screen. | ✓ |
| Show idle screen with disabled button | Second viewer sees idle with "Game in progress" message. | |

**User's choice:** Show live game immediately (Recommended)

---

## Prediction Widget

| Option | Description | Selected |
|--------|-------------|----------|
| From deal until SHOWDOWN | Visible PRE-FLOP → RIVER; disappears at SHOWDOWN/WINNER. | ✓ |
| Only on FLOP or later | Appears after flop dealt; viewers have more info. | |

**User's choice:** From deal until SHOWDOWN (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Floating overlay above community cards | Centered panel matching winner overlay pattern. | ✓ |
| Inside ReasoningPanel sidebar | Lives in left sidebar. | |
| Fixed bottom bar | Thin strip across bottom with player chips. | |

**User's choice:** Floating overlay above community cards (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Per hand | Fresh prediction each hand; localStorage tracks { handId, prediction, result }. | ✓ |
| Per session | One prediction per game session (10 hands). | |

**User's choice:** Per hand (Recommended)

---

## Last Game Result

| Option | Description | Selected |
|--------|-------------|----------|
| Redis (backend-owned, shared) | Backend stores last result; included in game_status payload. All viewers see same data. | ✓ |
| localStorage (frontend-only) | Frontend captures WINNER state; fresh browser shows nothing. | |

**User's choice:** Redis (Recommended)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Winner name + hand name only | `{ winnerName, winnerOrg, winnerHand }` — minimal, matches WINNER overlay. | ✓ |
| Full final game state | Full GameState snapshot — heavier, more detail. | |

**User's choice:** Winner name + hand name only (Recommended)

---

## Claude's Discretion

- Idle screen visual design (Balatro aesthetic)
- PredictionWidget animation timing
- `handId` generation strategy
- `POST /api/game/start` response body
- asyncio.Event attribute naming on app.state

## Deferred Ideas

- Live viewer count display (v2)
- Prediction streak tracking (v2)
- Pre-game lobby countdown (v2)
- Configurable hands per session (pending todo, not blocking)
- Optional archetypes mode (pending todo, not blocking)
