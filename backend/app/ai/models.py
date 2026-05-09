"""
models.py — Pydantic models for Phase 4 LLM integration.

LLMDecisionResponse: validated shape of the LLM fenced-JSON response.
ReasoningEntry:      SSE reasoning delta payload — MUST exactly match TypeScript
                     ReasoningEntry in app/_components/types.ts.

Serialization: ReasoningEntry.model_dump(by_alias=True) produces camelCase JSON
matching types.ts — same pattern as GameState/Player in engine/models.py.
"""
from __future__ import annotations
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class LLMDecisionResponse(BaseModel):
    """
    Validated shape parsed from the fenced JSON block in the LLM response.
    D-06: ```json {"action": "...", "amount": 0, "reasoning": "..."} ```
    """
    action: Literal["fold", "call", "raise", "check"]
    amount: int = Field(default=0, ge=0)
    reasoning: str = Field(min_length=1, max_length=500)

    @field_validator("reasoning")
    @classmethod
    def strip_reasoning(cls, v: str) -> str:
        return v.strip()


class ReasoningEntry(BaseModel):
    """
    SSE reasoning delta payload (D-01, D-02).

    MUST exactly match TypeScript ReasoningEntry in app/_components/types.ts:
      id (string), playerId (ModelId), text (string), phase (string),
      streaming (boolean), action (ActionType | null), amount (number)

    Serialise with model_dump(by_alias=True) for camelCase JSON over SSE.
    Same alias_generator pattern as Player/GameState in engine/models.py.
    """
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_id: str                    # -> playerId in JSON (must match ModelId: "gpt4"|"gemini"|"deepseek"|"grok")
    text: str = ""
    phase: str
    streaming: bool = True
    action: Optional[Literal["fold", "call", "raise", "check"]] = None
    amount: int = 0
