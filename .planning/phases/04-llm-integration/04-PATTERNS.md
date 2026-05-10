# Phase 4: LLM Integration — Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 10 new/modified files
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/ai/__init__.py` | config | — | `backend/app/broadcast/__init__.py` | role-match |
| `backend/app/ai/archetypes.py` | config/utility | transform | `backend/app/config.py` | role-match |
| `backend/app/ai/decision.py` | service | request-response + streaming | `backend/app/engine/game.py` (`mock_decision`) | partial |
| `backend/app/ai/prompt.py` | utility | transform | `backend/app/engine/poker_math.py` | partial |
| `backend/app/ai/budget.py` | utility | event-driven | `backend/app/broadcast/broker.py` | partial |
| `backend/app/ai/models.py` | model | — | `backend/app/engine/models.py` | exact |
| `backend/app/broadcast/publisher.py` | service | pub-sub | `backend/app/broadcast/publisher.py` (self) | exact (extend) |
| `backend/app/engine/game.py` | service | event-driven | `backend/app/engine/game.py` (self) | exact (modify) |
| `backend/app/engine/session.py` | service | CRUD | `backend/app/engine/session.py` (self) | exact (modify) |
| `backend/app/engine/models.py` | model | — | `backend/app/engine/models.py` (self) | exact (modify) |
| `backend/app/game_loop.py` | service | event-driven | `backend/app/game_loop.py` (self) | exact (modify) |
| `backend/app/api/stream.py` | controller | streaming | `backend/app/api/stream.py` (self) | exact (modify) |
| `backend/tests/test_llm_decision.py` | test | request-response | `backend/tests/test_session.py` + `backend/tests/test_sse.py` | role-match |

---

## Pattern Assignments

### `backend/app/ai/__init__.py` (config, package marker)

**Analog:** `backend/app/broadcast/__init__.py`

**Pattern:** Empty file — package marker only. No imports needed at the `__init__.py` level (consumers import directly from `ai.archetypes`, `ai.decision`, etc.).

```python
# backend/app/broadcast/__init__.py — empty, just a package marker
```

---

### `backend/app/ai/archetypes.py` (config, transform)

**Analog:** `backend/app/config.py`

**Imports pattern** (`config.py` lines 1-8):
```python
import json
import pathlib
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
```

**Config loading pattern** (`config.py` lines 8-13):
```python
_MODELS_CONFIG = pathlib.Path(__file__).parent.parent.parent / "models.config.json"

def _default_player_models() -> list[str]:
    with open(_MODELS_CONFIG) as f:
        return [m["litellmModel"] for m in json.load(f)]
```

**Core pattern for archetypes** — data-driven frozen dataclass + shuffle fn (from RESEARCH.md Pattern 3, verified against D-09):
```python
# backend/app/ai/archetypes.py
from dataclasses import dataclass
import random

@dataclass(frozen=True)
class Archetype:
    name: str
    description: str          # used verbatim in system prompt (D-04)
    hand_looseness: float     # min win_probability to stay in hand
    raise_freq: float         # min win_probability to raise
    bluff_freq: float         # probability of raising regardless of hand
    tilt_threshold: float     # future tilt mechanic (placeholder for v2)

ARCHETYPES: list[Archetype] = [...]   # 4 entries — D-10

def assign_archetypes(players: list) -> dict[str, Archetype]:
    """Random shuffle — unique archetype per player (D-08)."""
    shuffled = ARCHETYPES[:]
    random.shuffle(shuffled)
    return {player.id: arch for player, arch in zip(players, shuffled)}
```

---

### `backend/app/ai/models.py` (model, Pydantic)

**Analog:** `backend/app/engine/models.py`

**Imports pattern** (`engine/models.py` lines 1-20):
```python
from __future__ import annotations
from typing import Callable, Awaitable, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
```

**Pydantic model with camelCase aliasing** (`engine/models.py` lines 51-67, Player):
```python
class Player(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    name: str
    # ...snake_case fields that become camelCase in JSON via by_alias=True
```

**Core pattern — ReasoningEntry model** (must match `app/_components/types.ts` lines 21-29 exactly):
```python
# ReasoningEntry TypeScript interface for reference:
#   id: string
#   playerId: ModelId
#   text: string
#   phase: string
#   streaming: boolean
#   action: ActionType | null
#   amount: number

import uuid
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

class ReasoningEntry(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_id: str           # → "playerId" in JSON
    text: str = ""
    phase: str
    streaming: bool = True
    action: Optional[Literal["fold", "call", "raise", "check"]] = None
    amount: int = 0
```

**Serialization:** `entry.model_dump(by_alias=True)` — same pattern as `GameState.model_dump_json(by_alias=True)` in `publisher.py` line 32.

**LLMDecisionResponse model** (for parsing the fenced JSON block from the LLM — D-06):
```python
class LLMDecisionResponse(BaseModel):
    action: Literal["fold", "call", "raise", "check"]
    amount: int = 0
    reasoning: str = ""
```

---

### `backend/app/ai/decision.py` (service, request-response + streaming)

**Analog:** `backend/app/engine/game.py` (`mock_decision`, lines 499-514)

**DecisionFn signature to preserve** (`engine/models.py` line 107):
```python
DecisionFn = Callable[[Player, GameState], Awaitable[Action]]
# Signature: async def make_decision(player: Player, game_state: GameState) -> Action
```

**Analog — mock_decision pattern** (`game.py` lines 499-514):
```python
async def mock_decision(player: Player, game_state: GameState) -> Action:
    """Mock DecisionFn — Phase 4 replaces with LLM calls, zero refactor needed."""
    max_bet = max(
        (p.bet for p in game_state.players if not p.is_folded),
        default=0
    )
    if player.bet >= max_bet:
        return Action(action_type="check")
    return Action(action_type="call")
```

**Valid actions reconstruction pattern** (`game.py` lines 508-514 — `mock_decision` reconstructs current state from `GameState.players`):
```python
# Pattern for reconstructing current_bet without BettingRoundState:
max_bet = max(
    (p.bet for p in game_state.players if not p.is_folded),
    default=0
)
call_amount = max(0, max_bet - player.bet)
can_raise = player.chips > call_amount
```

**Action construction — correct field name** (`engine/models.py` lines 41-44):
```python
# ActionType = Literal['fold', 'call', 'raise', 'check']  — NOT an Enum
# Field is "action_type", NOT "type"
action = Action(action_type="raise", amount=120)
action = Action(action_type="fold")    # amount defaults to 0
action = Action(action_type="call")
action = Action(action_type="check")
```

**Closure factory pattern** (`game_loop.py` lines 47-48 — `partial` to bind context):
```python
# Existing pattern: partial binds redis_client
broadcast_fn = partial(publish, redis_client)

# Phase 4 adaptation: closure factory binds archetype + budget + circuit into DecisionFn
def make_llm_decision_fn(archetypes, redis_client, budget, circuit):
    async def llm_decision_fn(player: Player, game_state: GameState) -> Action:
        ...
    return llm_decision_fn
```

**Error handling pattern** (`game_loop.py` lines 55-64):
```python
except asyncio.CancelledError:
    logger.info("Game loop cancelled — shutting down")
    raise  # propagate — do NOT swallow CancelledError

except Exception as exc:
    logger.error("Game loop error (will retry): %s", exc, exc_info=True)
    await asyncio.sleep(settings.hand_delay_seconds)
```

**LiteLLM streaming call pattern** (from RESEARCH.md Code Examples, verified against installed litellm 1.83.14):
```python
import asyncio, re, json, logging
from litellm import acompletion
from litellm.exceptions import APITimeoutError, RateLimitError, APIError, BadRequestError

_JSON_FENCE_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
INDIVIDUAL_TIMEOUT_S = 2.0

# None guard on delta — first and last chunks have content=None (Pitfall 2)
async for chunk in stream:
    if delta := chunk.choices[0].delta.content:
        full_text += delta
        await publish_reasoning(redis_client, player_id, phase, delta, done=False)
```

---

### `backend/app/ai/prompt.py` (utility, transform)

**Analog:** `backend/app/engine/poker_math.py` (pure function module, no side effects)

**Module structure pattern** (`poker_math.py` lines 1-27):
```python
"""
poker_math.py — thin wrapper around treys for hand evaluation and equity calculation.
[docstring explaining module purpose and key caveats]
"""
# imports
_evaluator = Evaluator()  # single instance at module level

def function_name(arg1: type, arg2: type) -> dict:
    """
    Docstring explaining args and return shape.
    """
    ...
    return {"key": value, ...}
```

**Pure function signature pattern for prompt builder:**
```python
# backend/app/ai/prompt.py
def build_system_prompt(player_name: str, player_org: str, archetype: Archetype) -> str:
    """Build system message: identity + archetype persona (D-04)."""
    ...

def build_user_prompt(
    player: Player,
    game_state: GameState,
    math_ctx: dict,          # from poker_math.calculate_equity()
    valid_actions_ctx: dict, # from reconstruct_valid_actions()
) -> str:
    """Build user message: current-hand context only, no cross-hand memory (D-05)."""
    ...
```

**Math context from poker_math.py** (`poker_math.py` lines 55-118):
```python
# calculate_equity() returns:
{
    "hand_strength": int | None,   # None if pre-flop (< 3 community cards)
    "win_probability": float,      # 0.0-1.0
    "pot_odds": None,              # MUST be computed by caller: call_amount / (pot + call_amount)
}
# NOTE: pot_odds is always None from calculate_equity() — prompt builder must compute it
```

---

### `backend/app/ai/budget.py` (utility, event-driven)

**Analog:** `backend/app/broadcast/broker.py` (stateful background service class with dataclass-style state)

**Class structure pattern** (`broker.py` lines 18-35):
```python
class EventBroker:
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._message_id: int = 0

    def next_id(self) -> int:
        """Single method, single responsibility, clear docstring."""
        self._message_id += 1
        return self._message_id
```

**BudgetTracker and CircuitBreaker pattern** (from RESEARCH.md Code Examples, dataclass pattern matching `engine/models.py` `BettingRoundState`):
```python
# engine/models.py lines 91-100 — dataclass pattern:
@dataclass
class BettingRoundState:
    current_bet: int
    last_raise_size: int
    aggressor_seat: int
    has_acted: set = field(default_factory=set)

# budget.py follows same dataclass pattern:
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class BudgetTracker:
    _spend: float = 0.0
    _tokens: dict = field(default_factory=lambda: defaultdict(int))

@dataclass
class CircuitBreaker:
    threshold: int = 3
    _errors: dict = field(default_factory=lambda: defaultdict(int))
    _open: set = field(default_factory=set)
```

**Logging pattern** (`broker.py` lines 15-16, `game_loop.py` lines 27-28):
```python
import logging
logger = logging.getLogger(__name__)

# Usage:
logger.error("CircuitBreaker OPEN for %s after %d consecutive errors", model, threshold)
logger.info("Session spend: %s", budget.summary())
```

---

### `backend/app/broadcast/publisher.py` — EXTEND (add `publish_reasoning`)

**Analog:** `backend/app/broadcast/publisher.py` (self — extend with new function)

**Existing publish() pattern** (lines 24-36) — new `publish_reasoning()` follows identical structure:
```python
CHANNEL = "game:state"
SNAPSHOT_KEY = "game:state:last"
SNAPSHOT_TTL = 3600

async def publish(redis_client: redis.Redis, state: GameState) -> None:
    payload = state.model_dump_json(by_alias=True)  # camelCase JSON
    await redis_client.set(SNAPSHOT_KEY, payload, ex=SNAPSHOT_TTL)
    await redis_client.publish(CHANNEL, payload)
    logger.debug("Published game state (phase=%s, payload_len=%d)", state.phase, len(payload))
```

**New function to add** (same module, follows same pattern):
```python
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
    logger.debug("Published reasoning delta (player=%s, done=%s)", player_id, done)
```

**Note:** `publish_reasoning()` does NOT set a snapshot key — reasoning is ephemeral. Late joiners see completed `ReasoningEntry` objects in the `game_state` snapshot's `reasoning` array.

---

### `backend/app/engine/models.py` — MODIFY (add `current_bet` to GameState, type `reasoning`)

**Analog:** `backend/app/engine/models.py` (self — two targeted additions)

**GameState model** (lines 73-84) — two changes needed:
```python
class GameState(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    phase: str
    pot: int
    community_cards: list[Card] = Field(default_factory=list)
    players: list[Player] = Field(default_factory=list)
    show_cards: bool = False
    # CHANGE 1: Type from `list` to `list[ReasoningEntry]`
    reasoning: list = Field(default_factory=list)   # → list[ReasoningEntry]
    winner: Optional[int] = None
    winner_hand: str = ""
    # CHANGE 2: Add current_bet for valid action reconstruction (RESEARCH.md Open Question 1)
    current_bet: int = 0    # → "currentBet" in JSON
```

**Import to add at top of models.py:**
```python
# Add after existing imports — ReasoningEntry defined in ai/models.py
# Use TYPE_CHECKING to avoid circular import:
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.ai.models import ReasoningEntry
```

---

### `backend/app/engine/game.py` — MODIFY (broadcast after each player action, D-03)

**Analog:** `backend/app/engine/game.py` (self — targeted modification to `run_betting_round`)

**Existing broadcast pattern** (`game.py` lines 268-275, `_maybe_broadcast`):
```python
async def _maybe_broadcast(state: GameState, broadcast_fn: Optional[BroadcastFn]) -> None:
    """Call broadcast_fn if provided. No-op when fn is None (Phase 2 tests unaffected)."""
    if broadcast_fn is not None:
        await broadcast_fn(state)
```

**Existing call sites** (lines 355, 381, 403, 425, 471) — all at phase transitions. Phase 4 D-03 requires adding `await _maybe_broadcast(game_state, broadcast_fn)` AFTER EACH player action decision inside `run_betting_round()` (line 147 onwards), not just at phase boundaries.

**BroadcastFn type** (`game.py` — search for its definition):
```python
BroadcastFn = Callable[[GameState], Awaitable[None]]
```

---

### `backend/app/engine/session.py` — MODIFY (`_make_players` replaced)

**Analog:** `backend/app/engine/session.py` (self — replace `_make_players`)

**Current `_make_players`** (lines 26-38) — replace with config-driven init:
```python
def _make_players(n_players: int, starting_chips: int) -> list[Player]:
    """Create mock player roster for Phase 2. Phase 4 replaces with LLM-backed players."""
    return [
        Player(
            id=f'player-{i}',
            name=f'Player {i}',
            org='mock',
            color='gray',
            deck='default',
            chips=starting_chips,
        )
        for i in range(n_players)
    ]
```

**Config loading pattern from `config.py`** (lines 8-13):
```python
_MODELS_CONFIG = pathlib.Path(__file__).parent.parent.parent / "models.config.json"

def _default_player_models() -> list[str]:
    with open(_MODELS_CONFIG) as f:
        return [m["litellmModel"] for m in json.load(f)]
```

**`models.config.json` fields** (all 4 entries have): `id`, `name`, `org`, `color`, `deck`, `litellmModel`, `stake`. The `Player` model accepts `id`, `name`, `org`, `color`, `deck`, `chips`. The `litellmModel` field must NOT be passed to `Player()` — store separately on `GameSession`.

**Player construction from config** (D-13 pattern):
```python
import json, pathlib

_MODELS_CONFIG = pathlib.Path(__file__).parent.parent.parent / "models.config.json"

def _load_players_from_config(starting_chips: int) -> tuple[list[Player], dict[str, str]]:
    """
    Returns (players, player_models) where player_models maps player.id → litellmModel.
    Separation prevents litellmModel from leaking into Player Pydantic model (Pitfall 6).
    """
    with open(_MODELS_CONFIG) as f:
        configs = json.load(f)
    players = [
        Player(
            id=cfg["id"],
            name=cfg["name"],
            org=cfg["org"],
            color=cfg["color"],
            deck=cfg["deck"],
            chips=starting_chips,
        )
        for cfg in configs
    ]
    player_models = {cfg["id"]: cfg["litellmModel"] for cfg in configs}
    return players, player_models
```

---

### `backend/app/game_loop.py` — MODIFY (wire LLM decision fn + BudgetTracker)

**Analog:** `backend/app/game_loop.py` (self — targeted additions)

**Current game loop pattern** (lines 30-64) — the structure to extend:
```python
async def run_game_loop(redis_client: redis_asyncio.Redis, settings: Settings) -> None:
    logger.info("Game loop started (hand_delay=%ds)", settings.hand_delay_seconds)

    while True:
        try:
            session = GameSession(n_players=4, starting_chips=1000, big_blind=20)
            broadcast_fn = partial(publish, redis_client)

            logger.info("Starting new GameSession (10 hands)")
            await session.run(n_hands=10, broadcast_fn=broadcast_fn)
            logger.info("GameSession complete — waiting %ds...", settings.hand_delay_seconds)
            await asyncio.sleep(settings.hand_delay_seconds)

        except asyncio.CancelledError:
            logger.info("Game loop cancelled — shutting down")
            raise  # MUST re-raise — never swallow CancelledError

        except Exception as exc:
            logger.error("Game loop error (will retry): %s", exc, exc_info=True)
            await asyncio.sleep(settings.hand_delay_seconds)
```

**New imports to add** (following existing import style at lines 19-26):
```python
from app.ai.decision import make_llm_decision_fn
from app.ai.archetypes import assign_archetypes
from app.ai.budget import BudgetTracker, CircuitBreaker
```

**LLM decision fn wiring** (closure factory pattern — D-14):
```python
# Inside while True, after session = GameSession(...)
budget = BudgetTracker()
circuit = CircuitBreaker()
archetypes = assign_archetypes(session.players)

decision_fn = make_llm_decision_fn(
    archetypes=archetypes,
    redis_client=redis_client,
    budget=budget,
    circuit=circuit,
    player_models=session.player_models,  # dict[player_id, litellm_model_str]
)
await session.run(n_hands=10, decision_fn=decision_fn, broadcast_fn=broadcast_fn)
logger.info("Session spend: %s", budget.summary())  # D-15
```

---

### `backend/app/api/stream.py` — MODIFY (route `event: reasoning` events)

**Analog:** `backend/app/api/stream.py` (self — extend SSE generator)

**Current hardcoded event type** (lines 55-65):
```python
# Step 3: Drain live events; check disconnect on each iteration
while True:
    if await request.is_disconnected():
        break
    try:
        data: str = await asyncio.wait_for(queue.get(), timeout=1.0)
        yield ServerSentEvent(
            raw_data=data,
            event="game_state",    # ← hardcoded, must become dynamic
            id=str(broker.next_id()),
        )
    except asyncio.TimeoutError:
        continue
```

**Message envelope approach** (RESEARCH.md Open Question 2, recommended solution):
```python
# broker.py: when broadcasting reasoning events, publisher wraps with event type tag:
# {"event": "reasoning", "data": "<json string>"}
# {"event": "game_state", "data": "<json string>"}
# stream.py unpacks the envelope:

import json

data: str = await asyncio.wait_for(queue.get(), timeout=1.0)
try:
    envelope = json.loads(data)
    event_type = envelope.get("event", "game_state")
    payload = envelope.get("data", data)
except (json.JSONDecodeError, KeyError):
    event_type = "game_state"
    payload = data

yield ServerSentEvent(
    raw_data=payload,
    event=event_type,
    id=str(broker.next_id()),
)
```

**Snapshot event type** (line 49-54) — snapshot is always `event: game_state`, no change needed:
```python
yield ServerSentEvent(
    raw_data=snapshot.decode("utf-8"),
    event="game_state",
    id=str(broker.next_id()),
)
```

**main.py subscriber task** (lines 51-55) — must be extended to also subscribe to `"game:reasoning"` channel. Broker `run_subscriber` currently takes one channel; may need second task or multi-channel support:
```python
# Current (lines 51-55):
app.state.subscriber_task = asyncio.create_task(
    app.state.broker.run_subscriber(
        app.state.redis_client, channel="game:state"
    )
)
# Phase 4 addition: second subscriber task for reasoning channel
app.state.reasoning_task = asyncio.create_task(
    app.state.broker.run_subscriber(
        app.state.redis_client, channel="game:reasoning"
    )
)
```

---

### `backend/tests/test_llm_decision.py` (test, request-response)

**Analog:** `backend/tests/test_session.py` + `backend/tests/test_sse.py`

**Test module header pattern** (`test_session.py` lines 1-18):
```python
"""
test_session.py — TDD tests for backend/app/engine/session.py

Test coverage:
  SC1 - [description]
  SC2 - [description]
  ...
"""
import asyncio
import pytest
from app.engine.session import GameSession
from app.engine.models import GameState, Action, Player
```

**Async test pattern** (`test_sse.py` lines 92-107):
```python
@pytest.mark.asyncio
async def test_snapshot_sent_on_connect(self, inject_stubs):
    """STREAM-02: Late joiner receives snapshot as the first SSE event."""
    redis = inject_stubs.state.redis_client
    snapshot = await redis.get(SNAPSHOT_KEY)
    assert snapshot is not None
```

**Stub/mock injection pattern** (`test_sse.py` lines 36-71):
```python
class StubRedis:
    """Minimal Redis stub: returns preset snapshot, no-ops for everything else."""
    def __init__(self, snapshot: bytes | None = None) -> None:
        self._snapshot = snapshot

    async def get(self, key: str) -> bytes | None:
        return self._snapshot

    async def publish(self, channel: str, message: str) -> None:
        pass

@pytest.fixture
def inject_stubs():
    # Inject stubs so no real Redis or LLM calls are made
    ...
```

**LiteLLM mock pattern** (`test_litellm_providers.py` lines 36-51) — use `unittest.mock.patch` or `pytest.mark.skipif` for tests requiring API keys:
```python
@pytest.mark.skipif(
    not _TEST_MODEL,
    reason="No test model configured — set LITELLM_TEST_MODEL or PLAYER_MODELS",
)
def test_litellm_connectivity():
    ...
```

**Custom decision fn helper** (`test_session.py` lines 31-34):
```python
async def always_fold(player: Player, game_state: GameState) -> Action:
    """Custom decision fn: always folds — tests decision_fn parameter acceptance."""
    return Action(action_type="fold")
```

**Class-per-scenario structure** (`test_session.py` lines 40-253):
```python
class TestFallbackOnTimeout:
    """decision.py: fallback fires when asyncio.wait_for raises TimeoutError."""

    @pytest.mark.asyncio
    async def test_timeout_returns_action(self):
        ...

class TestFallbackOnBadJSON:
    """decision.py: fallback fires when LLM returns non-JSON text."""

    @pytest.mark.asyncio
    async def test_bad_json_returns_action(self):
        ...

class TestCircuitBreaker:
    """budget.py: 3 consecutive errors opens the circuit."""

    def test_circuit_opens_after_threshold(self):
        ...
```

---

## Shared Patterns

### Async Safety — Never Swallow CancelledError

**Source:** `backend/app/game_loop.py` lines 55-58
**Apply to:** `decision.py` (all try/except blocks around `acompletion`), `game_loop.py` modifications
```python
except asyncio.CancelledError:
    raise  # always re-raise — never swallow shutdown signal
```

### Logging Convention

**Source:** `backend/app/broadcast/broker.py` lines 15-16, `backend/app/game_loop.py` lines 27-28
**Apply to:** All new `ai/` module files
```python
import logging
logger = logging.getLogger(__name__)
# Usage: logger.warning("msg [%s]: %s", context_val, exc)
# Usage: logger.info("msg (%s=%d)", key, val)
```

### Pydantic camelCase Serialization

**Source:** `backend/app/engine/models.py` lines 51-54
**Apply to:** `ai/models.py` (`ReasoningEntry`)
```python
model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
# Serialize: model.model_dump(by_alias=True) → camelCase JSON
# Deserialize: Model(snake_case_field=val) or Model(**camelCase_dict) both work
```

### Redis Publish Pattern

**Source:** `backend/app/broadcast/publisher.py` lines 24-36
**Apply to:** New `publish_reasoning()` in `publisher.py`
```python
async def publish(redis_client: redis.Redis, ...) -> None:
    payload = ...  # JSON string
    await redis_client.publish(CHANNEL, payload)
    logger.debug("Published ... (key=%s, len=%d)", key_val, len(payload))
```

### Action Construction (Critical)

**Source:** `backend/app/engine/models.py` lines 38-44
**Apply to:** `ai/decision.py` (all Action instantiation — fallback and parsed responses)
```python
# ActionType = Literal['fold', 'call', 'raise', 'check']  ← NOT an Enum
# Field is "action_type", NOT "type"
Action(action_type="fold")           # ✓ correct
Action(action_type="raise", amount=80)  # ✓ correct
# Action(type=ActionType.RAISE, amount=80)  ← WRONG — will raise ValidationError
```

### pytest-asyncio Configuration

**Source:** `backend/tests/test_sse.py` (uses `@pytest.mark.asyncio`), `backend/pyproject.toml`
**Apply to:** `tests/test_llm_decision.py` — all async test methods
```python
@pytest.mark.asyncio
async def test_something():
    ...
# Note: asyncio_mode = "strict" is already configured in pyproject.toml
```

### JSON + Redis Publish for Non-Pydantic Payloads

**Source:** `backend/app/broadcast/publisher.py` uses `model_dump_json(by_alias=True)`. For dict payloads (like reasoning delta), use `json.dumps()` with camelCase keys directly:
```python
import json
payload = json.dumps({
    "playerId": player_id,   # camelCase to match types.ts contract
    "phase": phase,
    "delta": delta,
    "done": done,
})
await redis_client.publish(CHANNEL, payload)
```

---

## No Analog Found

All files have analogs. No new technology patterns are introduced without a codebase reference — LiteLLM is already used in `backend/tests/test_litellm_providers.py`.

| File | Note |
|------|------|
| `backend/app/ai/prompt.py` | Closest analog is `poker_math.py` (pure transform module) — prompt assembly is simpler, no library required |
| `backend/app/ai/decision.py` (streaming) | `acompletion` streaming pattern has no existing analog in production code (only sync `completion` in `test_litellm_providers.py`) — use RESEARCH.md Code Examples (verified against litellm 1.83.14 docs) |

---

## Critical Gaps (Must Not Miss)

These are **not** pattern gaps — they are correctness constraints the planner must enforce in every task that touches the affected files:

1. **`Action` field name:** Always `action_type`, never `type`. `ActionType` is `Literal`, not `Enum`. Source: `engine/models.py` lines 38-44.

2. **`valid_actions()` not callable from `decision.py`:** `BettingRoundState` is local to `run_betting_round()` and not in `GameState`. Use `max(p.bet for p in game_state.players if not p.is_folded)` pattern from `mock_decision` (game.py lines 508-511). Alternative: add `current_bet: int = 0` to `GameState` and populate in `run_betting_round()` (RESEARCH.md recommendation).

3. **`litellmModel` must not reach `Player.__init__`:** `Player` Pydantic model has no `litellmModel` field — passing it raises `ValidationError`. Store as separate `player_models: dict[str, str]` on `GameSession`. Source: `engine/models.py` lines 51-67.

4. **`pot_odds` is always `None` from `calculate_equity()`:** The prompt builder must compute it as `call_amount / (pot + call_amount)`. Source: `poker_math.py` lines 114-118.

5. **`num_retries` silently ignored with `stream=True`:** Never pass `num_retries` to `acompletion()` when streaming. All retry logic belongs in `CircuitBreaker`. Source: RESEARCH.md Pitfall 3.

6. **Reasoning events need broker multi-channel support:** `EventBroker.run_subscriber()` takes one channel. Phase 4 requires subscribing to both `"game:state"` and `"game:reasoning"`. Either run two subscriber tasks or extend `run_subscriber()` to accept a list of channels.

---

## Metadata

**Analog search scope:** `backend/app/`, `backend/tests/`
**Files scanned:** 16 source files, 8 test files
**Pattern extraction date:** 2026-05-07
