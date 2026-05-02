# Domain Pitfalls: LLM Poker Arena with Real-Time Broadcast

**Domain:** Live AI poker spectator arena with SSE streaming  
**Researched:** 2026-05-01  
**Confidence:** MEDIUM-HIGH (verified against official docs, production patterns, and ecosystem experience)

---

## Critical Pitfalls (Project-Breaking)

These mistakes cause rewrites, data loss, financial harm, or complete feature failure.

### Pitfall 1: LLM API Cost Spiral Without Demand Gating

**What goes wrong:**
The project runs games continuously or responds to spurious requests, burning through LLM API budgets at exponential rates. A single silent retry loop (e.g., malformed JSON responses from LLM, network timeouts triggering automatic retries without budget awareness) can inflate monthly bills 40%+ month-over-month with zero new users.

**Why it happens:**
- Games are triggered without validating viewer presence
- Retry logic fires immediately without jitter, hitting overloaded endpoints repeatedly
- No global deadline or budget ceiling enforces a maximum spend per session/game
- Retry loops are decoupled from failure budgets—a stuck loop can burn thousands in minutes

**Consequences:**
- Unbounded financial liability (five-figure bills discovered after-the-fact)
- Service shutdown due to budget exhaustion mid-game
- Competitive models (Claude, GPT-4o, Gemini, Llama) cost imbalance causes one to spiral alone

**Prevention:**
1. **Mandatory viewer presence check** before game start: only run games when `viewerCount >= 1`
2. **Session-level budget cap**: Track cumulative token spend per game session; return 429 and halt when ceiling is hit (recommend $5-$10 per game based on 4 LLM calls × ~1500 tokens each)
3. **Per-request timeout budget**: Global 8-second deadline allocated across all 4 LLM calls (e.g., 2 sec per call with jitter)
4. **Circuit breaker per model**: If a model's spend rate exceeds 3x its trailing 7-day average in 15-minute window, auto-throttle to 1 request/second and alert
5. **Gateway-enforced cost routing**: Never let game code check budgets—enforce via API gateway before forwarding requests (malicious/buggy code cannot skip checks)
6. **Monthly hard ceiling per model**: Set spend cap on each API key; once breached, fallback to cheaper model or disable that player

**Detection:**
- Exponential cost growth with flat user count
- Repeated identical LLM errors in logs (malformed JSON, token limit exceeded)
- Retry counts > 3 for single request
- Any game running > 10 minutes (should be ~3 mins)

**Sources:**
- [LLM Budget Management — Stop Runaway AI Costs](https://aisecuritygateway.ai/docs/llm-budget-enforcement)
- [Agent Runaway Costs: How to Set LLM Budget Limits](https://relayplane.com/blog/agent-runaway-costs-2026)

---

### Pitfall 2: SSE Connection Drops & Proxy Buffering on VPS

**What goes wrong:**
30-40% of spectators experience 20+ second delays or missed game state updates. Events are buffered by corporate firewalls, load balancers, or intermediate proxies until connection closes. Clients think they're watching live, but are actually watching a 30-second tape delay. When network instability causes reconnects, some clients miss flop/turn updates entirely.

**Why it happens:**
- SSE uses streaming without Content-Length header, so proxies interpret it as indefinite data flow
- Network proxies (especially corporate, legacy infrastructure) buffer packets and don't flush until connection terminates
- The HTTP spec allows proxies to legally buffer indefinitely—no headers can force immediate flush
- No fallback handshake to verify data was received; server assumes client got it
- Default browser retry is 3 seconds, but network may take 15+ seconds to detect drop

**Consequences:**
- Spectators see delayed/frozen game state ("why is the action still on player 1?")
- Missed state transitions (flop never appears, goes straight to turn)
- Incorrect bet amounts (player sees old pot value)
- Player reasoning doesn't sync with visible action (client sees fold but hearing reasoning about betting)
- Users think product is broken and leave

**Prevention:**
1. **Disable buffering on VPS proxy layer**: Add `X-Accel-Buffering: no` header in SSE responses (for Nginx)
2. **Heartbeat every 5 seconds**: Send a `:` heartbeat comment to force proxy flush and detect dead connections early
3. **Message IDs for replay**: Tag every state update with monotonic `id: N` so reconnecting clients can request missed events from server cache
4. **Acknowledgment-based validation**: Client sends back HTTP POST confirming last received message ID; if server doesn't receive ACK after 2 heartbeats, force reconnect
5. **Connection timeout detection**: If no events sent for 10+ seconds, proactively close and let client auto-reconnect with backoff
6. **Client-side replay buffer**: Keep last 10 state snapshots in memory; on reconnect, detect gaps and fetch missing states via `/api/game/state/since/{lastMessageId}`

**Detection:**
- Client lag reports (spectator says "action is delayed" in feedback)
- Discrepancy between server's `sentAt` timestamp and client's `receivedAt` timestamp > 5 seconds
- SSE connection stays open but no events received for 10+ seconds
- Monitor browser console for SSE reconnect count > 1 per game

**Sources:**
- [Server Sent Events not production ready after a decade](https://dev.to/miketalbot/server-sent-events-are-still-not-production-ready-after-a-decade-a-lesson-for-me-a-warning-for-you-2gie)
- [The Hidden Risks of SSE (Server-Sent Events)](https://medium.com/@2957607810/the-hidden-risks-of-sse-server-sent-events-what-developers-often-overlook-14221a4b3bfe)
- [Optimizing Server-Sent Events Resilience](https://ithy.com/article/sse-connection-resilience-qwo3x8pb)

---

### Pitfall 3: Race Conditions in Concurrent Game State Updates

**What goes wrong:**
Two SSE writes fire simultaneously (e.g., one from "player action" thread, one from "betting calculation" thread). Game state corrupts: pot is calculated twice, player chip count goes negative, or turn card appears alongside flop events. Different clients see inconsistent state.

**Why it happens:**
- Multiple async tasks write to shared `gameState` object without synchronization
- Node.js event loop is single-threaded but async I/O can interleave: while SSE write#1 is flushing, write#2 reads stale pot value and calculates off it
- Easy to miss: "single-threaded event loop" feels safe until you call two async functions simultaneously
- LLM API calls for 4 players happen in parallel; if reasoning parsing and state update aren't atomic, inconsistency emerges

**Consequences:**
- Spectators see invalid game state (negative chips, duplicate cards, impossible pot)
- Showdown logic breaks (wrong hand evaluation due to corrupted state)
- Replay is unplayable (state rewind finds inconsistency, player count wrong mid-game)
- Audit logs show events out of order or duplicated

**Prevention:**
1. **Single event channel for all state writes**: All mutations go through one controlled function, never direct property assignment
2. **Atomic state snapshots**: Before writing to SSE, snapshot entire `gameState` object; write snapshot, not live reference (prevents in-flight mutations)
3. **Message queue with serial processing**: Queue all state-change requests (action, bet, flop reveal) and process one at a time; next request waits for previous SSE write to complete
4. **Explicit write locks**: Use a simple mutex or semaphore (even a boolean flag with async/await) to ensure only one SSE write is in flight at a time
5. **Validation before broadcast**: After every state mutation, run validation (pot == sum of bets, hand count == 2, etc.); log violation and revert if invalid

**Detection:**
- Assertion failures in validation (pot mismatch, chip count negative)
- Event audit log shows duplicated or out-of-order events
- Spectator reports inconsistency (e.g., "player X folded but still in hand")
- Showdown hand evaluation doesn't match prior betting decisions

**Sources:**
- [Race Conditions in Concurrent Systems](https://medium.com/@arunseetharaman/race-conditions-the-silent-threat-in-concurrent-systems-11c440bd115d)
- [Architecture of Node.js Multiplayer Game](https://medium.com/@MichalMecinski/architecture-of-a-node-js-multiplayer-game-a9365356cb9)

---

### Pitfall 4: LLM API Timeout / Garbage Response Mid-Game

**What goes wrong:**
One of 4 LLM calls times out or returns unparseable JSON during a critical decision (e.g., turn action). Game halts, times out waiting, or proceeds with missing player reasoning. Entire game becomes invalid.

**Why it happens:**
- OpenAI, Google, Anthropic APIs operate at ~99.5% uptime (3.5 days downtime/year); outages happen without warning
- A single timeout isn't retried with backoff + jitter; loop fires immediately, hammering the already-overloaded endpoint
- No fallback plan if Claude is unreachable—game can't auto-degrade to Llama
- LLM returns valid JSON but with malformed game logic (e.g., "fold" and "raise" in same decision) — code doesn't validate action schema
- Timeout is global (8 seconds for entire game turn); if one call takes 6 seconds, others starve

**Consequences:**
- 15-30 second spectator stall mid-game (looks frozen)
- Game skips a player's action or decides for them (unfair)
- Reasoning panel shows "ERROR" or blank, undermines product trust
- Logs fill with retry noise; hard to debug actual issue

**Prevention:**
1. **Per-call timeout budget with global deadline**: Allocate 2-second ceiling per LLM call; track total time; if global deadline approaches, cancel remaining calls and use fallback
2. **Graceful degradation**: If Claude times out, immediately retry with Llama at 50% temperature (faster, more decisive). If both fail, use hand-strength formula to auto-decide (fold weak hand, raise strong hand)
3. **Circuit breaker per provider**: Track failure rate per model; if failure rate > 10% in 1-minute window, auto-fallback to different model for next game
4. **Schema validation before game logic**: Parse LLM response, validate action key, amount, reasoning text; reject and re-request if malformed
5. **Timeout-safe defaults**: If all 4 calls fail, game runs with deterministic fallback policy (e.g., "aggressive archetype always raises, passive always checks")

**Detection:**
- LLM call latency > 3 seconds (indicates degradation)
- Error rate per provider > 5% per game
- Any timeout count > 0 per game
- Spectator sees blank reasoning panel or "ERROR" message

**Sources:**
- [LLM API Resilience in Production: Rate Limits, Failover](https://tianpan.co/blog/2026-03-11-llm-api-resilience-production)
- [Retries, Fallbacks, and Circuit Breakers in LLM Apps](https://portkey.ai/blog/retries-fallbacks-and-circuit-breakers-in-llm-apps/)

---

## Common Bugs (Require Fixes, Not Rewrites)

These mistakes are frequent, cause UX issues or logic errors, but don't crash the system entirely.

### Bug 1: Poker Hand Evaluation Mistakes

**What goes wrong:**
- Kicker comparison done wrong: two players with pair of queens, one has K-J-9 kickers, other has K-Q-9—code compares suits instead of ranks, declares wrong winner
- Flush vs straight flush: code evaluates flush strength but misses that there's a straight flush available from the hand, ranks incorrectly
- Split pot logic: two players with identical final 5-card hand, code doesn't split pot evenly or awards both pot instead of half each
- Counterfeiting: player hole cards are A-K, board is A-K-2-3-4, code still uses hole card kickers even though board kickers now play—player thinks they have top pair with K-J, actually has 5-kicker

**Why it happens:**
- Poker hand evaluation is deceptively complex; 7-card evaluation (2 hole + 5 board) requires checking all 21 possible 5-card combos and selecting best
- Easy to hard-code suit logic or forget that board often "counterfeits" hole card kickers
- Insufficient test coverage for edge cases (flush on board vs in hand, pairs at different card ranks)

**Prevention:**
1. **Use a peer-reviewed poker library**: Don't write hand evaluation from scratch—use [poker-evaluator](https://github.com/chenh1/poker-evaluator) or similar with thousands of test cases
2. **Comprehensive test suite**: At minimum, test all 9 hand ranks + split pots + counterfeiting. Test kicker ordering (K-J-9 vs K-Q-9 vs K-J-T)
3. **Validation against known hands**: Create 100 real poker scenarios, evaluate with code and real poker rules, assert match
4. **Code review by poker player**: Have someone who understands poker kickers review hand evaluation logic

**Detection:**
- Spectator bet histograms show winners with weaker hands than losers (statistically impossible)
- Specific hand types (flush-heavy, split pot scenarios) have wrong outcome frequency
- Replay analysis shows hand that should win getting second place

---

### Bug 2: Archetype Bias Decay (AI Becomes Mechanical)

**What goes wrong:**
After 20-30 games, Claude and GPT-4o become mechanical and repetitive despite personality archetype assignment. Reasoning panel shows same phrases ("I'm analyzing pot odds", "let me evaluate my hand"), betting becomes predictable (always min-raise, always check after flop). LLM reasoning degrades into obvious token-catcher patterns.

**Why it happens:**
- Context window for entire game session grows to 50K+ tokens (game history + all reasoning + all board states)
- Each response token becomes more likely to repeat previous patterns (token context includes self)
- Parameter tweaks (presence_penalty, frequency_penalty) show "zero to negative effect" in practice—not the real cause
- Archetype prompt doesn't override natural LLM tendency to minimize output variance

**Consequences:**
- Spectator comments: "poker is boring now, same decisions every game"
- Viewers stop tuning in after 30 minutes (expected 2+ hour engagement)
- Product feels less like "AI plays poker" and more like "deterministic algo with LLM flavor"

**Prevention:**
1. **Prompt engineering over parameters**: Reduce archetype prompt to ~60 lines max (lean, natural language), eliminate numbered lists and tables (train repetition). Include explicit line: "State each decision only once; never repeat your reasoning."
2. **Fresh context per game**: Discard prior game session context entirely; start with only current game state, not prior game decisions
3. **Inject controlled randomness in reasoning format**: Vary phrasing ("I'm thinking...", "My assessment is...", "Here's my logic...") via prompt variants, not code
4. **Monitor output diversity**: Track unique tokens per reasoning output; if falls below threshold (50 unique tokens from 100 generated), force re-prompt with "write differently" instruction
5. **Seasonal archetype rotation**: Every 10 games, swap archetypes (aggressive player becomes conservative) to force fresh decision patterns

**Detection:**
- Reasoning output word frequency distribution skewed (top 10 words comprise >30% of output)
- Spectator feedback mentions "repetitive", "boring", "predictable"
- Same action decisions in structurally identical board situations (e.g., always raises with 55% win probability)

**Sources:**
- [We Reduced LLM Repetition from 15% to 0%](https://tonyseah.medium.com/we-reduced-llm-repetition-from-15-to-0-and-parameter-tuning-wasnt-the-answer-e1a1cd811c3c)
- [Antislop Framework for LLM Output Quality](https://liner.com/review/antislop-a-comprehensive-framework-for-identifying-and-eliminating-repetitive-patterns)

---

### Bug 3: Memory Leaks in Long-Running Game Loop

**What goes wrong:**
After 200-300 games, Node.js process memory climbs from 120MB to 500MB+ without dropping. Garbage collector runs less frequently. Game loop gets sluggish. Eventually OOM kill or slowdown stops new games.

**Why it happens:**
- Event listeners for each game never unsubscribed: SSE close handlers don't clean up old listeners, so every new player connection adds unreleased handler
- Timers (setInterval for game turns, timeouts for LLM call deadlines) accumulate without clearInterval—callbacks hold closures referencing prior game state
- Global game history array keeps every game object in memory (for replay)—objects have circular references that GC can't trace
- Closures in callbacks retain entire scope: LLM response handler closes over `gameState`, `players`, `bettingRound`—even after game ends, these objects stay reachable

**Consequences:**
- Spectators experience 500ms+ latency per action after 4+ hours of games (GC pauses)
- Process restarts required every 8 hours (DevOps burden)
- OOM crashes mid-game, interrupting live broadcast

**Prevention:**
1. **Explicit listener cleanup**: When game ends, call `emitter.removeAllListeners()` and `eventSource.close()` for all connected clients
2. **Timer management**: Keep array of `timerId` from setInterval/setTimeout; on game end, `timerId.forEach(id => clearInterval(id))`
3. **Bounded history**: Keep only last 100 games in memory; archive older to disk/DB; delete objects when purged from history
4. **Destructure in closures**: In LLM callback, extract only needed fields (`const { id, turn } = gameState`) instead of capturing whole object
5. **WeakMap for internal caches**: If caching player stats, use WeakMap so players can be GC'd when game ends

**Detection:**
- Heap growth > 10MB per 50 games (should be flat)
- Action latency increases with uptime (p99 latency creep)
- Spectator-visible lag: reasoning panel updates slowly, action delays by 200ms+
- `node --trace-gc` shows GC pause duration increasing over time

**Sources:**
- [Preventing and Debugging Memory Leaks in Node.js](https://betterstack.com/community/guides/scaling-nodejs/high-performance-nodejs/nodejs-memory-leaks/)
- [How to Avoid Memory Leaks in JavaScript Event Listeners](https://dev.to/alex_aslam/how-to-avoid-memory-leaks-in-javascript-event-listeners-4hna)

---

## Deployment-Specific Pitfalls

### Pitfall: SSE on Vercel vs. VPS

**What goes wrong:**
Product works in dev (local Node.js), breaks on Vercel free tier (10-second timeout cuts off SSE stream mid-game), works fine on VPS.

**Why it happens:**
- Vercel serverless functions timeout after 10 seconds (free tier), 60 seconds (Pro)
- Each SSE connection consumes a serverless function instance; exceed concurrency quota and new clients get 429
- Caching enabled by default; route gets statically optimized despite `dynamic = "force-dynamic"`
- VPS runs persistent Node.js process; handles unlimited concurrent SSE connections

**Consequences (Vercel scenario):**
- Spectators disconnect after 10 seconds
- Rendering shows frozen state, no updates for 5+ seconds before disconnect
- Scaling fails: 1000 concurrent viewers = 1000 function instances (expensive or rate-limited)

**Prevention:**
1. **Deploy to VPS, not Vercel/serverless**: Your architecture is persistent SSE + game loop; serverless is wrong deployment target
2. **Test SSE on VPS early**: Don't assume "it's just HTTP streaming" works the same way
3. **If Vercel required**: Use WebSocket instead of SSE (works within timeout), or accept 10-second viewport (not suitable for real-time poker)

**Detection:**
- Spectator disconnect after exactly 10, 30, or 60 seconds (Vercel timeout boundaries)
- Error logs show "function timeout" or "process killed"
- Works locally but fails on prod

**Sources:**
- [Server-Sent Events don't work in Next.js API routes](https://github.com/vercel/next.js/discussions/48427)
- [Can SSE be implemented with only Next.js API routes?](https://community.vercel.com/t/can-sse-be-implemented-with-only-next-js-api-routes/11063)
- [Next.js SSE Guide: Real-Time Apps (2026)](https://nextjslaunchpad.com/article/nextjs-server-sent-events-real-time-notifications-progress-tracking-live-dashboards)

---

## Phase Mapping

| Pitfall | Phase | Reason | Action |
|---------|-------|--------|--------|
| LLM Cost Spiral | Phase 2 (Game Loop) | Must implement before first LLM call | Enforce viewer gating, session budgets, circuit breakers |
| SSE Proxy Buffering | Phase 3 (Real-Time Sync) | Must implement before spectators see live games | Add heartbeat, message IDs, buffering headers |
| Race Conditions | Phase 2 (Game Loop) | Emerges with concurrent LLM + betting logic | Implement state lock, atomic snapshots, validation |
| LLM Timeout Fallback | Phase 2 (Game Loop) | Must handle from first game | Add per-call timeout, fallback chains, circuit breaker |
| Poker Hand Bugs | Phase 1 (Rules Engine) | Foundation for all game logic | Use peer-reviewed library, test 9 hand ranks + splits |
| Archetype Decay | Phase 4 (Reasoning Polish) | After game loop stable, optimize quality | Refactor prompts, rotate archetypes, monitor diversity |
| Memory Leaks | Phase 2-3 (Monitoring) | Emerges after 50+ games, catch early | Instrument GC, test 300-game runs, cleanup listeners |
| Vercel SSE Timeout | Phase 3 (Deployment) | Discovered during infra decision | Commit to VPS from day 1, not serverless |

---

## Warning Signs (Detect Problems Early)

| Problem | Early Warning Sign | When It Appears |
|---------|-------------------|-----------------|
| Cost spiral | Any LLM call > 3 sec; 2nd retry on same request | First 5 games with network issues |
| SSE buffering | Spectators report 20+ sec delays; client-side timestamp delta > 5 sec | First large viewer spike (100+ users) |
| Race conditions | Assertion failure in state validation; duplicate events in audit log | First concurrent game + 4-player decisions |
| LLM timeout | Timeout count > 0 in logs; blank reasoning panel | First 10 games; any API degradation event |
| Hand eval bug | Winner has weaker hand than loser; split pot isn't 50/50 | First poker game if using wrong logic |
| Output decay | Same tokens appear in 3+ consecutive reasoning outputs; spectator feedback "boring" | After 20 games |
| Memory leak | Heap size increases monotonically; action latency creeps +50ms/hour; GC pause > 100ms | After 100 games at constant load |
| Vercel timeout | Disconnect exactly at 10s or 60s boundary; error log shows timeout | First deployment to Vercel |

---

## References

**LLM Cost & Reliability:**
- [LLM Budget Management — Stop Runaway AI Costs](https://aisecuritygateway.ai/docs/llm-budget-enforcement)
- [Agent Runaway Costs: How to Set LLM Budget Limits](https://relayplane.com/blog/agent-runaway-costs-2026)
- [LLM API Resilience in Production](https://tianpan.co/blog/2026-03-11-llm-api-resilience-production)
- [Retries, Fallbacks, and Circuit Breakers in LLM Apps](https://portkey.ai/blog/retries-fallbacks-and-circuit-breakers-in-llm-apps/)

**SSE & Real-Time:**
- [Server Sent Events not production ready after a decade](https://dev.to/miketalbot/server-sent-events-are-still-not-production-ready-after-a-decade-a-lesson-for-me-a-warning-for-you-2gie)
- [The Hidden Risks of SSE](https://medium.com/@2957607810/the-hidden-risks-of-sse-server-sent-events-what-developers-often-overlook-14221a4b3bfe)
- [Optimizing Server-Sent Events Resilience](https://ithy.com/article/sse-connection-resilience-qwo3x8pb)

**Concurrency & Architecture:**
- [Race Conditions in Concurrent Systems](https://medium.com/@arunseetharaman/race-conditions-the-silent-threat-in-concurrent-systems-11c440bd115d)
- [Architecture of Node.js Multiplayer Game](https://medium.com/@MichalMecinski/architecture-of-a-node-js-multiplayer-game-a9365356cb9)

**Memory & Performance:**
- [Preventing Memory Leaks in Node.js](https://betterstack.com/community/guides/scaling-nodejs/high-performance-nodejs/nodejs-memory-leaks/)
- [How to Avoid Memory Leaks in Event Listeners](https://dev.to/alex_aslam/how-to-avoid-memory-leaks-in-javascript-event-listeners-4hna)

**LLM Output Quality:**
- [We Reduced LLM Repetition from 15% to 0%](https://tonyseah.medium.com/we-reduced-llm-repetition-from-15-to-0-and-parameter-tuning-wasnt-the-answer-e1a1cd811c3c)
- [Antislop Framework for LLM Repetition](https://liner.com/review/antislop-a-comprehensive-framework-for-identifying-and-eliminating-repetitive-patterns)

**Poker Rules & Hand Evaluation:**
- [Poker Kicker Rules & Tiebreaker Logic](https://pokerati.com/2025/10/poker-kicker-what-is-it-and-when-does-it-matter/)
- [Poker Hands Ranked Chart & Tiebreakers](https://www.pokernews.com/poker-hands/tied-poker-hands.htm)

**Next.js & Vercel Gotchas:**
- [Server-Sent Events in Next.js API routes](https://github.com/vercel/next.js/discussions/48427)
- [Next.js SSE Guide (2026)](https://nextjslaunchpad.com/article/nextjs-server-sent-events-real-time-notifications-progress-tracking-live-dashboards)
