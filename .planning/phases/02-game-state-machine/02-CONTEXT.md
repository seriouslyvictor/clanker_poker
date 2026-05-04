# Phase 2: Game State Machine — Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver a complete Texas Hold'em game engine that runs a full hand (and a multi-hand session) from pre-flop through showdown in pure Python — no UI, no LLMs, no SSE, no HTTP. Console output is sufficient for verification. The mock decision function is the only plug-in seam; it is the slot Phase 4 will replace with real LLM calls.

Phase 2 output: a runnable `asyncio`-driven game session that passes all 5 success criteria, including a 10-hand session with dealer rotation and no errors.

</domain>

<decisions>
## Implementation Decisions

### State Model
- **D-01:** Game state is modeled using **Pydantic `BaseModel`** classes throughout — `GameState`, `Player`, `Card`, `Action`. Pydantic is already in the stack (pydantic-settings in Phase 1). `.model_dump()` gives Phase 3 SSE its JSON payload for free with zero additional serialization work. No manual `.to_dict()` step needed.

### Decision Seam (Phase 4 LLM plug-in point)
- **D-02:** The mock decision function uses **`async def`** from day one:
  ```python
  async def make_decision(player: Player, game_state: GameState) -> Action: ...
  ```
  Phase 4 LLM calls are inherently async (LiteLLM `acompletion`). Designing the seam as async now means Phase 4 drops in its implementation with zero refactor. Phase 2 tests use `asyncio.run()` or `pytest-asyncio`.

### Card Format — treys ↔ Frontend Bridge
- **D-03:** **Phase 2 owns the treys-int ↔ `{s, r}` conversion.** Add `backend/app/engine/cards.py` with:
  - `new_card(r: str, s: str) -> int` — creates a treys int from rank+suit strings matching treys notation
  - `card_display(treys_int: int) -> dict` — returns `{"s": "♥", "r": "A"}` matching `types.ts Card`
  - Suit mapping: `♠→s`, `♥→h`, `♦→d`, `♣→c`
  - Rank mapping: `A→A`, `K→K`, ..., `2→2`
  
  `GameState` stores community cards and hole cards as `Card` Pydantic models with `{s, r}` fields. Whenever `poker_math.py` needs treys ints (evaluate/equity), convert at call time. Phase 3 SSE serializes `GameState` and card format is already correct for the browser.

### Session Scope — Multi-Hand with Dealer Rotation
- **D-04:** Phase 2 must support a **multi-hand session with dealer rotation**. ROADMAP SC4 explicitly requires a 10-hand mock session to complete without errors. Each hand:
  - Dealer button rotates one seat clockwise
  - Small blind = seat left of dealer, big blind = seat 2 left of dealer
  - Starting chip stacks carry over between hands (no reset per hand within a session)
  - Stacks reset when a new `GameSession` is initialized

### Raise Sizing
- **D-05 (Claude's Discretion):** Min raise = big blind amount. No cap on raises within a round (standard no-limit). All-in: player bets remaining stack; no side pot (v1 constraint — if a player can't cover, they're treated as called for their stack amount and the excess is returned to the raiser).

### Module Layout
- **D-06 (Claude's Discretion):** New files under `backend/app/engine/`:
  ```
  backend/app/engine/
  ├── poker_math.py     ← existing (Phase 1)
  ├── cards.py          ← new: treys ↔ {s,r} conversion helpers
  ├── models.py         ← new: Pydantic GameState, Player, Card, Action
  ├── game.py           ← new: single-hand engine (deal, betting rounds, showdown)
  └── session.py        ← new: multi-hand session with dealer rotation
  ```
  Tests in `backend/tests/test_game_engine.py`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 2 Requirements
- `.planning/REQUIREMENTS.md` — POKER-01 (Hold'em flow), POKER-02 (action order), POKER-05 (chip tracking)
- `.planning/ROADMAP.md` — Phase 2 success criteria (5 criteria, all must be TRUE)

### Frontend Type Contract
- `app/_components/types.ts` — `GameState`, `Player`, `Card`, `ActionType` TypeScript interfaces. The Python Pydantic models MUST produce JSON that matches these shapes when serialized — Phase 3 SSE feeds directly into these types.

### Existing Engine
- `backend/app/engine/poker_math.py` — `evaluate_hand(hole_cards, community_cards)` and `calculate_equity(...)`. Phase 2 imports these; do not duplicate their logic.

### Phase 1 Context
- `.planning/phases/01-backend-foundation/01-CONTEXT.md` — D-01 to D-06 decisions (directory layout, uv toolchain, treys usage, Monte Carlo equity)

### Architecture Reference
- `.planning/research/ARCHITECTURE.md` — Component map; Phase 2 produces the game engine component

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/engine/poker_math.py` — `evaluate_hand(hole_cards: list[int], community_cards: list[int])` returns `{hand_strength, hand_name}`. `calculate_equity(hole_cards, community_cards, num_opponents, n_simulations)` returns `{hand_strength, win_probability, pot_odds}`. Both take treys card ints.
- `treys.Card`, `treys.Deck`, `treys.Evaluator` — already installed; `Deck().cards` gives full 52-card deck as ints.

### Established Patterns
- Pydantic `BaseSettings` with `@lru_cache` pattern in `config.py` — Pydantic is established; `BaseModel` for game state follows the same style.
- `uv run pytest` from `backend/` — all new tests follow this convention.
- Async FastAPI app in `main.py` — async decision seam fits the existing async context.

### Integration Points
- `backend/app/engine/game.py` + `session.py` are the seam Phase 3 imports to drive the game loop and broadcast state transitions over SSE.
- `backend/app/engine/cards.py` conversion output (`{s, r}`) must match `app/_components/types.ts` `Card = { s: string; r: string }`.

</code_context>

<specifics>
## Specific Requirements

- `Card` Pydantic model: `{s: str, r: str}` — suits as unicode symbols matching the frontend (`♠`, `♥`, `♦`, `♣`)
- `ActionType` values: `"fold"`, `"call"`, `"raise"`, `"check"` — match frontend `ActionType` union exactly
- Decision function signature: `async def make_decision(player: Player, game_state: GameState) -> Action`
- Mock implementation: always calls (or folds with low hand strength) — drives a full session without human input
- 10-hand session verification: `asyncio.run(session.run(n_hands=10))` completes without exception
- No side pots in v1 — all-in treated as partial call, excess returned; single main pot only

</specifics>

<deferred>
## Deferred Ideas

- Pot odds surfacing at decision time — `calculate_equity` returns `pot_odds: None`; the Phase 2 game engine computes call_amount and pot and passes them in the `GameState` context sent to the decision function. Full structured context for LLMs is Phase 4.
- Archetype bias parameters — Phase 4 adds archetype-driven decision biases; Phase 2 mock function is archetype-agnostic.
- Raise history / re-raise tracking beyond minimum — simplified raise logic in v1; full re-raise caps deferred.

</deferred>

---

*Phase: 02-game-state-machine*
*Context gathered: 2026-05-03*
