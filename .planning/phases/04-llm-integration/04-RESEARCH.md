# Phase 4: LLM Integration — Research

**Researched:** 2026-05-07
**Domain:** LiteLLM async streaming, archetype-driven LLM decision loop, SSE reasoning broadcast
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Reasoning Streaming**
- D-01: New `event: reasoning` SSE event type alongside existing `event: game_state`
- D-02: Delta-only payload: `{ playerId, phase, delta, done }`; frontend appends delta, sets `streaming: false` when `done: true`
- D-03: `event: game_state` published after EACH individual player action (fold/call/raise/check) within a betting round — relaxes Phase 3 D-06

**LLM Prompt Structure**
- D-04: System + user message split (system = identity + archetype persona; user = current-hand context)
- D-05: Current-hand context only (no cross-hand memory). User message includes: hole cards, community cards, phase, pot, available actions with amounts, player's chip stack, opponent chip count + last action this street
- D-06: Fenced JSON response format: ` ```json { "action": "...", "amount": 0, "reasoning": "..." } ``` `; parsed with regex
- D-07: The `reasoning` field is streamed token-by-token; non-streaming fallback sends as single event with `done: true`

**Archetype Assignment**
- D-08: Unique archetypes per game via random shuffle (no repeats among N players)
- D-09: Data-driven archetype config: `name`, `description`, numeric bias params (`hand_looseness`, `raise_freq`, `bluff_freq`, `tilt_threshold`)
- D-10: 4 archetypes: Gunslinger, Rock, Grinder, Chaotic Optimist

**Fallback Behavior**
- D-11: Deterministic fallback using hand strength + archetype bias params on timeout / bad JSON / invalid action
- D-12: Fallback publishes single notice: `[{player name} {reason} — acting on instinct]`, `streaming: false`, `done: true`

**Player Initialization**
- D-13: `session.py._make_players()` replaced; players initialized from `models.config.json`
- D-14: `game_loop.py` constructs LLM decision fn and passes to `session.run(decision_fn=llm_decision_fn)`

**Budget and Circuit Breaker (INFRA-05)**
- D-15: Per-game spend tracked via token count approximation; logged at session end
- D-16: Circuit breaker per provider: 3 consecutive errors trips; resets on session start

**Module Layout**
- D-17: New module `backend/app/ai/` with `__init__.py`, `archetypes.py`, `decision.py`, `prompt.py`, `budget.py`; extend `broadcast/publisher.py` with `publish_reasoning()`

### Claude's Discretion
- Exact archetype bias thresholds
- LiteLLM `acompletion` streaming implementation details (chunk iteration)
- JSON extraction regex pattern
- Budget cost approximation method
- Circuit breaker reset strategy (per-session vs time-based)
- `ReasoningEntry` Python Pydantic model definition (must match TypeScript interface)

### Deferred Ideas (OUT OF SCOPE)
- Cross-hand player behavior profiling (v2) — per-player action history in decision prompts
- Parallel LLM calls (v2) — sequential is intentional for v1
- Provider pricing API for exact budget tracking (v2)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AI-01 | N configurable LLM players (default 4); roster from config/env; any LiteLLM-supported model; sequential calls per decision phase | `models.config.json` already has 4 players; `Settings.player_models` loads from it; `DecisionFn` seam receives `(player, game_state)` |
| AI-02 | Random archetype per player at game start; archetype defines personality + bias params | Archetype shuffle in `GameSession.__init__`; `archetypes.py` data-driven config; passes as context to `llm_decision_fn` |
| AI-03 | Structured math context at each decision: hand strength, pot odds, win probability, available actions with amounts, pot, community cards, archetype description | `poker_math.calculate_equity()` returns all three math fields; `valid_actions()` needs BettingRoundState (see Critical Gap below); prompt builder assembles user message |
| AI-04 | Validate LLM response; fallback on malformed/timeout/invalid action | `_parse_response()` + action enum check + `_fallback_action()`; 2s per-call / 8s global deadline via `asyncio.wait_for()` |
| AI-05 | Reasoning text streams token-by-token into ReasoningPanel | `publish_reasoning()` called on each streaming chunk; `event: reasoning` SSE events consumed by frontend |
| AI-06 | Visibly different play style per archetype; legible to non-poker-expert viewers | Code-level bias enforcement in `_fallback_action()`; archetype description in system prompt for LLM narrative |
| INFRA-05 | Per-game spend tracked; 8s global deadline; circuit breaker per provider | `BudgetTracker` + `CircuitBreaker` in `budget.py`; `asyncio.wait_for()` for global deadline management |
</phase_requirements>

---

## Summary

Phase 4 wires real LLM decisions into an already-complete game engine and SSE pipeline. The `DecisionFn` async seam (`async def make_decision(player, game_state) -> Action`) is the sole insertion point — the game engine calls it and does not need to know whether a human, mock, or LLM is deciding. Phase 4's implementation drops into that seam without refactoring Phases 1-3.

The primary work is creating `backend/app/ai/` as a new module: an archetype config system, a prompt builder, a decision function that calls LiteLLM with streaming, JSON extraction, Pydantic validation, and deterministic fallback. Parallel work extends `broadcast/publisher.py` with `publish_reasoning()` and updates `api/stream.py` to route both `event: game_state` and `event: reasoning` events from a shared broker queue.

Two critical integration gaps discovered during codebase audit require attention in planning: (1) `valid_actions()` in `game.py` takes `BettingRoundState` which is internal to `run_betting_round()` and not stored in `GameState` — the decision function must reconstruct valid actions from `GameState` data alone; (2) the AI-SPEC code examples use an incorrect `Action` field name (`type` instead of `action_type`) — all plan tasks must use `Action(action_type="raise", amount=x)`.

**Primary recommendation:** Build `backend/app/ai/` as a clean new module. Wire it into `game_loop.py` using a closure that curries archetype, budget, and circuit context into the `DecisionFn` signature without changing `game.py`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| LLM decision call | API / Backend (FastAPI async) | — | `acompletion()` must run inside the existing asyncio event loop; no bridging needed |
| Archetype config + bias enforcement | API / Backend | — | Code-level bias is applied in `_fallback_action()`; LLM only gets archetype for narrative |
| Prompt construction | API / Backend | — | `build_system_prompt()` + `build_user_prompt()` assemble Python strings; no frontend involvement |
| Streaming token fan-out | Redis Pub/Sub | FastAPI SSE | `publish_reasoning()` → Redis channel → broker → client queues (same pattern as game_state) |
| Reasoning display | Browser / Client | — | Frontend appends deltas to `ReasoningEntry.text`; sets `streaming: false` on `done: true` |
| Budget tracking + circuit breaker | API / Backend | — | In-memory per `GameSession`; no persistence needed in v1 |
| Player initialization from config | API / Backend | — | `session.py._make_players()` replacement reads `models.config.json` at session start |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| litellm | 1.83.14 [VERIFIED: venv importlib.metadata] | Unified async LLM interface | Already installed in Phase 1; provider-agnostic; `acompletion()` is the single call pattern for all 4 providers |
| pydantic | 2.12.5 [VERIFIED: venv importlib.metadata] | LLMDecisionResponse + ReasoningEntry model validation | Already the project's serialization standard; `model_validate()` for safe parse + `ValidationError` handling |
| asyncio | stdlib | `wait_for()` timeout enforcement | Native; no extra install; `wait_for(acompletion(...), timeout=2.0)` is the hard deadline |
| redis.asyncio | >=7.4.0 (already installed) | `publish_reasoning()` fan-out | Same pattern as existing `publish()` in `publisher.py` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | 1.3.0 [VERIFIED: venv] | Async test support | All `ai/` module tests; `asyncio_mode = "strict"` already configured |
| arize-phoenix + openinference-instrumentation-litellm | latest | LLM call tracing | Install as dev dependency for debugging; auto-instruments every `acompletion()` call |
| promptfoo | latest (Node.js, npm global) | CI/CD prompt regression tests | Run `promptfoo eval` on prompt changes; needs Node.js (already present for Next.js) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| LiteLLM direct `acompletion` | LangChain / LangGraph / CrewAI | All ruled out — add abstraction overhead for a linear sequential loop that needs none; see AI-SPEC Section 2 for full rationale |
| Fenced JSON response parsing | `response_format={"type": "json_object"}` | Not universally supported across OpenAI, Google, DeepSeek, xAI in the same call signature |
| In-memory `BudgetTracker` | Provider pricing API | v1 approximation is sufficient; exact pricing deferred to v2 |

**Installation (new dev dependencies only):**
```bash
cd backend/
uv add --dev arize-phoenix opentelemetry-sdk openinference-instrumentation-litellm
npm install -g promptfoo
```

---

## Architecture Patterns

### System Architecture Diagram

```
LiteLLM providers (OpenAI / Google / DeepSeek / xAI)
        |
        | acompletion(model, messages, stream=True)
        v
backend/app/ai/decision.py
  llm_decision_fn(player, game_state)
        |
        +--[circuit open?]--> _fallback_action() --> Action
        |
        +--[asyncio.wait_for 2s]--> acompletion stream
        |         |
        |         | async for chunk: delta
        |         v
        |    publish_reasoning(redis, player_id, phase, delta, done=False)
        |         |
        |         v
        |    Redis PUBLISH "game:reasoning"
        |         |
        |         v
        |    EventBroker.broadcast() --> per-client asyncio.Queue
        |         |
        |         v
        |    api/stream.py SSE generator --> event: reasoning --> Browser ReasoningPanel
        |
        +--[stream done]--> publish_reasoning(..., done=True)
        |
        +--[parse + validate]--+--> Action (success)
                               +--> _fallback_action() (parse failure / invalid action)

game_loop.py
  session.run(decision_fn=llm_decision_fn_curried)
        |
        | [after EACH player action — D-03]
        v
  publish(redis, game_state) --> event: game_state --> Browser
```

### Recommended Project Structure

```
backend/app/
├── ai/
│   ├── __init__.py
│   ├── archetypes.py       # archetype config dicts; ARCHETYPE_LIST; random shuffle fn
│   ├── decision.py         # llm_decision_fn; _parse_response; _fallback_action
│   ├── prompt.py           # build_system_prompt(player, archetype)
│   │                       # build_user_prompt(game_state, math_ctx, valid_acts_with_amounts)
│   ├── models.py           # LLMDecisionResponse + ReasoningEntry Pydantic models
│   └── budget.py           # BudgetTracker (dataclass) + CircuitBreaker (dataclass)
├── broadcast/
│   └── publisher.py        # existing publish() + new publish_reasoning()
├── engine/
│   ├── game.py             # MODIFIED: broadcast_fn called after each player action (D-03)
│   ├── session.py          # MODIFIED: _make_players() replaced with config-driven init
│   └── models.py           # MODIFIED: GameState.reasoning type → list[ReasoningEntry]
├── game_loop.py             # MODIFIED: constructs llm_decision_fn closure + BudgetTracker
├── api/
│   └── stream.py           # MODIFIED: routes both "game_state" and "reasoning" events
└── config.py               # NO CHANGE: Settings.player_models + llm_timeout_seconds already present
```

### Pattern 1: DecisionFn Signature Preservation via Closure

**What:** The existing `DecisionFn = Callable[[Player, GameState], Awaitable[Action]]` must not change — `game.py` calls it at line 198 with exactly `(player, game_state)`. The LLM decision function needs additional context (archetype, math_ctx, redis_client, budget, circuit). Use a closure in `game_loop.py` to curry extra parameters.

**When to use:** Any time extra context must be supplied to a decision function without changing `game.py`.

```python
# Source: codebase audit of backend/app/engine/models.py + game.py
# game_loop.py
from functools import partial
from app.ai.decision import make_llm_decision_fn
from app.ai.archetypes import assign_archetypes
from app.ai.budget import BudgetTracker, CircuitBreaker

async def run_game_loop(redis_client, settings):
    while True:
        budget = BudgetTracker()
        circuit = CircuitBreaker()
        players_config = load_players_from_config()   # from models.config.json
        archetypes = assign_archetypes(players_config)  # random shuffle

        # Make a closure that matches DecisionFn exactly
        decision_fn = make_llm_decision_fn(
            archetypes=archetypes,
            redis_client=redis_client,
            budget=budget,
            circuit=circuit,
        )
        # decision_fn is now: async def _(player: Player, game_state: GameState) -> Action

        session = GameSession(players=players_config, ...)
        await session.run(n_hands=10, decision_fn=decision_fn, broadcast_fn=...)

        logger.info("Session spend: %s", budget.summary())
```

### Pattern 2: Valid Actions Reconstruction Without BettingRoundState

**What:** `valid_actions()` in `game.py` requires `BettingRoundState` which is never stored in `GameState`. The LLM decision function receives only `(player, game_state)`. To get the current_bet, reconstruct it from `max(p.bet for p in game_state.players if not p.is_folded)`.

**Why it works:** `mock_decision` already uses this exact pattern (game.py line 505-514). The max player bet IS the current_bet for purposes of checking / calling / raising.

```python
# Source: codebase audit of backend/app/engine/game.py lines 499-514
def reconstruct_valid_actions(player: Player, game_state: GameState) -> dict:
    """
    Reconstruct valid actions + amounts from GameState alone.
    Returns dict with keys: valid_types (set), call_amount, min_raise, max_raise.
    """
    current_bet = max(
        (p.bet for p in game_state.players if not p.is_folded),
        default=0
    )
    call_amount = max(0, current_bet - player.bet)
    can_raise = player.chips > call_amount

    valid = []
    amounts = {}

    valid.append("fold")

    if call_amount == 0:
        valid.append("check")
        amounts["check"] = 0
    else:
        valid.append("call")
        amounts["call"] = min(call_amount, player.chips)  # all-in cap

    if can_raise:
        # min raise = current_bet + big_blind (approximation without last_raise_size)
        # prompt builder uses this for the "available actions" list
        amounts["raise_min"] = current_bet + 20  # approximate; game.py enforces actual min
        amounts["raise_max"] = player.chips + player.bet  # all-in
        valid.append("raise")

    return {
        "valid_types": set(valid),
        "call_amount": amounts.get("call", 0),
        "raise_min": amounts.get("raise_min", 0),
        "raise_max": amounts.get("raise_max", 0),
    }
```

**Planner note:** The game engine (`game.py` lines 218-230) enforces the true minimum raise independently, so approximate `raise_min` in the prompt is safe — an underestimate will be corrected by the engine on execution.

### Pattern 3: Correct Action Model Usage

**What:** The `Action` model uses `action_type` (not `type`), and `ActionType` is a `Literal` string union (not an Enum). The AI-SPEC code examples contain an error.

**When to use:** Any task creating `Action` instances in the `ai/` module.

```python
# Source: codebase audit of backend/app/engine/models.py lines 38-44
# WRONG (from AI-SPEC code samples — do not use):
# Action(type=ActionType.RAISE, amount=80)
# ActionType.RAISE  — Literal has no attribute access

# CORRECT:
from app.engine.models import Action, ActionType
action = Action(action_type="raise", amount=80)
action = Action(action_type="fold")    # amount defaults to 0
action = Action(action_type="call")
action = Action(action_type="check")
```

### Pattern 4: `publish_reasoning()` Channel Routing

**What:** Reasoning events must travel through the same broker fan-out as game state events. The simplest approach is a second Redis channel (`"game:reasoning"`) that the broker subscribes to alongside `"game:state"`.

**Alternative:** Multiplex both event types through the same `"game:state"` channel by adding an `"eventType"` field to the payload — but this requires differentiating at the SSE generator level and risks confusing the Phase 3 snapshot logic.

**Recommended:** Two separate Redis channels; `broker.run_subscriber()` subscribes to both; `stream.py` SSE generator routes by channel tag stored in the queue message envelope.

```python
# backend/app/broadcast/publisher.py addition
REASONING_CHANNEL = "game:reasoning"

async def publish_reasoning(
    redis_client: redis.Redis,
    player_id: str,
    phase: str,
    delta: str,
    done: bool,
) -> None:
    payload = json.dumps({
        "playerId": player_id,
        "phase": phase,
        "delta": delta,
        "done": done,
    })
    await redis_client.publish(REASONING_CHANNEL, payload)
```

**SSE stream.py routing:** The queue message from the broker needs a tag so the SSE generator knows which `event:` type to emit. One approach: prefix the payload with the channel name in the broker broadcast, then split in `stream.py`.

### Pattern 5: ReasoningEntry Pydantic Model

**What:** Python `ReasoningEntry` must exactly match the TypeScript interface in `app/_components/types.ts`.

**TypeScript interface (verified from codebase):**
```typescript
// Source: app/_components/types.ts lines 21-29
interface ReasoningEntry {
  id: string;
  playerId: ModelId;  // one of: "gpt4" | "gemini" | "deepseek" | "grok"
  text: string;
  phase: string;
  streaming: boolean;
  action: ActionType | null;
  amount: number;
}
```

**Matching Python model:**
```python
# Source: app/_components/types.ts + pydantic v2 pattern from codebase
from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Literal, Optional
import uuid

class ReasoningEntry(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_id: str           # → playerId in JSON
    text: str = ""
    phase: str
    streaming: bool = True
    action: Optional[Literal["fold", "call", "raise", "check"]] = None
    amount: int = 0
```

**Serialization:** `entry.model_dump(by_alias=True)` produces the camelCase JSON matching `types.ts`.

### Anti-Patterns to Avoid

- **Using `asyncio.run()` inside FastAPI route or background task:** Raises `RuntimeError: This event loop is already running`. Always `await acompletion(...)` directly.
- **Passing `num_retries` with `stream=True`:** Silently ignored — creates false sense of retry safety. All retry logic via `CircuitBreaker`.
- **`chunk.choices[0].delta.content` without None guard:** First and last chunks have `content=None`. Always: `if delta := chunk.choices[0].delta.content:`.
- **Hardcoding model strings in `decision.py`:** All model strings must come exclusively from `models.config.json` via `Settings.player_models` or the player config object.
- **Changing the `DecisionFn` type signature in `models.py`:** `game.py` calls it at line 198 with exactly `(player, game_state)`. Use closure / partial to supply extra context.
- **Using `Action(type=..., amount=...)` or `ActionType.FOLD`:** The field is `action_type` and `ActionType` is a `Literal`, not an Enum. Use `Action(action_type="fold")`.
- **Calling `valid_actions(player, betting_state)` from `decision.py`:** `BettingRoundState` is not available there. Reconstruct valid actions from `GameState` (Pattern 2 above).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async LLM calls to 4 providers | Provider-specific HTTP clients | `litellm.acompletion()` | Unified exception hierarchy, provider routing, no per-vendor SDK imports |
| Streaming token iteration | Manual HTTP chunked response parsing | `async for chunk in stream` (LiteLLM AsyncGenerator) | LiteLLM normalizes all provider streaming formats to OpenAI delta shape |
| Pydantic model validation | Custom dict parsing + type checks | `LLMDecisionResponse.model_validate(data)` | Generates detailed field-level errors for logging; consistent with project pattern |
| LLM call tracing | Manual logging of prompt + response + latency | `LiteLLMInstrumentor()` (Arize Phoenix) | Auto-instruments every `acompletion()` call as an OpenTelemetry span |
| Prompt regression CI | Custom test harness | `promptfoo eval` | Purpose-built for LLM prompt testing; integrates with CI via `--fail-threshold` |

---

## Critical Integration Gaps

These gaps are not in CONTEXT.md or AI-SPEC — discovered by reading the actual codebase.

### Gap 1: `valid_actions()` Requires `BettingRoundState` Not in `GameState`

**The problem:** `game.py:valid_actions(player, state: BettingRoundState)` takes `BettingRoundState` as its second argument. `BettingRoundState` is created locally inside `run_betting_round()` and is never stored in `GameState`. The `DecisionFn` receives `(player, game_state)` — no `BettingRoundState`.

**The consequence:** `decision.py` cannot call `valid_actions()` from `game.py`. The AI-SPEC code examples that call `valid_actions()` directly will fail at import/call time.

**The solution:** Implement `reconstruct_valid_actions(player, game_state)` in `ai/decision.py` using Pattern 2 above. This is safe because the game engine enforces true min-raise limits anyway — the prompt's raise range only needs to be approximate.

**Alternative (if more accuracy is needed):** Add `current_bet: int = 0` field to `GameState` and populate it in `run_betting_round()`. This exposes the exact current_bet to the decision function. The planner should choose between these two approaches.

### Gap 2: Action Model Field Name Mismatch in AI-SPEC

**The problem:** The AI-SPEC code examples (Section 4, `_fallback_action`) use:
```python
action = Action(type=ActionType.RAISE, amount=...)
```
The actual model (`models.py` lines 41-44) uses:
```python
class Action(BaseModel):
    action_type: ActionType  # field is "action_type", not "type"
    amount: int = 0
```
And `ActionType = Literal['fold', 'call', 'raise', 'check']` — no `.RAISE` attribute access.

**The consequence:** All plan tasks creating `Action` instances in `ai/decision.py` must use `Action(action_type="raise", amount=x)`. Copying the AI-SPEC examples verbatim will produce Pydantic `ValidationError` at runtime.

### Gap 3: `stream.py` Only Emits `event: game_state`

**The problem:** The existing `stream.py` SSE generator (lines 49-66) hardcodes `event="game_state"` on every `ServerSentEvent`. It has no logic to route `event: reasoning` events.

**The solution:** The EventBroker queue currently carries raw JSON strings. To support two event types, either: (a) the broker queue message includes a `{"eventType": "game_state"|"reasoning", "data": "..."}` envelope; or (b) a second Redis channel + second broker queue handles reasoning events exclusively. Option (b) is cleaner and avoids changing the existing `publisher.py` / game_state broadcast contract.

---

## Common Pitfalls

### Pitfall 1: `asyncio.wait_for()` Fires Mid-Stream, Leaving Partial Buffer

**What goes wrong:** If a model begins streaming but takes >2s to complete all chunks, `asyncio.wait_for()` fires while `full_text` is incomplete. The fenced JSON block is truncated; regex extraction fails. Code that attempts to use the partial buffer produces parse errors or corrupted actions.

**Why it happens:** `asyncio.wait_for()` applies to the outer coroutine lifecycle. Once the stream object is returned, chunk iteration can still block indefinitely.

**How to avoid:** Pass `timeout=INDIVIDUAL_TIMEOUT_S` to `acompletion()` as well. LiteLLM uses this parameter to close the HTTP connection from its side, capping the stream lifetime. Use both layers: `wait_for()` as the hard asyncio wall, and `timeout=` on the call for HTTP cleanup. [VERIFIED: docs.litellm.ai/docs/completion/input]

**Warning signs:** `asyncio.TimeoutError` caught at the `wait_for` level; `full_text` is non-empty but the fenced JSON regex returns no match.

### Pitfall 2: `chunk.choices[0].delta.content` is None on First and Last Chunks

**What goes wrong:** `full_text += delta` raises `TypeError: can only concatenate str (not "NoneType") to str`.

**Why it happens:** First chunk carries `role="assistant"` with `content=None`; final chunk has `finish_reason="stop"` with `content=None`.

**How to avoid:** Always: `if delta := chunk.choices[0].delta.content:` before appending. [VERIFIED: docs.litellm.ai/docs/completion/stream]

### Pitfall 3: `num_retries` is Silently Ignored with `stream=True`

**What goes wrong:** Developer passes `num_retries=3` expecting automatic retry on failure. With `stream=True`, LiteLLM cannot retry a streaming call (the response object is returned before the stream is consumed). The parameter is silently ignored.

**Why it happens:** LiteLLM's retry mechanism wraps the full `acompletion()` call, but streaming returns an object before the stream is consumed — retry semantics are undefined at that boundary.

**How to avoid:** Never pass `num_retries` with `stream=True`. Implement all retry / fallback logic in `CircuitBreaker`. [VERIFIED: AI-SPEC Section 3, Pitfall 5]

### Pitfall 4: Archetype Collapse at Extreme Win Probabilities

**What goes wrong:** When `win_probability` is very high (>0.90) or very low (<0.10), all archetypes converge on the obvious action (raise with nuts, fold with air). Gunslinger and Rock become indistinguishable to viewers.

**Why it happens:** At extremes, the LLM's training on "correct" poker play overrides persona instructions. The code-level bias in `_fallback_action()` also converges at extremes because both Gunslinger `raise_freq` and Rock `hand_looseness` thresholds are exceeded/undercut.

**How to avoid:** Archetype bias thresholds should be tuned so they differ significantly in the 0.3–0.7 win probability band (the interesting region). Gunslinger should raise at ≥0.4, Rock should call at ≥0.65. The LLM system prompt should include explicit behavioral guidance that persists even with strong hands: "Even with the nuts, the Gunslinger slow-plays to trap; the Rock always bets for value."

**Warning signs:** Archetype raise rate delta (Gunslinger raise% - Rock raise%) falls below 15pp in a 10-hand session.

### Pitfall 5: SSE Stream Routing Conflict — Two Event Types, One Queue

**What goes wrong:** `stream.py` currently puts all broker messages into `event: game_state`. If `publish_reasoning()` publishes to the same Redis channel, all reasoning events would be emitted as `event: game_state`, which the frontend does not handle (it expects `event: reasoning`).

**Why it happens:** The existing `run_subscriber()` subscribes to one channel and broadcasts all messages without tagging.

**How to avoid:** Use a dedicated second Redis channel (`"game:reasoning"`) for reasoning events. Extend `EventBroker` to subscribe to multiple channels, tagging each message with its source channel. In `stream.py`, emit `event="reasoning"` for reasoning messages and `event="game_state"` for game state messages.

### Pitfall 6: `_make_players()` Replacement Must Preserve `GameSession` Contract

**What goes wrong:** `session.py` calls `_make_players()` in `__init__` and stores the result in `self.players`. If the replacement function returns different field types (e.g., `litellm_model` as an extra field not in the Pydantic `Player` model), the game engine will raise `ValidationError` or silently ignore the field.

**Why it happens:** `Player` Pydantic model does not have a `litellm_model` field (models.py lines 51-67). The `litellmModel` from `models.config.json` must be stored separately (e.g., in a parallel dict keyed by player id, or in a subclass of `Player`).

**How to avoid:** Store `litellm_model` in a separate `player_models: dict[str, str]` on `GameSession` (keyed by `player.id`). The `DecisionFn` closure captures this dict and uses it for routing LLM calls.

---

## Code Examples

### Streaming Decision Call with Timeout and Fallback

```python
# Source: AI-SPEC Section 4, verified against codebase models.py + game.py
# backend/app/ai/decision.py

import asyncio, re, json, logging
from litellm import acompletion
from litellm.exceptions import APITimeoutError, RateLimitError, APIError, BadRequestError

from app.engine.models import Action, ActionType  # ActionType is Literal, not Enum

_JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
INDIVIDUAL_TIMEOUT_S = 2.0

async def call_llm_streaming(
    model: str,
    system_prompt: str,
    user_prompt: str,
    player_id: str,
    phase: str,
    redis_client,
) -> str | None:
    """Returns raw response text or None on any failure."""
    try:
        stream = await asyncio.wait_for(
            acompletion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                stream=True,
                max_tokens=300,
                temperature=0.7,
                timeout=INDIVIDUAL_TIMEOUT_S,  # HTTP-level cleanup
            ),
            timeout=INDIVIDUAL_TIMEOUT_S,      # asyncio hard wall
        )
    except (asyncio.TimeoutError, APITimeoutError, RateLimitError, APIError, BadRequestError) as exc:
        logging.warning("LLM call failed [%s]: %s", model, exc)
        return None

    full_text = ""
    async for chunk in stream:
        if delta := chunk.choices[0].delta.content:   # None guard (Pitfall 2)
            full_text += delta
            await publish_reasoning(redis_client, player_id, phase, delta, done=False)

    await publish_reasoning(redis_client, player_id, phase, "", done=True)
    return full_text
```

### Action Construction (Correct Field Name)

```python
# Source: codebase audit backend/app/engine/models.py lines 38-44
# CORRECT — field is "action_type", ActionType is a Literal string union
from app.engine.models import Action

fold_action  = Action(action_type="fold")
call_action  = Action(action_type="call", amount=40)
raise_action = Action(action_type="raise", amount=120)
check_action = Action(action_type="check")
```

### Archetype Config Structure

```python
# Source: CONTEXT.md D-09 — data-driven, adding archetype = config entry only
# backend/app/ai/archetypes.py
from dataclasses import dataclass
from typing import Optional
import random

@dataclass(frozen=True)
class Archetype:
    name: str
    description: str          # used in system prompt
    hand_looseness: float     # min win_probability to stay in hand (call threshold)
    raise_freq: float         # min win_probability to raise
    bluff_freq: float         # probability of bluffing (raise regardless of hand)
    tilt_threshold: float     # future: triggers "tilt" behavior after losses

ARCHETYPES: list[Archetype] = [
    Archetype("Gunslinger",      "Aggressive raiser who applies maximum pressure and never backs down", 0.30, 0.40, 0.15, 0.80),
    Archetype("Rock",            "Tight folder who only commits chips with premium holdings",          0.65, 0.80, 0.02, 0.95),
    Archetype("Grinder",         "Tight-solid player who values position and pot odds",               0.55, 0.65, 0.05, 0.90),
    Archetype("Chaotic Optimist","Calls anything; believes every hand is a winner",                   0.10, 0.35, 0.20, 0.50),
]

def assign_archetypes(players: list) -> dict[str, Archetype]:
    """Random shuffle — each player gets a unique archetype (D-08)."""
    shuffled = ARCHETYPES[:]
    random.shuffle(shuffled)
    return {player.id: arch for player, arch in zip(players, shuffled)}
```

### BudgetTracker and CircuitBreaker

```python
# Source: AI-SPEC Section 4b.5 — verified against project patterns
# backend/app/ai/budget.py
from dataclasses import dataclass, field
from collections import defaultdict
import logging

@dataclass
class BudgetTracker:
    _spend: float = 0.0
    _tokens: dict = field(default_factory=lambda: defaultdict(int))
    _COST_PER_TOKEN: dict = field(default_factory=lambda: {
        "openai": 0.0000004, "gemini": 0.00000004,
        "deepseek": 0.00000028, "xai": 0.000001,
    })

    def record(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        provider = model.split("/")[0]
        rate = self._COST_PER_TOKEN.get(provider, 0.000001)
        self._spend += (prompt_tokens + completion_tokens) * rate
        self._tokens[provider] += prompt_tokens + completion_tokens

    @property
    def total_spend(self) -> float:
        return self._spend

    def summary(self) -> dict:
        return {"total_usd": round(self._spend, 6), "tokens_by_provider": dict(self._tokens)}


@dataclass
class CircuitBreaker:
    threshold: int = 3
    _errors: dict = field(default_factory=lambda: defaultdict(int))
    _open: set = field(default_factory=set)

    def record_error(self, model: str) -> None:
        self._errors[model] += 1
        if self._errors[model] >= self.threshold:
            self._open.add(model)
            logging.error("CircuitBreaker OPEN for %s after %d consecutive errors", model, self.threshold)

    def record_success(self, model: str) -> None:
        self._errors[model] = 0  # reset only consecutive streak

    def is_open(self, model: str) -> bool:
        return model in self._open
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded player list in session.py | Config-driven from models.config.json | Phase 4 (quick task already done) | Player roster is a config concern, not a code concern |
| Phase-transition-only broadcast | Per-action broadcast (D-03 relaxes D-06) | Phase 4 | Viewers see live chip movements during a betting round |
| Mock decision (always call) | LLM-driven decision with streaming + fallback | Phase 4 | Game is now a real AI spectacle |

**Deprecated/outdated:**
- `session.py._make_players()`: Replaced by config-driven init in Phase 4. Function body changes but signature of `GameSession` remains backward-compatible for tests.
- `GameState.reasoning: list` (untyped): Becomes `list[ReasoningEntry]` in Phase 4.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python / uv | All backend tasks | Yes | Python via uv | — |
| litellm | LLM calls | Yes | 1.83.14 [VERIFIED] | — |
| pydantic | Model validation | Yes | 2.12.5 [VERIFIED] | — |
| redis.asyncio | publish_reasoning() | Yes (Phase 3 wired) | >=7.4.0 | — |
| pytest-asyncio | Async tests | Yes | 1.3.0 [VERIFIED] | — |
| Node.js + npm | promptfoo eval CI | Assumed (Next.js already present) | unknown | Skip promptfoo; use pytest-only eval |
| arize-phoenix | LLM call tracing | Not verified | — | Skip tracing; use logging only |
| API keys (OpenAI, Google, DeepSeek, xAI) | Live LLM calls | Required at runtime | — | Mock in tests; skip in CI without keys |

**Missing dependencies with no fallback:**
- API keys for all 4 providers must be in `.env` for end-to-end testing. Unit tests must use `unittest.mock` to avoid real calls.

**Missing dependencies with fallback:**
- arize-phoenix: Can skip for Phase 4; pure logging in `decision.py` is sufficient for debugging.
- promptfoo: Can skip; pytest tests cover critical automated checks; promptfoo is a bonus eval layer.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `calculate_equity()` is called at decision time and takes <100ms for 1000 simulations with a partial board | Architecture Patterns | If too slow, would bloat per-decision latency beyond the 2s timeout; may need `n_simulations=200` |
| A2 | The `game:reasoning` Redis channel can be added without changes to `EventBroker` beyond subscribing to a second channel | Architecture Patterns / Pitfall 5 | If EventBroker only supports one channel subscription, more significant refactor needed |
| A3 | `models.config.json` `id` values (`"gpt4"`, `"gemini"`, `"deepseek"`, `"grok"`) match `ModelId` in `constants.ts` | Standard Stack | If they diverge, `ReasoningEntry.player_id` would not match frontend's `ModelId` type and reasoning would silently fail to render |
| A4 | The `pot_odds` field from `calculate_equity()` returns `None` (not a computed value) — the prompt builder must compute it as `call_amount / (pot + call_amount)` | Code Examples | If misunderstood, pot_odds would be absent from LLM prompt, violating AI-03 |
| A5 | Archetype bias thresholds (raise_freq, hand_looseness values) in the Code Examples section produce measurable behavioral differentiation in a 10-hand session | Common Pitfalls | If thresholds are too similar, SC-2 (Gunslinger raises 2x more than Rock) will fail |

---

## Open Questions

1. **How to expose betting state to `prompt.py`?**
   - What we know: `valid_actions()` requires `BettingRoundState`; `GameState` does not contain it
   - What's unclear: Whether Pattern 2 (reconstruct from max player bet) is sufficient accuracy, or whether `current_bet` should be added to `GameState`
   - Recommendation: Add `current_bet: int = 0` to `GameState` in `models.py` and populate it in `run_betting_round()`. This is one field change, keeps the prompt accurate, and is worth the small models.py touch.

2. **How to multiplex two event types through the SSE broker queue?**
   - What we know: `stream.py` currently hardcodes `event="game_state"`; a second channel needs routing
   - What's unclear: Whether to use a second Redis channel + second broker queue, or a message envelope with `eventType`
   - Recommendation: Message envelope `{"event": "reasoning"|"game_state", "data": "..."}` in the queue string. Simpler than two separate subscriptions; one queue per client; `stream.py` unpacks the envelope and sets `event=` accordingly.

3. **Should `ReasoningEntry` be appended to `GameState.reasoning` during streaming?**
   - **STATUS: RESOLVED** — implemented in Plan 03 Task 2 (`_append_reasoning_to_state()` helper).
   - What we know: Frontend's `GameState.reasoning: ReasoningEntry[]` is broadcast via `event: game_state`. But `event: reasoning` sends deltas separately.
   - Resolution: After each player decision (LLM success or any fallback path), `_append_reasoning_to_state()` builds a finalized `ReasoningEntry(streaming=False, action=..., amount=...)` and appends it to `game_state.reasoning`. The `publish()` call in `game_loop.py` fires AFTER `decision_fn()` returns, so the Redis snapshot captures the completed entry. Late-joining viewers see all reasoning via the SNAPSHOT_KEY. All four return paths in `llm_decision_fn` call this helper before returning.

---

## Project Constraints (from CLAUDE.md)

- **Never run a game without a viewer** — demand-triggered loop is a hard budget constraint (Phase 6 enforces; Phase 4 loop still runs unconditionally per current game_loop.py)
- **Math in code, not LLMs** — hand strength, pot odds, win probability computed in `poker_math.py` and fed to LLM as structured context (enforced by AI-03)
- **Models are config-driven** — `models.config.json` is source of truth; no model strings hardcoded in `decision.py`
- **No side pots in v1** — no impact on Phase 4
- **Read `node_modules/next/dist/docs/`** before writing any Next.js code — Phase 4 is Python-only; this constraint applies to Phase 5
- **VPS only deployment** — SSE + persistent async loops are compatible; no serverless constraints

---

## Sources

### Primary (HIGH confidence)
- `backend/app/engine/models.py` — `Action`, `ActionType`, `DecisionFn`, `GameState`, `Player`, `BettingRoundState` — exact field names and types verified by reading source
- `backend/app/engine/game.py` — `valid_actions()`, `run_betting_round()`, `mock_decision()` — confirmed `BettingRoundState` isolation
- `backend/app/engine/session.py` — `GameSession._make_players()`, `run()` signature
- `backend/app/broadcast/publisher.py` — existing `publish()` pattern
- `backend/app/api/stream.py` — hardcoded `event="game_state"` confirmed
- `app/_components/types.ts` — `ReasoningEntry` TypeScript interface verified field-by-field
- `models.config.json` — 4 player configs with `litellmModel` strings
- `backend/pyproject.toml` — dependency versions
- LiteLLM installed version: 1.83.14 [VERIFIED via `importlib.metadata`]
- Pydantic installed version: 2.12.5 [VERIFIED via `importlib.metadata`]

### Secondary (MEDIUM confidence)
- docs.litellm.ai/docs/completion/stream — async streaming pattern, `chunk.choices[0].delta.content` nullable [CITED: verified by WebFetch 2026-05-07]
- docs.litellm.ai/docs/exception_mapping — `APITimeoutError`, `RateLimitError`, `APIError`, `BadRequestError`, `InternalServerError` [CITED: verified by WebFetch 2026-05-07]
- `.planning/phases/04-llm-integration/04-AI-SPEC.md` — LiteLLM patterns, BudgetTracker, CircuitBreaker, prompt structure [CITED: from project's own AI-SPEC]
- `.planning/phases/04-llm-integration/04-CONTEXT.md` — all locked decisions D-01 through D-17 [CITED: project context doc]

### Tertiary (LOW confidence)
- Archetype bias threshold values in Code Examples section [ASSUMED] — need tuning against live sessions

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified installed at exact versions
- Architecture: HIGH — all integration points verified by reading source files
- Critical gaps: HIGH — discovered by direct codebase audit, not inferred
- Pitfalls: HIGH — Pitfalls 1-3 from official docs + codebase; Pitfalls 4-6 from code reading
- Archetype thresholds: LOW — assumed values, need empirical tuning

**Research date:** 2026-05-07
**Valid until:** 2026-06-07 (LiteLLM releases frequently; verify `acompletion` streaming API before major changes)
