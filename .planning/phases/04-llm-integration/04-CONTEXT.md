# Phase 4: LLM Integration — Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire real LLM players into the game engine: each AI player calls its model at every decision point with structured math context and archetype flavor, streams reasoning token-by-token into the frontend ReasoningPanel, and never halts the game on timeout or bad output.

The `DecisionFn` async seam is already in place — Phase 4 drops in its implementation with zero refactor. Game still runs on VPS; SSE pipeline from Phase 3 is extended with a new `event: reasoning` event type.

</domain>

<decisions>
## Implementation Decisions

### Reasoning Streaming
- **D-01:** A new `event: reasoning` SSE event type is added alongside the existing `event: game_state`. Published during each player's decision window while the LLM is streaming tokens.
- **D-02:** Payload is delta-only: `{ playerId, phase, delta, done }`. Frontend appends `delta` to the active `ReasoningEntry.text`; sets `streaming: false` when `done: true`.
- **D-03:** Phase 3's phase-transition-only broadcast rule (D-06) is relaxed for Phase 4: a `game_state` event is published after **each individual player action** (fold/call/raise/check) within a betting round — not just at flop/turn/river/showdown transitions. Viewers see chip movements and action stamps live during betting.

### LLM Prompt Structure
- **D-04:** System + user message split. System message carries player identity, archetype persona, and behavioral instruction ("You are GPT-5.5 Nano, playing as the Gunslinger archetype..."). User message carries structured current-hand context.
- **D-05:** Current-hand context only — no cross-hand memory. User message includes: hole cards, community cards, current phase, pot, available actions with amounts, player's own chip stack, and a list of opponents with their chip count + last action this street (fold/call/raise/check). No opponent hole cards.
- **D-06:** LLM response format: fenced JSON block ` ```json { "action": "...", "amount": 0, "reasoning": "..." } ``` `. Parsed with regex fallback to extract the JSON. Works across all providers without tool-call support requirements.
- **D-07:** The `reasoning` field from the LLM response is what gets streamed token-by-token if using streaming mode; for non-streaming fallback it is sent as a single `event: reasoning` with `done: true`.

### Archetype Assignment
- **D-08:** Archetypes are assigned uniquely per game — each of the N players gets a different archetype. With 4 players and 4 archetypes, every game has exactly one of each type. Assignment is a random shuffle of the archetype list at game start.
- **D-09:** Archetypes are data-driven — defined as a config structure (JSON or Python dict) with: `name`, `description` (used in LLM prompt), and numeric bias parameters: `hand_looseness`, `raise_freq`, `bluff_freq`, `tilt_threshold`. Adding a new archetype requires only a config entry, no code change. Supports the roadmap's future "joke cards" extension.
- **D-10:** Initial 4 archetypes: **Gunslinger** (aggressive raiser), **Rock** (tight folder), **Grinder** (tight-solid, position-aware), **Chaotic Optimist** (calls anything). These match the requirements (AI-06) and are the baseline for viewer-legible style contrast.

### Fallback Behavior
- **D-11:** When an LLM call times out (>2s individual / >8s global) or returns malformed/invalid output, the fallback produces a **deterministic decision based on hand strength + archetype bias parameters**. Example: Gunslinger raises if `win_probability > raise_freq threshold`; Rock folds unless `win_probability > hand_looseness threshold`.
- **D-12:** Fallback publishes a single non-streaming `ReasoningEntry` with a notice like `[GPT-5.5 Nano timed out — acting on instinct]`. `streaming: false`, `done: true`. The ReasoningPanel stays alive for all players; timeouts are visible to viewers.

### Player Initialization
- **D-13:** `session.py._make_players()` is replaced. Players are initialized from `models.config.json`: `id`, `name`, `org`, `color`, `deck` come from config; `chips` set from `starting_chips`. Archetype assigned at session/game start (not per-hand).

### Game Loop Wiring
- **D-14:** `game_loop.py` is updated to construct the LLM decision function and pass it to `session.run(decision_fn=llm_decision_fn)`. The decision function reads the player's model string from config and routes through LiteLLM `acompletion`.

### Budget & Circuit Breaker (INFRA-05)
- **D-15:** Per-game LLM spend is tracked by accumulating token counts × cost-per-token (or approximation) and logged at session end. Implemented as a simple in-memory accumulator per `GameSession`.
- **D-16:** Circuit breaker per provider: if a provider returns errors on N consecutive calls (configurable, default 3), subsequent calls for that provider's player fall through to fallback immediately without attempting the LLM. Resets on session start.

### Module Layout
- **D-17 (Claude's Discretion):** New files under `backend/app/`:
  ```
  backend/app/
  ├── ai/
  │   ├── __init__.py
  │   ├── archetypes.py     ← archetype definitions (data-driven config)
  │   ├── decision.py       ← LLM decision function (DecisionFn implementation)
  │   ├── prompt.py         ← prompt builder (system + user message construction)
  │   └── budget.py         ← per-game spend tracker + circuit breaker
  └── broadcast/
      └── publisher.py      ← extended with publish_reasoning() for event: reasoning
  ```

### Claude's Discretion
- Exact archetype bias thresholds (Gunslinger raise_freq, Rock hand_looseness, etc.)
- LiteLLM `acompletion` streaming implementation details (chunk iteration)
- JSON extraction regex pattern
- Budget cost approximation method (token count log vs. provider pricing API)
- Circuit breaker reset strategy (per-session vs. time-based)
- `ReasoningEntry` Python Pydantic model definition (must match TypeScript interface)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 4 Requirements
- `.planning/REQUIREMENTS.md` — AI-01 through AI-06 (LLM players, archetypes, structured prompts, fallbacks, streaming reasoning, visible style differences), INFRA-05 (budget protection)
- `.planning/ROADMAP.md` — Phase 4 success criteria (6 criteria, all must be TRUE)

### Frontend Type Contract
- `app/_components/types.ts` — `ReasoningEntry` TypeScript interface (`id`, `playerId`, `text`, `phase`, `streaming`, `action`, `amount`). Python `ReasoningEntry` Pydantic model MUST match this shape. `GameState.reasoning: list[ReasoningEntry]`.

### Player + Model Config
- `models.config.json` — Player roster with `id`, `name`, `org`, `color`, `deck`, `litellmModel`. Source of truth for player initialization and LiteLLM model strings.
- `backend/app/config.py` — `Settings.player_models` (list of LiteLLM model strings from config), `llm_timeout_seconds: int = 8`.

### Existing Engine (Phase 2 output)
- `backend/app/engine/models.py` — `DecisionFn` type alias (async seam), `Player`, `GameState`, `Action`, `ActionType`. `GameState.reasoning: list` → Phase 4 types to `list[ReasoningEntry]`.
- `backend/app/engine/session.py` — `GameSession.run(decision_fn, broadcast_fn)` — D-13 replaces `_make_players()`. D-14 wires LLM decision fn.
- `backend/app/engine/game.py` — `valid_actions()`, `BroadcastFn` type. D-03 requires `broadcast_fn` called after each player action.
- `backend/app/engine/poker_math.py` — `calculate_equity()` returns `win_probability`, `pot_odds`, `hand_strength`. These are the math fields fed to the LLM prompt (AI-03).

### SSE Broadcast (Phase 3 output)
- `backend/app/broadcast/publisher.py` — existing `publish(redis_client, game_state)`. Extend with `publish_reasoning(redis_client, reasoning_delta)` for `event: reasoning`.
- `backend/app/api/stream.py` — SSE endpoint. Must handle the new `event: reasoning` event type alongside existing `event: game_state`.
- `.planning/phases/03-sse-broadcast/03-CONTEXT.md` — D-04 (full snapshot model), D-09 (per-client asyncio.Queue fan-out), D-06 (phase-transition rule — relaxed by Phase 4 D-03)

### Prior Phase Context
- `.planning/phases/01-backend-foundation/01-CONTEXT.md` — LiteLLM wiring, env var pattern
- `.planning/phases/02-game-state-machine/02-CONTEXT.md` — D-02 (async decision seam design)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/engine/poker_math.py` — `calculate_equity(hole_cards, community_cards, num_opponents, n_simulations)` → `{ hand_strength, win_probability, pot_odds }`. Call this at decision time to build the math context for the LLM prompt.
- `backend/app/engine/game.py` — `valid_actions(player, state)` → list of valid `ActionType`s with amounts. Feed directly into the prompt's available-actions list.
- `backend/app/broadcast/publisher.py` — existing `publish()` pattern; new `publish_reasoning()` follows same structure.
- `backend/app/config.py` — `Settings.player_models`, `Settings.llm_timeout_seconds` already there. `get_settings()` with `@lru_cache`.

### Established Patterns
- Async decision seam: `async def make_decision(player: Player, game_state: GameState) -> Action`
- Pydantic `BaseModel` for all serialized data; `model_dump(by_alias=True)` for camelCase JSON
- `uv run pytest` from `backend/` — all tests follow this convention
- `asyncio.Queue` fan-out pattern in `broadcast/broker.py` — new `event: reasoning` events go through same queue

### Integration Points
- `game_loop.py`: construct `llm_decision_fn` → pass to `session.run(decision_fn=llm_decision_fn)`
- `session.py._make_players()`: replace with config-driven player init from `models.config.json`
- `broadcast/publisher.py`: add `publish_reasoning()` alongside existing `publish()`
- `api/stream.py`: SSE generator already yields `ServerSentEvent` — extend to handle `event: reasoning` events from the queue
- `GameState.reasoning`: change type annotation from `list` to `list[ReasoningEntry]` (new Pydantic model)

</code_context>

<specifics>
## Specific Requirements

- `event: reasoning` SSE payload: `{ "playerId": "...", "phase": "...", "delta": "...", "done": false }`
- `event: game_state` published after each player action within a betting round (not only phase transitions)
- Fallback notice format: `[{player name} timed out — acting on instinct]` as a single ReasoningEntry with `streaming: false`
- Archetypes are assigned as a random shuffle (unique, no repeats) at `GameSession` initialization
- LLM response must be parsed from a fenced ` ```json ``` ` block; regex extraction required
- Sequential LLM calls (not parallel) per decision phase — all players in turn order
- 2s timeout per individual LLM call; 8s global deadline across all calls in one decision phase
- Circuit breaker: 3 consecutive errors per provider triggers immediate fallback for remainder of session
- Player identity fields (`id`, `name`, `org`, `color`, `deck`) loaded from `models.config.json`

</specifics>

<deferred>
## Deferred Ideas

- **Cross-hand player behavior profiling** — Feed per-player action history across hands into the decision prompt so LLMs can identify "Player 2 bluffs every street" and adapt. Interesting for viewer experience but requires persistent cross-hand state. Deferred to v2.
  - Sub-question noted: at what thresholds should history override archetype instinct? (e.g., does a Gunslinger with a strong hand ignore opponent reads entirely?)

- **Parallel LLM calls** — Calling all players simultaneously per decision phase. Sequential is intentional for v1 (simpler, cheaper). Revisit if latency becomes a viewer experience problem.

- **Provider pricing API for exact budget tracking** — v1 uses token count approximation. Exact cost tracking via provider APIs deferred.

</deferred>

---

*Phase: 04-llm-integration*
*Context gathered: 2026-05-07*
