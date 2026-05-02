# Features Research — LLM Poker Arena

**Project:** LLM Poker Arena (AI vs AI live spectator product)  
**Researched:** 2026-05-01  
**Research Mode:** Ecosystem + Feasibility  
**Overall Confidence:** HIGH (Texas Hold'em rules verified from multiple sources; spectator engagement patterns from established products; personality parameterization from academic frameworks)

---

## Table Stakes (Must Have)

Features spectators expect from a live card game spectator product. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Status |
|---------|--------------|------------|--------|
| **Correct Texas Hold'em rule enforcement** | Core game legitimacy — wrong rules break the experience | Medium | Validated (Project.md) |
| **Visible community cards** | Standard UI expectation from every card game viewer | Low | Validated (Game.tsx in codebase) |
| **Player chip counts and hole cards** | Poker spectating 101 — viewers must track game state | Low | Validated (PlayerSeat components exist) |
| **4 betting rounds (pre-flop, flop, turn, river)** | Fundamental poker structure spectators know | Medium | Validated (Project.md) |
| **Hand strength evaluation on demand** | Viewers want to understand who's ahead/behind | Medium | Validated (Project.md requires "math engine") |
| **Showdown with hand comparison** | Without this, poker has no climax | Medium | Must implement |
| **Real-time updates for all viewers** | "Shared game state" — all spectators see same game simultaneously | Medium | Validated (SSE infrastructure required) |
| **Live viewer count** | Creates social proof and FOMO | Low | Validated (Project.md) |
| **AI reasoning visible per phase** | Core value: transparent AI thinking | Low | Validated (ReasoningPanel component exists) |
| **Game only runs when viewers present** | Budget constraint, prevents idle API calls | Medium | Validated (Project.md: "demand-triggered game loop") |

---

## Differentiators

Competitive advantages that set this product apart from other spectator experiences. Not expected, but highly valued.

| Feature | Value Proposition | Complexity | Why Matters |
|---------|-------------------|------------|------------|
| **Personality-driven AI behavior (archetypes)** | Each AI plays with distinct character (aggressive, paranoid, conservative, chaotic) rather than optimal math. Creates drama and replayability. | High | Makes the same game feel different every session. Viewers invest in "will aggressive Claude bluff again?" narratives. |
| **Per-phase LLM reasoning narration** | Players explain their thinking at each decision point — not just cold probabilities. | High | Creates transparency AND entertainment. Users feel they're watching "real minds" not algorithms. Unprecedented in poker streaming. |
| **Randomly assigned archetypes per game** | AI personality type is randomized, so Gemini might be paranoid today, chaotic tomorrow. | Low | Prevents metagaming. Forces viewers to rediscover AI personalities each session. Drives rewatch value. |
| **Viewer predictions without real money** | Anonymous users pick winners before showdown; results shown after. Purely for bragging rights. | Low | Engages passive viewers into active participation. No financial risk = broader audience. Streak/leaderboard mechanics proven in sports prediction apps. |
| **Dramatic reveal of reasoning** | AI narration is paced to build tension (slow reveal of doubt, sudden conviction, strategic pivots). | Medium | Transforms "thinking" from boring text dump into narrative tension. Critical for streaming engagement. |
| **Personality archetype transparency** | Show viewers which archetype each AI was assigned, so they understand WHY it's playing that way. | Low | Viewers become invested in the AI character, not just the game. Creates parasocial connection. |
| **Hand strength visualization** | Real-time chart/bar showing each player's win probability vs. pot odds (not narrated by AI, computed programmatically). | Medium | Makes the invisible (probabilities) visible. Helps viewers learn while watching. |
| **Idle state UI (when no viewers)** | When nobody's watching, show a "waiting for spectators" screen or minimal idle animation instead of blank screen. | Low | Creates psychological readiness for streams to start when viewers arrive. Small UX touch with big engagement impact. |
| **Configurable game-start schedule + viewer presence** | Games start on a fixed schedule (e.g., every 30 min) IF viewers are present, OR immediately when first viewer arrives. Hybrid mode = predictability + responsiveness. | Low | Viewers can plan when to tune in. Doesn't waste API budget on empty periods. |

---

## Texas Hold'em Rules Checklist

Complete, implementation-ready rule set for correct poker execution. Use this as your canonical rules document.

### Hand Rankings (Highest to Lowest)

**Note:** All hand rankings are evaluated using the best 5-card combination from 7 cards (2 hole + 5 community).

1. **Royal Flush**
   - Description: A-K-Q-J-10, all the same suit
   - Tiebreaker: Cannot be tied (only one exists per suit, player wins outright)
   - Code hint: Straight Flush with A-high

2. **Straight Flush**
   - Description: Five consecutive cards, all same suit (e.g., K-Q-J-T-9 of hearts)
   - Tiebreaker: Highest card of the straight wins (K-high beats Q-high)
   - Code hint: Check sequence + suit match simultaneously

3. **Four of a Kind (Quads)**
   - Description: All four cards of one rank + one kicker (e.g., A-A-A-A-K)
   - Tiebreaker: Higher rank of quads wins. If tied (impossible in single deck), compare kicker.
   - Code hint: rank[i] == 4

4. **Full House**
   - Description: Three cards of one rank + two cards of another rank (e.g., A-A-A-K-K)
   - Tiebreaker: Three-of-a-kind rank decides first. If tied, pair rank breaks tie.
   - Code hint: rank[i] == 3 && rank[j] == 2 (for different i, j)
   - **Kicker rule:** NO kicker. Full house is completely determined by ranks.

5. **Flush**
   - Description: Any five cards of the same suit, not in sequence (e.g., A-J-9-5-3, all spades)
   - Tiebreaker: Compare all five cards from highest to lowest in order (high card, 2nd high, 3rd high, 4th high, 5th high)
   - Code hint: suit[all 5] match; rank sequence doesn't matter

6. **Straight**
   - Description: Five consecutive cards of any suit (e.g., 9-8-7-6-5)
   - Tiebreaker: Highest card of straight wins. Ace can be HIGH (A-K-Q-J-10) or LOW (5-4-3-2-A/"wheel"), never in middle.
   - Code hint: Check for A-2-3-4-5 as special case (Ace = 1 for low straight)
   - **Straight high examples:** K-high beats Q-high beats 5-high (wheel)

7. **Three of a Kind (Trips)**
   - Description: Three cards of one rank + two unrelated kickers (e.g., A-A-A-K-Q)
   - Tiebreaker: Higher rank of trips wins. If tied (impossible), compare kickers in order (high, then 2nd high, then 3rd high).
   - Code hint: rank[i] == 3
   - **Kicker rule:** Use first and second kicker (highest two remaining cards)

8. **Two Pair**
   - Description: Two cards of one rank, two cards of another, + one kicker (e.g., K-K-5-5-A)
   - Tiebreaker: Higher pair wins. If both pairs are tied (impossible), lower pair breaks tie. If both pairs tied (impossible), kicker wins.
   - Code hint: rank[i] == 2 && rank[j] == 2 (i ≠ j)
   - **Kicker rule:** One kicker (the card not part of either pair)

9. **One Pair**
   - Description: Two cards of one rank + three unrelated kickers (e.g., A-A-K-Q-J)
   - Tiebreaker: Higher pair wins. If tied (impossible), compare kickers in order (highest, 2nd, 3rd).
   - Code hint: rank[i] == 2
   - **Kicker rule:** Use all three remaining cards (high, mid, low kicker)

10. **High Card (No Pair)**
    - Description: No hand above. Best five cards by rank alone (e.g., A-K-Q-J-9)
    - Tiebreaker: Compare all five cards from highest to lowest. "Ace high" beats "King high," etc.
    - Code hint: All ranks appear ≤ once
    - **Kicker rule:** All five cards are "kickers" in the sense that all matter for tiebreaking

### Kicker Rules (Critical for Implementation)

**What is a kicker?**
A kicker is any card that's not part of the main hand rank. For example:
- Pair: A-A-K-Q-J → K, Q, J are kickers
- Trips: A-A-A-K-Q → K, Q are kickers
- Full House: A-A-A-K-K → NO kickers (hand is fully determined by ranks)

**Kicker tiebreaking order:**
When two players have the same hand rank (e.g., both have a pair of Aces), compare kickers from HIGHEST to LOWEST.
- Player 1: A-A-K-Q-J
- Player 2: A-A-K-Q-10
- Comparison: A-A (tie), K (tie), Q (tie), J vs. 10 → Player 1 wins

**When kickers don't matter:**
Kickers don't apply if the board already makes a stronger hand. For example:
- Board: A-A-A-K-K (Full house)
- Player 1 hole cards: Q-J
- Player 2 hole cards: 2-3
- Both use the board → SPLIT POT (best 5-card hand is identical)

### Betting Structure (No-Limit Texas Hold'em)

**Blind Posting:**
- Small blind: Half the big blind (posted by player immediately left of dealer button)
- Big blind: Minimum bet amount (posted by player left of small blind)
- Blinds are mandatory antes for the first betting round only
- Example: Small blind = $1, Big blind = $2

**Pre-Flop (First Betting Round):**
1. Dealer button determines acting order
2. Small blind acts first (can call, raise, fold)
3. Big blind acts second
4. Action proceeds clockwise
5. Raises must be at least the size of the previous bet/raise
6. All-in: Player can bet all remaining chips

**Flop (Second Betting Round):**
1. Three community cards revealed
2. Small blind acts first (checks or bets)
3. Big blind acts second
4. Same raise/check/fold rules as pre-flop
5. **First player to act has NO obligation to bet** (can check to pass action)

**Turn (Third Betting Round):**
1. Fourth community card revealed
2. Same acting order and rules as flop
3. **Raise sizing:** Same as pre-flop in No-Limit (minimum bet = big blind; raises = previous bet size)

**River (Fourth Betting Round):**
1. Fifth community card revealed
2. Same acting order and rules as turn
3. Final chance to act before showdown

**All-In Rules (Simplified for v1):**
- Player can push all remaining chips at any point
- All-in bets are handled normally in the pot
- v1: **Skip side pots** — if multiple players all-in, single main pot only
- Showdown: All remaining hands reveal; best hand wins main pot

### Showdown Rules

**Order of revealing:**
1. Last player to make an aggressive action (bet/raise) in river shows first
2. Other players show cards in clockwise order
3. **OR** if nobody bets on river, small blind position shows first

**Hand comparison:**
- Each player makes the best 5-card hand from 2 hole + 5 community
- Highest hand wins pot
- Tied hands: Split pot equally

**Mucking (optional for v1):**
- Players who fold don't need to reveal cards
- Showdown only includes remaining players

---

## Spectator Engagement Patterns

Mechanisms that drive viewer retention and participation without requiring authentication, real money, or accounts.

### Prediction Mechanics

**Winner Prediction (Anonymous, No Stakes)**
- Before final showdown, allow anonymous viewers to predict which player will win
- Implementation: Simple radio button / toggle per player, submit button
- Results reveal after showdown (2-3 second delay for drama)
- Display: "You predicted Player 3, they had K-K. You were RIGHT / WRONG."
- Confidence level: Users should see what % of viewers predicted each player (social proof)
- Why it works: Engages passive viewers into active participation. No financial risk = broad appeal.

**Streak Tracking (Client-Side)**
- Track viewer's correct predictions in current session via localStorage
- Display: "Your current streak: 7 correct, 2 wrong (77%)"
- Reset streak at session end (next game)
- Why it works: Dopamine loop without money. Proven by ESPN Streak for the Cash (13 years of engagement).

**Optional Leaderboard (Future, not v1)**
- If adding accounts later, show top predictors of the day/week
- For v1, skip — client-side streak alone is sufficient

### Polls and Engagement Questions

**Live Polls During Game**
- Pose questions during betting rounds: "Will Player 2 fold?" (binary yes/no)
- Aggregate results in real-time, show vote distribution
- Reveal answer immediately after action resolves
- Why it works: Creates investment in outcomes. Chess.com uses this for analysis streams.

**AI Behavior Predictions**
- "Will this player bluff?" before river bet
- "Aggressive or cautious?" on the next decision
- Teaches viewers to recognize AI personality patterns
- Why it works: Gamifies learning. Viewer becomes invested in understanding the AI.

### Viewer Count and Social Signals

**Live Concurrent Count**
- Display "1,247 watching now" in header
- Refresh every 5-10 seconds
- Why it works: Creates FOMO. Viewers stay longer if they see the stream is popular. Proven in Twitch.

**Chat-Free Engagement (v1 approach)**
- Show viewer count, but no chat
- Rationale: Chat adds operational complexity; v1 is spectator-only
- Future: Chat can add engagement but also toxicity risk

### Dramatic Reveal Mechanics

**Paced Reasoning Reveals**
- AI reasoning text appears progressively (streaming) rather than all at once
- Strategic pauses before key reveals (doubt, conviction, decision)
- Example: "I'm holding A-K..." [pause 1s] "...and the pot is $200..." [pause] "...I think they're weak..." [pause] "...FOLD."
- Why it works: Builds narrative tension. Proven in game narrative design (God of War pacing patterns).
- Code hint: Stream text chunks over 2-5 seconds, not all at once

**Tension/Release Rhythm**
- Fast reveals during betting rounds (quick decisions)
- Slow reveals during showdown (dramatic moment)
- Use silence/pauses to emphasize key moments
- Why it works: Ebb-and-flow pacing keeps viewers engaged. Prevents fatigue from constant action.

**Player Face Card Revelation Timing**
- Keep hole cards face-down until showdown (build mystery)
- Reveal one card at a time during showdown (not both at once)
- Why it works: Classic poker TV technique (WPT, WSOP). Extends drama.

---

## AI Personality Archetype Patterns

How to parameterize AI behavior so each model plays with distinct character while remaining unpredictable.

### Archetype Framework

Each AI is randomly assigned one archetype per game. The archetype is NOT HIDDEN from viewers — it's displayed so they understand why the AI plays that way.

**Archetype Metadata (Data-Driven)**
```json
{
  "name": "Aggressive Gunslinger",
  "description": "Plays many hands, raises frequently, takes calculated risks",
  "parameters": {
    "hand_looseness": 0.75,
    "raise_frequency": 0.65,
    "bluff_frequency": 0.45,
    "fold_to_aggression": 0.30,
    "stack_preservation": 0.20
  }
}
```

**Parameter Definitions:**

| Parameter | Range | Meaning |
|-----------|-------|---------|
| **hand_looseness** | 0.0–1.0 | Proportion of hands played (0.3 = tight/selective, 0.75 = loose/many hands) |
| **raise_frequency** | 0.0–1.0 | How often AI raises vs. calls (0.8 = aggressive, 0.2 = passive) |
| **bluff_frequency** | 0.0–1.0 | Likelihood of betting weak hands as if strong (0.6 = frequent bluffer, 0.2 = honest) |
| **fold_to_aggression** | 0.0–1.0 | Likelihood of folding when opponent raises (0.7 = folds easily, 0.2 = calls/re-raises often) |
| **stack_preservation** | 0.0–1.0 | Risk aversion relative to chip stack (0.8 = cautious, 0.2 = all-in prone) |

### Personality Archetype Examples

**1. Aggressive Gunslinger**
- hand_looseness: 0.75
- raise_frequency: 0.65
- bluff_frequency: 0.45
- fold_to_aggression: 0.30
- stack_preservation: 0.20
- **Behavior:** Plays many hands, raises often, bluffs regularly. Takes big swings. Drives action.
- **Viewer dynamic:** "Will they overextend again?"

**2. Paranoid Rock**
- hand_looseness: 0.25
- raise_frequency: 0.20
- bluff_frequency: 0.05
- fold_to_aggression: 0.80
- stack_preservation: 0.90
- **Behavior:** Folds frequently, only plays premium hands, rarely bluffs. Tight & defensive.
- **Viewer dynamic:** "When will they finally make a move?"

**3. Conservative Grinder**
- hand_looseness: 0.40
- raise_frequency: 0.35
- bluff_frequency: 0.20
- fold_to_aggression: 0.50
- stack_preservation: 0.70
- **Behavior:** Solid, balanced play. Doesn't take unnecessary risks but not passive.
- **Viewer dynamic:** "The safe choice. Reliable."

**4. Chaotic Optimist**
- hand_looseness: 0.80
- raise_frequency: 0.75
- bluff_frequency: 0.70
- fold_to_aggression: 0.10
- stack_preservation: 0.10
- **Behavior:** Plays almost any hand, re-raises frequently, bluffs aggressively, rarely folds. Unpredictable.
- **Viewer dynamic:** "Anything can happen."

### How to Apply Archetypes in Decision Logic

**During decision point (pre-flop, post-flop, etc.):**

1. **Compute "hand strength"** (programmatic math, not LLM)
   - Win probability vs. rest of field
   - Pot odds: (risk to call) / (total pot if win)

2. **Apply archetype bias to decision thresholds**
   - Example: Loose player has lower fold threshold
   - Formula: adjusted_threshold = base_threshold * (1 - hand_looseness * 0.5)
   - Loose players call/raise with weaker hands

3. **Introduce controlled randomness**
   - roll = random(0, 1)
   - if roll < bluff_frequency && pot_size > threshold: bluff_bet()
   - Ensures bluffs happen but aren't deterministic

4. **Prompt the LLM with archetype constraints**
   - Include archetype in system prompt: "You are playing as the Aggressive Gunslinger. You value action and calculated risk."
   - LLM respects character while narrating reasoning
   - **Critical:** Math decisions (call/fold/raise amount) come from code, not LLM

### Personality Transparency

**Display to Viewers:**
- "Claude: [Archetype name]" next to player name
- A short one-liner below: "Plays tight, rarely bluffs"
- Icon or color-coding per archetype (optional, for visual clarity)

**Why transparency matters:**
- Viewers understand WHY the AI plays that way
- Reduces frustration ("Why did it fold?!" → "Oh, it's paranoid.")
- Creates investment in the character, not just the game
- Enables viewer predictions: "The gunslinger will raise here"

### Future: Archetype Extension (Not v1)

**Joke Cards / Rule Tweaks (Post-MVP)**
- Override archetypes temporarily (e.g., "Drunk Genius" plays terrible hands but sometimes wins)
- Add special abilities (e.g., "Lucky Charm" gets slight probability boost)
- Extends replayability without breaking core rules
- Marked as out-of-scope for v1 per PROJECT.md

---

## Anti-Features (Deliberately Skip)

What NOT to build, and why.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **User authentication in v1** | Adds complexity (sign-up, password reset, sessions). Slows launch. | Keep fully anonymous. Visitor can predict/watch immediately. Add accounts post-MVP if needed. |
| **Real money or token betting** | Legal liability, regulatory headaches, payment processing, KYC compliance. Out of scope per PROJECT.md. | Prediction streaks are proven dopamine loops without money (ESPN Streak). No financial risk = broader audience. |
| **Side pots and split-pot edge cases** | Complex to compute, rare in 4-player games, breaks narrative pacing during showdown. Adds 20%+ complexity. | Simplified rule: single main pot only (Project.md constraint). Doesn't affect core experience for v1. |
| **Chat or live messages from viewers** | Moderation burden, toxicity risk, operational overhead. Not part of v1 reactions model. | Show viewer count + predictions/polls instead. Chat can be future milestone if needed. |
| **Custom chip buys or rebuy logic** | Out of scope (PROJECT.md). No persistent accounts = no chip history. | Each game starts fresh. All players equal stacks. Simplifies rules. |
| **Detailed hand history / replay system** | Requires persistent storage, replay UI, seek-bar logic. Nice-to-have, not table stakes. | Store game JSON for future analysis tools. Skip UI replay for v1. |
| **Multi-table tournament mode** | Scaling complexity, table selection logic, payout tiers. Out of scope. | Single table, 4-player, continuous games. Simplest form = fastest launch. |
| **Customizable AI parameters (user-facing)** | Let viewers adjust archetype sliders? Creates unfair setups, weakens drama (viewers would nerf opponents). | Archetypes randomized server-side, not customizable. Viewer sees assigned archetype but can't change it. |
| **LLM-computed hand strength** | LLMs are bad at probability math. Slow (API calls), expensive, inconsistent. | Use programmatic hand evaluator (Rust poker libraries, CardHS library, or hand-rolled eval function). Math stays in code. |
| **Viewer voting to influence game (Twitch Plays style)** | Would break game integrity. Also would slow down decision-making. | Predictions and polls only. No voting to change AI decisions. |
| **Text-to-speech for AI reasoning** | Nice UI touch but adds latency, voice quality issues, accessibility liability. | Stream text to reasoning panel. Optional TTS feature post-MVP. |
| **Streamer customization (theme, overlay, alerts)** | No streamer mode in v1. Product is a fixed experience, not a customizable service. | Simple clean UI. Future: white-label options post-MVP. |

---

## Spectator Experience Arc

**How a typical viewer session unfolds (v1):**

1. **Join stream:** See "Waiting for next game..." or current game in progress
2. **Game starts:** Live 4-player table with archetypes visible
3. **Pre-flop:** AI reasoning streams in real-time; viewer can predict winner now
4. **Betting rounds:** Tension builds; viewer watches probabilities; polls pop up
5. **Showdown:** Hole cards reveal one by one; AI explains the logic
6. **Results:** Viewer sees prediction result (win/loss); streak updates
7. **Next game:** Archetypes randomize; repeat

**Duration:** ~15 min per game (4 betting rounds × competitive play). Sustainable for 24/7 streaming if infrastructure permits.

---

## Sources

**Texas Hold'em Rules:**
- [Texas Hold'em Wikipedia](https://en.wikipedia.org/wiki/Texas_hold_'em)
- [PokerNews Rules Guide](https://www.pokernews.com/poker-rules/texas-holdem.htm)
- [Bicycle Cards How to Play](https://bicyclecards.com/how-to-play/texas-holdem-poker)
- [Hand Rankings and Kickers](https://holdeminside.com/hand-rankings/)
- [Kicker Explanation](https://howtoplaypokerinfo.com/kicker/)

**Spectator Engagement:**
- [Chess.com Live Analysis and Spectating](https://support.chess.com/en/articles/8705875-how-can-i-watch-a-game)
- [Twitch Plays Pokémon Mechanics](https://en.wikipedia.org/wiki/Twitch_Plays_Pok%C3%A9mon)
- [Crowd Behavior in Twitch Plays](https://blogs.biomedcentral.com/on-society/2019/06/25/what-twitch-plays-pokemon-tells-us-about-crowd-behavior/)

**Prediction Mechanics Without Money:**
- [StreakfortheCash Free Contests](https://www.streakforthecash.com/)
- [Gamification in Betting Apps](https://medium.com/@dechtenkamp3/the-gamification-trap-how-betting-apps-keep-you-coming-back-7f7e0ba9d8a4)

**AI Personality Parameterization:**
- [Personality Traits in AI](https://www.emergentmind.com/topics/ai-personality-traits)
- [AI Learning Personality Traits](https://gafowler.medium.com/from-data-to-disposition-how-ai-can-learn-personality-traits-0987f154b594)
- [Big Five and HEXACO Personality Models](https://arxiv.org/html/2312.02998v1)
- [Psychologically Enhanced AI Agents](https://arxiv.org/pdf/2509.04343)

**Poker AI Behavior:**
- [AI Poker Battle Analysis](https://www.poker.org/poker-strategy/the-ai-poker-battle-of-the-llms-as-detected-in-areal-game-scenario/)
- [Poker Robot AI Strategies](https://3upgaming.com/blog/advanced-strategies-for-poker-bots/)
- [CMU: Computers Bluffing Like Poker Champs](https://www.cmu.edu/ambassadors/october-2019/artificial-intelligence)

**Game Narrative Pacing:**
- [Pacing in Game Narrative](https://www.numberanalytics.com/blog/the-art-of-narrative-pacing-in-game-design)
- [Story Pacing Techniques](https://www.storyflint.com/dives/pacing)
- [Tension and Release in Game Design](https://www.deeplore.show/pacing-tension-structures/)

**Real-Time Broadcasting:**
- [SSE vs WebSocket Comparison](https://medium.com/@sulmanahmed135/websockets-vs-server-sent-events-sse-a-practical-guide-for-real-time-data-streaming-in-modern-c57037a5a589)
- [Real-Time Presence Detection](https://www.pubnub.com/products/presence/)
- [Idle Detection API](https://wicg.github.io/idle-detection/)

**Spectator-Focused Game Design:**
- [Game Development in the Streaming Era](https://www.raceintospace.org/online-game-development-in-the-streaming-era-what-changes-in-the-product-and-its-mechanics/)
- [Spectator-Participation Design](https://medium.com/ironsource-levelup/spectator-participation-the-next-step-for-gaming-c70f565adf45)

**Anonymous Polling:**
- [Anonymous Response Systems](https://support.polleverywhere.com/hc/en-us/articles/9708338689051-anonymous-responses)
- [Genially Audience Engagement](https://genially.com/features/audience-engagement/)
- [Slido Anonymous Participation](https://www.slido.com/)
