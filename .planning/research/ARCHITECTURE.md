# Architecture Research — LLM Poker Arena

**Project:** LLM Poker Arena  
**Researched:** 2026-05-01  
**Overall Confidence:** HIGH (verified with current game server patterns, Node.js best practices, and 2026 SSE/streaming standards)

---

## Executive Summary

The LLM Poker Arena requires a **server-authoritative game engine** running as a singleton process that persists across HTTP request/response cycles. The architecture separates three tiers:

1. **Game Engine Layer** — Stateful poker logic, LLM orchestration, hand evaluation (runs in a background process or isolated server memory)
2. **Broadcast Layer** — SSE connection management, state change detection, real-time sync to all connected viewers
3. **Frontend Layer** — Next.js React UI consuming SSE stream (already built)

The key architectural challenge is decoupling the long-lived game loop from HTTP request/response semantics. Rather than force game logic into API routes, we recommend a **separate background process** (Worker) or **in-process singleton with event emission**. For a VPS, the Worker approach scales more predictably and isolates game crashes from the web server.

The system uses **Redis** for transient state (current game, viewer connections) and **PostgreSQL** for persistent history (game records, replay data). Viewer presence is tracked via SSE connection lifecycle (connect/disconnect events), and the game loop only runs when viewers are present.

---

## Component Map

### Tier 1: Game Engine (Stateful Singleton)

| Component | Responsibility | Owned State | Communicates With |
|-----------|---------------|-------------|-------------------|
| **GameEngine** | Core poker logic, player actions, hand evaluation, state transitions | Game state (players, cards, pot, phase) | GamePhaseOrchestrator, Persistor |
| **GamePhaseOrchestrator** | Manages pre-flop → flop → turn → river → showdown sequence; decides when LLM calls happen | Phase state (current phase, action player, decision pending) | LLMOrchestrator, GameEngine, BroadcastEventBus |
| **LLMOrchestrator** | Calls 4 LLM APIs sequentially with timeout/retry/streaming; aggregates reasoning | Decision results (action, confidence, reasoning text) | GamePhaseOrchestrator, LLMClients |
| **PokerMathEngine** | Hand evaluation, pot odds, win probability calculation (NOT by LLM) | — (pure functions) | GameEngine |
| **ArchetypeEngine** | Maps personality archetype → decision bias in player behavior | Archetype definitions, bias multipliers | LLMOrchestrator (context injection) |
| **Persistor** | Writes game history to database; loads/saves game state | — (query interface) | GameEngine (on phase changes) |
| **GameLoopController** | Manages singleton lifecycle; start/stop on viewer presence; timing constraints | Loop state (running/idle), interval timing | GameEngine, ViewerPresenceManager |

### Tier 2: Broadcast & Connection Layer (HTTP-Facing)

| Component | Responsibility | Owned State | Communicates With |
|-----------|---------------|-------------|-------------------|
| **SSEConnectionManager** | Accept SSE connections; track viewer presence; emit/broadcast state deltas | Active connections (Set<Response>), viewer count | ViewerPresenceManager, BroadcastEventBus |
| **ViewerPresenceManager** | Tracks connected viewers; manages game loop start/stop demand | Connected viewer list, heartbeat timers | SSEConnectionManager, GameLoopController |
| **BroadcastEventBus** | Central event emitter for game state changes; routes to all SSE clients | — (pub/sub mediator) | All tiers (observer pattern) |
| **StateDeltaEncoder** | Computes minimal state changes between game ticks; sends only deltas to clients | — (pure encoding) | BroadcastEventBus |

### Tier 3: API Routes (Request/Response Handlers)

| Component | Responsibility | Owned State | Communicates With |
|-----------|---------------|-------------|-------------------|
| **POST /api/games/create** | Trigger new game start (if viewers present); return game ID | — (command handler) | GameLoopController |
| **GET /api/games/:id/sse** | Establish SSE connection; stream game state updates | — (connection handler) | SSEConnectionManager |
| **GET /api/games/:id/state** | Snapshot query (viewer joins after game started); return current state | — (query handler) | GameEngine |
| **POST /api/viewers/bet** | Record spectator prediction before showdown | Viewer bets (ephemeral) | Persistor |
| **GET /api/stats** | Game history, viewer count, uptime metrics | — (query handler) | Persistor, ViewerPresenceManager |

---

## Data Flow

### Game Loop (Per-Phase Cycle)

```
1. GameLoopController.tick() fires at interval (0.5–2 Hz depending on phase)
   ↓
2. GamePhaseOrchestrator.step()
   - Checks: Is it time for a player decision?
   - If yes: GameEngine.getDecisionContext() (hand strength, pot odds, etc.)
   ↓
3. LLMOrchestrator.callAllLLMs(context)
   - Call #1: GPT-4o with context (parallel-capable, but we do sequential)
   - Call #2: Gemini 2.0 (wait for #1)
   - Call #3: Claude 3.5 Sonnet (wait for #2)
   - Call #4: Llama 3 local or API (wait for #3)
   - Timeout per call: 8-12 seconds (adjustable)
   - Aggregate: {action, confidence, reasoning}
   ↓
4. GameEngine.applyLLMDecision()
   - Resolve action → pot change, folded players, etc.
   - Detect phase completion (all players acted, river is final)
   ↓
5. BroadcastEventBus.emit('gameStateUpdated', newState)
   - All SSE clients receive delta or full state
   ↓
6. Persistor.logPhaseCompletion(gameId, phase, decisions)
   - Write to PostgreSQL for replay/analytics
   ↓
7. If phase complete: GamePhaseOrchestrator.nextPhase()
   - If showdown: compute hand ranks → winner → emit 'gameEnded'
   - If still in play: loop back to step 2
```

### Viewer Connection Lifecycle

```
Client opens /api/games/:id/sse
   ↓
SSEConnectionManager.addConnection(res)
   ↓
ViewerPresenceManager.onViewerConnected()
   ├─ viewer count: 0 → 1?
   │  └─ YES: GameLoopController.start() (if not running)
   └─ Add heartbeat timer (30-60s ping to keep connection alive)
   ↓
SSE stream open → client receives game state updates
   ↓
Client disconnects or timeout
   ↓
SSEConnectionManager.removeConnection(res)
   ↓
ViewerPresenceManager.onViewerDisconnected()
   ├─ viewer count: 1 → 0?
   │  └─ YES: GameLoopController.stop() (idle after current phase)
   └─ Remove heartbeat timer
```

### State Delta Broadcast

```
GameEngine emits: event 'playerActionResolved'
   ↓
BroadcastEventBus.emit('gameStateUpdated', {
  previousState: {...},
  currentState: {...},
  changedFields: ['players[0].chips', 'pot', 'phase']
})
   ↓
StateDeltaEncoder.encode(event)
   └─ Returns: {type: 'delta', changes: {players: [{index: 0, chips: 800}], pot: 200}}
   ↓
SSEConnectionManager.broadcast(encodedDelta)
   ├─ res1.write('data: ' + JSON.stringify(delta) + '\n\n')
   ├─ res2.write('data: ' + JSON.stringify(delta) + '\n\n')
   └─ ... all open responses
```

---

## Game Engine Singleton Pattern

### Problem

Node.js is request-driven: HTTP handlers execute, return a response, then context is garbage collected. Game loops are **continuous, stateful processes** that span multiple request cycles. You cannot run meaningful game logic in an API route because:

1. The route handler completes in 10-100ms; the game tick takes 10-15 seconds (LLM calls)
2. Route context dies; game state is lost
3. Multiple requests would spawn multiple conflicting game loops

### Solution: Background Process Worker (Recommended for VPS)

Deploy the game engine as a **separate Node.js process** (or thread worker) that:

- Runs indefinitely on the VPS
- Maintains in-memory game state (players, cards, pot)
- Emits events to a pub/sub bus (Redis or in-process EventEmitter)
- Listens for control signals from the main Next.js process (start/stop)

**Implementation outline:**

```javascript
// worker.js (separate process)
import { GameEngine } from './game-engine.js'
import { GameLoopController } from './game-loop-controller.js'
import Redis from 'ioredis'

const redis = new Redis({ host: 'localhost', port: 6379 })
const engine = new GameEngine()
const controller = new GameLoopController(engine)

// Listen for control commands from main process
redis.subscribe('game-control-channel', (err, count) => {
  if (err) console.error('Failed to subscribe:', err)
})

redis.on('message', (channel, message) => {
  const cmd = JSON.parse(message)
  if (cmd.action === 'start') controller.start()
  if (cmd.action === 'stop') controller.stop()
})

// Broadcast state updates to all viewers
engine.on('stateUpdated', (state) => {
  redis.publish('game-state-updates', JSON.stringify(state))
})

// Start heartbeat
controller.setupHeartbeat()
```

**In Next.js API route:**

```javascript
// route: /api/games/:id/sse
import { redis } from '@/lib/redis'

export async function GET(req, res) {
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')

  // Subscribe to game state updates
  const subscriber = redis.duplicate()
  subscriber.subscribe('game-state-updates', (err) => {
    if (err) res.write('event: error\ndata: ' + err + '\n\n')
  })

  subscriber.on('message', (channel, message) => {
    res.write('data: ' + message + '\n\n')
  })

  res.on('close', () => {
    subscriber.unsubscribe()
    subscriber.quit()
  })
}
```

### Alternative: In-Process EventEmitter (Simpler, Monolithic)

If you want a single Node.js process:

```javascript
// game-engine.ts
import { EventEmitter } from 'events'

export class GameEngine extends EventEmitter {
  private gameState: GameState
  private loopInterval: NodeJS.Timer | null = null

  start() {
    if (this.loopInterval) return
    this.loopInterval = setInterval(() => this.tick(), 1000)
  }

  stop() {
    if (this.loopInterval) clearInterval(this.loopInterval)
    this.loopInterval = null
  }

  private async tick() {
    // Execute one phase step
    // ...
    this.emit('stateUpdated', this.gameState)
  }
}

// In Next.js API route: create singleton instance
export const gameEngine = new GameEngine()
gameEngine.start() // Called once on server startup
```

**Trade-offs:**

| Approach | Pros | Cons |
|----------|------|------|
| **Worker Process** | Isolated; crash doesn't kill web server; scales to multiple workers | More complex setup; IPC overhead; requires monitoring |
| **In-Process Singleton** | Simple; low latency; single deployment | Game crash crashes web; harder to scale; blocks event loop if not careful |

**Recommendation for VPS:** Start with **in-process singleton** (simpler), migrate to Worker if you need horizontal scaling.

---

## Viewer Presence System

### Connection Tracking

**SSE is stateless at the HTTP level** — the server doesn't know when a client is "present" until the connection closes. Detection requires:

1. **Connection Accept** — Client opens GET `/api/games/:id/sse` → Server accepts response stream
2. **Heartbeat Ping** — Server sends periodic keep-alive every 30-60 seconds to detect dead connections
3. **Connection Close** — Client disconnect or server timeout → Connection removed from active set

### Implementation

```typescript
class SSEConnectionManager {
  private activeConnections: Set<{
    res: ServerResponse
    viewerId: string
    connectedAt: Date
  }> = new Set()

  addConnection(res: ServerResponse, viewerId: string) {
    const conn = { res, viewerId, connectedAt: new Date() }
    this.activeConnections.add(conn)
    
    // Send initial state
    res.write('data: ' + JSON.stringify({ type: 'init', state: currentGameState }) + '\n\n')
    
    // Setup heartbeat
    const heartbeat = setInterval(() => {
      res.write(':\n') // Comment (no-op), keeps connection alive
    }, 45000)

    res.on('close', () => {
      clearInterval(heartbeat)
      this.activeConnections.delete(conn)
      this.notifyViewerDisconnected()
    })
  }

  broadcast(data: any) {
    const message = 'data: ' + JSON.stringify(data) + '\n\n'
    for (const { res } of this.activeConnections) {
      res.write(message)
    }
  }

  getViewerCount(): number {
    return this.activeConnections.size
  }
}
```

### Demand-Triggered Game Start/Stop

```typescript
class ViewerPresenceManager {
  constructor(
    private sseManager: SSEConnectionManager,
    private gameController: GameLoopController
  ) {}

  onViewerConnected() {
    const count = this.sseManager.getViewerCount()
    if (count === 1) {
      // First viewer → start game (if not running)
      this.gameController.start()
      console.log('[Presence] First viewer connected → game starting')
    }
  }

  onViewerDisconnected() {
    const count = this.sseManager.getViewerCount()
    if (count === 0) {
      // Last viewer left → stop game after current phase
      this.gameController.stopAfterPhase()
      console.log('[Presence] Last viewer disconnected → game stopping')
    }
  }
}
```

### Viewer Count Display

The game state includes a `viewerCount` field that is broadcast with every update:

```typescript
// In GameEngine.tick():
this.emit('stateUpdated', {
  ...gameState,
  viewerCount: this.viewerPresenceManager.getViewerCount()
})

// In frontend (React):
<div>👁️ {gameState.viewerCount} watching</div>
```

---

## LLM Orchestration Layer

### Challenge

You have 4 LLM APIs to call per decision point (pre-flop, flop, turn, river):
- OpenAI GPT-4o
- Google Gemini
- Anthropic Claude
- Llama 3

Each call takes **8-15 seconds** (streaming + token generation). A naive parallel approach wastes compute (all 4 running simultaneously = 15s). Sequential is slower but cheaper (if budget-constrained). The current project doesn't specify parallelization, so **sequential** is safer to start.

### Timeout & Streaming Strategy

**Streaming is critical** because:
- Keeps HTTP connections alive (prevents proxy timeouts at 30-60s)
- Lets you cancel early if reasoning becomes clear
- Reduces perceived latency (reasoning appears incrementally)

```typescript
class LLMOrchestrator {
  async callAllLLMs(context: DecisionContext): Promise<LLMDecisions> {
    const decisions = {
      gpt4o: null,
      gemini: null,
      claude: null,
      llama: null,
    }

    // Call sequentially with timeout
    decisions.gpt4o = await this.callLLMWithTimeout(
      'openai',
      context,
      12000 // 12 second timeout
    )
    
    decisions.gemini = await this.callLLMWithTimeout(
      'google',
      context,
      12000
    )
    
    decisions.claude = await this.callLLMWithTimeout(
      'anthropic',
      context,
      12000
    )
    
    decisions.llama = await this.callLLMWithTimeout(
      'local',
      context,
      8000 // Local LLM faster
    )

    return decisions
  }

  private async callLLMWithTimeout(
    provider: string,
    context: DecisionContext,
    timeoutMs: number
  ): Promise<LLMDecision> {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), timeoutMs)

    try {
      const reasoning = [] // Accumulate streaming chunks
      const stream = await this.getLLMClient(provider).call(
        this.buildPrompt(context),
        { signal: controller.signal }
      )

      for await (const chunk of stream) {
        reasoning.push(chunk)
        // Broadcast partial reasoning to viewers in real-time
        this.broadcastReasoningChunk(provider, chunk)
      }

      const text = reasoning.join('')
      return {
        provider,
        action: this.parseAction(text),
        reasoning: text,
        confidence: this.parseConfidence(text),
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        console.warn(`[LLM] ${provider} timeout after ${timeoutMs}ms`)
        return {
          provider,
          action: 'call', // Fallback: conservative action
          reasoning: '(timeout)',
          confidence: 0.3,
        }
      }
      throw error
    } finally {
      clearTimeout(timeout)
    }
  }

  private buildPrompt(context: DecisionContext): string {
    const archetype = context.player.archetype
    return `
You are a poker player with a ${archetype.name} personality.
${archetype.description}

Your hole cards: ${context.holeCards}
Community cards: ${context.communityCards}
Your chip stack: ${context.chips}
Pot size: ${context.pot}
Players remaining: ${context.playersRemaining}
Current bet to call: ${context.betToCall}
Phase: ${context.phase}

Decide: fold, call, raise, or check?
Explain your reasoning briefly (2-3 sentences).
Format: ACTION: [fold/call/raise/check], CONFIDENCE: [0-100]
`
  }

  private parseAction(text: string): 'fold' | 'call' | 'raise' | 'check' {
    const match = text.match(/ACTION:\s*(fold|call|raise|check)/i)
    return match ? match[1].toLowerCase() as any : 'call'
  }

  private parseConfidence(text: string): number {
    const match = text.match(/CONFIDENCE:\s*(\d+)/i)
    return match ? parseInt(match[1]) / 100 : 0.5
  }

  private broadcastReasoningChunk(provider: string, chunk: string) {
    this.eventBus.emit('reasoningUpdate', {
      provider,
      text: chunk,
      timestamp: Date.now(),
    })
  }
}
```

### Frontend Integration

The reasoning panel subscribes to `reasoningUpdate` events and displays streaming text as it arrives:

```typescript
// ReasoningPanel.tsx
useEffect(() => {
  const handleReasoningUpdate = (event: ReasoningUpdate) => {
    setReasoningText((prev) => ({
      ...prev,
      [event.provider]: (prev[event.provider] || '') + event.text,
    }))
  }

  gameEventBus.on('reasoningUpdate', handleReasoningUpdate)
  return () => gameEventBus.off('reasoningUpdate', handleReasoningUpdate)
}, [])

return (
  <div className="reasoning-panel">
    {Object.entries(reasoningText).map(([provider, text]) => (
      <div key={provider} className="reasoning-card">
        <h4>{provider}</h4>
        <p>{text}</p>
      </div>
    ))}
  </div>
)
```

---

## Storage Requirements

### Transient State (Redis, in-memory TTL)

**Lives for the duration of the current game.** Expires after game ends.

```typescript
// redis key: 'game:{gameId}'
{
  gameId: string
  status: 'waiting' | 'playing' | 'showdown' | 'complete'
  phase: 'preflop' | 'flop' | 'turn' | 'river' | 'showdown'
  players: [
    {
      id: string // LLM provider name
      archetype: string
      chips: number
      holeCards: Card[]
      isFolded: boolean
      betThisRound: number
      action: string | null
      reasoning: string | null
    }
  ]
  communityCards: Card[]
  pot: number
  dealerButton: number
  smallBlind: number
  bigBlind: number
  createdAt: number // timestamp
  expiresAt: number // TTL set to 24 hours
}
```

**TTL:** 24 hours (auto-cleanup if game server crashes)

**Why Redis:**
- Extremely fast reads/writes (sub-millisecond)
- Atomic operations for consistency
- Built-in TTL expiration
- Pub/Sub for broadcasting state changes

### Persistent History (PostgreSQL)

**Recorded at phase completion and game end.** Enables replay, analytics, viewer betting resolution.

```sql
-- Games table
CREATE TABLE games (
  id UUID PRIMARY KEY,
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  winner_id VARCHAR(50), -- LLM provider name
  final_pot_winner BIGINT,
  viewer_count_peak INT,
  status VARCHAR(50)
);

-- Game phases table (log every phase for replay)
CREATE TABLE game_phases (
  id UUID PRIMARY KEY,
  game_id UUID NOT NULL REFERENCES games(id),
  phase_number INT,
  phase_name VARCHAR(50), -- 'preflop', 'flop', 'turn', 'river', 'showdown'
  state_json JSONB, -- Full game state at phase end
  decisions_json JSONB, -- { gpt4o: {...}, gemini: {...}, ... }
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Player decisions table (for analytics)
CREATE TABLE player_decisions (
  id UUID PRIMARY KEY,
  game_id UUID NOT NULL,
  phase_number INT,
  player_id VARCHAR(50), -- LLM provider name
  archetype VARCHAR(100),
  action VARCHAR(50), -- 'fold', 'call', 'raise', 'check'
  reasoning TEXT,
  confidence FLOAT,
  hand_strength FLOAT,
  pot_odds FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Viewer bets table
CREATE TABLE viewer_bets (
  id UUID PRIMARY KEY,
  game_id UUID NOT NULL,
  viewer_fingerprint VARCHAR(255), -- Anonymous IP hash
  predicted_winner VARCHAR(50), -- LLM provider name
  created_at TIMESTAMPTZ DEFAULT NOW(),
  resolved BOOLEAN DEFAULT FALSE,
  correct BOOLEAN
);
```

### What Needs to Persist vs. Cache

| Data | Storage | Reason |
|------|---------|--------|
| Current game state | Redis | Needs microsecond access during game loop |
| Phase transitions | PostgreSQL (async write) | Replay, analytics, debuggability |
| LLM decisions | PostgreSQL (async write) | Understand archetype behavior over time |
| Game outcomes | PostgreSQL | Answer "who won?" for viewer bets, leaderboards |
| Viewer bets | PostgreSQL | Resolve predictions after game |
| Game history for UI | PostgreSQL (read via API) | "Top 10 Games", "Last 20 Winners" |
| Reasoning text | PostgreSQL (optional) | Narrative/entertainment review, not required for game loop |

**Write pattern:**
- Synchronous Redis writes (game loop can't block)
- Asynchronous PostgreSQL writes (fire-and-forget batch writes per phase)

```typescript
// In GamePhaseOrchestrator.onPhaseComplete():
private async logPhaseToDatabase(phase: GamePhase) {
  // Async, doesn't block game loop
  setImmediate(() => {
    db.query('INSERT INTO game_phases (...) VALUES (...)')
      .catch(err => console.error('Failed to log phase:', err))
  })
}
```

---

## Build Order & Component Dependency Graph

### Phase 1: Foundation (Weeks 1-2)

**Goal:** Runnable game loop that plays one hand to completion without LLMs.

**Build in order:**

1. **PokerMathEngine** (pure functions, zero dependencies)
   - Hand evaluation (compare two 5/7-card hands → winner)
   - Pot odds calculation (pot size, hand strength, win probability)
   - Card deck management (shuffle, deal)
   - Testable in isolation with simple unit tests

   ```bash
   npm test -- poker-math-engine.test.ts
   ```

2. **GameState & Immutable Structures**
   - Define types: `GameState`, `Player`, `Card`, `Action`, `Phase`
   - Use immutability patterns (not mutation) for predictable state
   - Enable replay and undo if needed

3. **GameEngine** (core orchestration)
   - Manages players, cards, pot, phase
   - Calls PokerMathEngine to compute hand strength
   - Doesn't call LLMs yet (mock decisions)
   - Has test that plays 5 mock hands end-to-end

   ```bash
   npm test -- game-engine.integration.test.ts
   ```

4. **GamePhaseOrchestrator** (state machine)
   - Preflop → Flop → Turn → River → Showdown
   - Blinds, betting rounds, dealer rotation
   - Calls GameEngine to apply actions
   - Mock LLM decisions with hard-coded fallbacks

5. **GameLoopController** (timing & lifecycle)
   - setInterval tick at 1 Hz (1 game action per second, tuned later)
   - start() / stop() methods
   - Tracks running state
   - Test: manually verify 10-second game plays to completion

**Acceptance criteria:**
- Unit tests for PokerMathEngine (100% coverage)
- Integration test: 4 mock players → game → showdown → correct winner
- No database required yet
- No LLM calls
- No real-time streaming

**Output:** Runnable `npm run game-demo` that prints game flow to console

---

### Phase 2: Real-Time Broadcast Layer (Weeks 2-3)

**Goal:** Game updates visible in real-time to multiple viewers via SSE.

**Build in order:**

1. **BroadcastEventBus** (EventEmitter wrapper)
   - Central pub/sub for game state changes
   - Simple: `gameEngine.on('stateUpdated', (state) => { ... })`
   - Test: emit event → verify listener called

2. **SSEConnectionManager**
   - Accept GET `/api/games/:id/sse` requests
   - Store active connections in Set
   - Broadcast state to all connections
   - Test: open 2 connections → emit event → both receive message

3. **ViewerPresenceManager**
   - Tracks connected viewers
   - Calls `gameController.start()` when count 0 → 1
   - Calls `gameController.stop()` when count 1 → 0
   - Test: connect viewer → game starts; disconnect → game stops

4. **StateDeltaEncoder** (optimization, optional for MVP)
   - Compute minimal diffs between states
   - Reduce bandwidth (send only changed fields)
   - Can defer to Phase 3 if bandwidth isn't a concern

5. **Redis integration** (transient state storage)
   - Store current game in `game:{gameId}` key with 24h TTL
   - Persist across process crashes (graceful restart)
   - Test: game in progress → kill server → restart → game resumes

6. **Next.js API routes** (HTTP interfaces)
   - POST `/api/games/create` → creates Redis entry, starts loop
   - GET `/api/games/:id/state` → snapshot read
   - GET `/api/games/:id/sse` → stream updates
   - POST `/api/games/:id/bet` → record viewer prediction

**Acceptance criteria:**
- Open frontend → SSE connects → updates arrive every 1s
- Viewer count displayed and updates live
- Open 3 browsers → all see same game state in real-time
- Close all browsers → game stops

**Output:** Live demo with frontend rendering real game state via SSE

---

### Phase 3: LLM Integration (Weeks 3-4)

**Goal:** Real AI decisions via 4 LLM APIs with streaming reasoning.

**Build in order:**

1. **LLMClients** (wrapper for each API)
   - `OpenAIClient.call(prompt)` → stream tokens
   - `GoogleClient.call(prompt)` → stream tokens
   - `AnthropicClient.call(prompt)` → stream tokens
   - `LlamaClient.call(prompt)` → stream tokens (local or API)
   - Each client handles auth, retry, timeout
   - Test: call each API → verify streaming works

2. **ArchetypeEngine** (personality injection)
   - Define archetypes: `Aggressive`, `Conservative`, `Paranoid`, `Chaotic`
   - Map archetype → prompt modifications (bias language)
   - Example: Aggressive gets "you're winning, bet big" in prompt
   - Test: same game state → 4 archetypes → 4 different decisions

3. **LLMOrchestrator** (sequential orchestration)
   - Calls LLM clients sequentially (current project design)
   - Handles timeouts (8-12s per call)
   - Aggregates decisions
   - Broadcasts reasoning in real-time to ReasoningPanel
   - Test: mock game → all 4 LLMs called → decisions parsed

4. **Decision Aggregation** (resolve conflicts)
   - 4 LLMs may suggest different actions
   - Apply archetype-aware bias weights
   - Majority vote or weighted average
   - Fallback to conservative action if tie
   - Test: 3 fold, 1 call → player folds (majority)

5. **Integration with GamePhaseOrchestrator**
   - Call LLMOrchestrator at decision points
   - Apply returned action to game state
   - Continue to next player or next phase
   - Test: full game with all 4 real LLMs

**Acceptance criteria:**
- Live game visible in frontend
- Reasoning panel shows streaming text from each LLM
- All 4 LLM decisions visible per player action
- Game completes with correct winner determination
- LLM timeouts handled gracefully (fallback action)

**Output:** Fully functional LLM Poker Arena (MVP)

---

### Phase 4: Persistence & Analytics (Weeks 4-5)

**Goal:** Game history, replay, viewer betting, leaderboards.

**Build in order:**

1. **Database schema** (PostgreSQL)
   - `games`, `game_phases`, `player_decisions`, `viewer_bets`
   - See Storage Requirements section above

2. **Persistor** (async database writes)
   - Log game outcome (winner, pot, timestamp)
   - Log each phase state (for replay)
   - Log each decision (for analytics)
   - Fire-and-forget async writes (don't block game loop)

3. **Replay functionality**
   - Read game phases from database
   - Replay game state frame-by-frame in frontend
   - Frontend UI: "Watch Game #42" → step through phases

4. **Viewer betting resolution**
   - After showdown: check `viewer_bets` table
   - Mark correct predictions
   - Compute leaderboard (% correct, points, etc.)
   - Display results to viewers

5. **Analytics dashboard** (optional for MVP)
   - Most frequent archetypes
   - Win rate by archetype
   - Average pot size
   - Viewer engagement (peak count, duration)
   - Accessible via GET `/api/stats`

**Acceptance criteria:**
- Game completes → recorded in PostgreSQL
- Viewer betting resolved correctly
- Replay functionality works
- Stats dashboard shows historical trends

**Output:** Historical game data accessible, viewers can see betting results

---

### Phase 5: Scale & Optimization (Weeks 5+)

**Goal:** Handle 10+ concurrent games, thousands of viewers per game.

**Only after MVP is stable. Focus:**

1. **Parallel orchestration** (if budget allows)
   - Call 4 LLMs in parallel instead of sequentially
   - Reduces per-decision time: 12s + 12s + 12s + 8s = 44s → 12s
   - Increases cost (4x LLM calls/second simultaneously)

2. **Worker process** (if in-process crashes web server)
   - Move game engine to separate process
   - Communicate via Redis pub/sub
   - Isolate game crashes

3. **Clustering** (multiple games simultaneously)
   - Redis Streams for game state snapshots
   - Queue system (BullMQ) for game sequencing
   - Load balance multiple game instances

4. **Caching** (reduce database queries)
   - Cache leaderboards in Redis (5-minute TTL)
   - Cache stats in PostgreSQL MATERIALIZED VIEW

---

## Architectural Patterns to Implement

### 1. Command Pattern (Player Actions)

```typescript
interface Command {
  execute(): void
  undo(): void
}

class FoldCommand implements Command {
  constructor(private player: Player, private pot: Pot) {}
  execute() { this.player.fold() }
  undo() { this.player.unfold() }
}
```

### 2. Observer Pattern (State Broadcast)

```typescript
gameEngine.on('stateUpdated', (state) => {
  broadcastEventBus.emit('stateUpdated', state)
  persistor.logStateChange(state)
  stateDeltaEncoder.encode(state)
})
```

### 3. State Machine (Phase Transitions)

```typescript
// Use a library like Machina or hand-rolled FSM
const phaseMachine = {
  preflop: { next: 'flop', condition: 'allPlayersActed' },
  flop: { next: 'turn', condition: 'allPlayersActed' },
  turn: { next: 'river', condition: 'allPlayersActed' },
  river: { next: 'showdown', condition: 'allPlayersActed' },
}
```

### 4. Strategy Pattern (Archetype Behavior)

```typescript
interface ArchetypeStrategy {
  biasPrompt(context: DecisionContext): string
  scoreAction(action: Action, context: DecisionContext): number
}

class AggressiveArchetype implements ArchetypeStrategy {
  biasPrompt(context) { return "You're in a strong position. Bet big!" }
  scoreAction(action) {
    return action === 'raise' ? 1.5 : action === 'call' ? 1.0 : 0.5
  }
}
```

### 5. Singleton Pattern (Game Instance)

```typescript
// Initialize once at server startup
export const gameEngine = new GameEngine()
export const broadcastBus = new EventEmitter()
export const sseManager = new SSEConnectionManager()

// All routes access the same instance
export async function GET(req) {
  return sseManager.getStream(req)
}
```

---

## Key Architectural Decisions & Rationale

| Decision | Trade-off | Why |
|----------|-----------|-----|
| **In-process singleton** (start) vs Worker (later) | Simplicity vs isolation | VPS can handle single process; worker adds complexity until crash issues appear |
| **Redis for game state** | Memory cost vs speed | Game loop needs sub-ms latency; PostgreSQL too slow |
| **Sequential LLM calls** | Speed vs cost | Budget-conscious; parallel costs 4x API spend; can optimize later |
| **SSE over WebSocket** | Latency vs simplicity | WebSocket adds infrastructure; SSE sufficient for 1-2 second updates; no binary support needed |
| **Async database writes** | Consistency vs performance | Game loop can't block on I/O; writes to database eventual, acceptable for analytics/replay |
| **Stateless API routes** (SSE, queries only) | Coupling vs decoupling | Separates request handling from game logic; game engine is single source of truth |
| **Event-driven architecture** | Memory overhead vs flexibility | Observer pattern lets viewers, database, and replay all hook in without game knowing about them |
| **PostgreSQL for history** | Schema management vs flexibility | Structured game records enable analytics, replays; JSONB for flexibility in decisions/state |

---

## Sources

- [Node.js SSE Implementation Guide (2026)](https://1xapi.com/blog/implement-server-sent-events-sse-nodejs-2026)
- [Building Real-Time Viewer Counter with SSE (Medium, Mar 2026)](https://medium.com/@iamamitgupta10/how-sites-like-booking-com-show-245-people-are-viewing-this-property-right-now-a645bf67af30)
- [Game Server Architecture Basics](https://techtidesolutions.com/blog/game-server-architecture-basics/)
- [Node.js Event Emitter Documentation](https://nodejs.org/api/events.html)
- [Node.js EventEmitter Best Practices (2026)](https://oneuptime.com/blog/post/2026-02-03-nodejs-eventemitter/view)
- [How to Implement Game State Management with Redis](https://oneuptime.com/blog/post/2026-01-21-redis-game-state-management/view)
- [Redis Persistence Options](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
- [API Timeout Handling for LLM Applications](https://markaicode.com/api-timeout-handling-llm-applications/)
- [Orchestration Frameworks Comparison (2026)](https://www.sitepoint.com/agent-orchestration-framework-comparison-2026/)
- [Poker Hand Evaluation Algorithm (GitHub)](https://github.com/HenryRLee/PokerHandEvaluator)
- [Next.js Background Jobs & PostgreSQL (2026)](https://render.com/articles/nextjs-background-jobs-postgresql-production)
- [State Machines in JavaScript (Smashing Magazine)](https://www.smashingmagazine.com/2018/01/rise-state-machines/)
