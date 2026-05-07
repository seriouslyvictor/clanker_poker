# Phase 4: LLM Integration — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-07
**Phase:** 04-llm-integration
**Areas discussed:** Reasoning streaming, LLM prompt structure, Archetype assignment, Fallback behavior

---

## Reasoning Streaming

| Option | Description | Selected |
|--------|-------------|----------|
| New `event: reasoning` | LiteLLM streams tokens → each chunk published as new SSE event type → frontend appends tokens to ReasoningEntry in real-time | ✓ |
| Batch at phase end | Full reasoning text included in next `event: game_state` payload | |

**User's choice:** New `event: reasoning` SSE event type with delta-only payload

| Option | Description | Selected |
|--------|-------------|----------|
| Delta only | Each event: `{ playerId, phase, delta, done }` — frontend appends | ✓ |
| Full accumulated text | Each event carries full text so far — frontend replaces | |

**User's choice:** Delta-only payload

| Option | Description | Selected |
|--------|-------------|----------|
| Broadcast after each action | `event: game_state` after each fold/call/raise/check within a betting round | ✓ |
| Phase transitions only | Keep Phase 3's existing rule | |

**User's choice:** Broadcast after each player action (relaxes Phase 3 D-06)

---

## LLM Prompt Structure

| Option | Description | Selected |
|--------|-------------|----------|
| System + User split | System: identity + archetype persona. User: current-hand context | ✓ |
| Single user message | Everything in one block | |
| System + tool call | Structured output via function calling | |

**User's choice:** System + user message split

**Notes on additional context:** User noted that cross-hand player action history would be valuable for LLMs to categorize opponents (e.g., detect bluff-heavy players) and adapt — this could lead to more diverse viewer experience. However, the scope and conditions for this (when to use history, whether a strong hand overrides it entirely) need further design. Seeded as a deferred idea for v2. For Phase 4: current-hand context only.

| Option | Description | Selected |
|--------|-------------|----------|
| Stacks + last action only | Each opponent: chip count + last action this street | ✓ |
| Full street action log | Every action this street for all players | |

**User's choice:** Stacks + last action only

| Option | Description | Selected |
|--------|-------------|----------|
| JSON in fenced block | ` ```json { action, amount, reasoning } ``` ` — parsed with regex fallback | ✓ |
| Plain JSON (no fence) | Raw JSON, no markdown | |

**User's choice:** JSON in fenced block

---

## Archetype Assignment

| Option | Description | Selected |
|--------|-------------|----------|
| Unique — each player gets a different one | Random shuffle, no repeats among 4 players | ✓ |
| Random with repeats | Each player independently random | |

**User's choice:** Unique per game (random shuffle)

| Option | Description | Selected |
|--------|-------------|----------|
| Data-driven — defined in config | JSON/dict with name + bias parameters; extendable without code change | ✓ |
| Hardcoded 4 for now | Simpler, refactor later | |

**User's choice:** Data-driven config

---

## Fallback Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Archetype-biased hand strength check | Deterministic decision using hand strength + archetype bias params (raise_freq, hand_looseness, etc.) | ✓ |
| Pure hand strength threshold | Archetype-agnostic thresholds | |

**User's choice:** Archetype-biased hand strength check

| Option | Description | Selected |
|--------|-------------|----------|
| Show a fallback notice | Publish ReasoningEntry: `[Player timed out — acting on instinct]` | ✓ |
| Silent — no reasoning entry | Panel stays empty for that player | |

**User's choice:** Show fallback notice in ReasoningPanel

---

## Claude's Discretion

- Exact archetype bias thresholds
- LiteLLM streaming implementation details
- JSON extraction regex pattern
- Budget cost approximation method
- Circuit breaker reset strategy
- `ReasoningEntry` Python Pydantic model definition

## Deferred Ideas

- Cross-hand player behavior profiling (v2) — per-player action history in decision prompts for opponent modeling
- Parallel LLM calls (v2) — revisit if sequential latency hurts viewer experience
- Provider pricing API for exact budget tracking (v2)
