"""
budget.py — Per-game LLM spend tracking and per-provider circuit breaker.

D-15: BudgetTracker accumulates token counts x cost-per-token; logged at session end.
D-16: CircuitBreaker trips after 3 consecutive errors per provider; resets on session start.
INFRA-05: Budget protection — cost runaway prevention.

Cost rates are approximations for 2026-05 pricing. Update from provider dashboards.
"""
from __future__ import annotations
import logging
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BudgetTracker:
    """
    In-memory per-GameSession spend accumulator.
    Reset by creating a new instance at session start (not a reset() method — immutable lifecycle).
    """
    _spend: float = 0.0
    _tokens: dict = field(default_factory=lambda: defaultdict(int))

    # Approximate cost-per-token (input + output blended) by provider prefix
    # Update before each deployment from provider pricing dashboards
    _COST_PER_TOKEN: dict = field(default_factory=lambda: {
        "openai":   0.0000004,     # gpt-5-nano blended rate
        "gemini":   0.00000004,    # gemini-3.1-flash-lite-preview blended rate
        "deepseek": 0.00000028,    # deepseek-v4-flash blended rate
        "xai":      0.000001,      # grok-4 conservative estimate — update when confirmed
    })

    def record(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        """
        Accumulate spend for one LLM call.

        Args:
            model: LiteLLM model string (e.g. "openai/gpt-5-nano")
            prompt_tokens: Approximate input token count (len(prompt_text) // 4)
            completion_tokens: Approximate output token count (len(response_text) // 4)
        """
        provider = model.split("/")[0]
        rate = self._COST_PER_TOKEN.get(provider, 0.000001)
        total_tokens = prompt_tokens + completion_tokens
        self._spend += total_tokens * rate
        self._tokens[provider] += total_tokens

    @property
    def total_spend(self) -> float:
        return self._spend

    def summary(self) -> dict:
        return {
            "total_usd": round(self._spend, 6),
            "tokens_by_provider": dict(self._tokens),
        }


@dataclass
class CircuitBreaker:
    """
    Per-provider consecutive error counter (D-16).
    Resets per session (new instance at GameSession start — not a reset() method).

    A provider is "open" (trips the breaker) after `threshold` consecutive errors.
    One success resets the consecutive streak — but does NOT re-close an already-open breaker.
    The breaker stays open for the remainder of the session.
    """
    threshold: int = 3
    _errors: dict = field(default_factory=lambda: defaultdict(int))
    _open: set = field(default_factory=set)

    def record_error(self, model: str) -> None:
        """Record a failed LLM call. Trips the breaker after threshold consecutive errors."""
        self._errors[model] += 1
        if self._errors[model] >= self.threshold and model not in self._open:
            self._open.add(model)
            logger.error(
                "CircuitBreaker OPEN for %s after %d consecutive errors — "
                "fallback will engage for remainder of session",
                model, self.threshold,
            )

    def record_success(self, model: str) -> None:
        """Reset consecutive error streak. Does NOT re-close an already-open breaker."""
        self._errors[model] = 0

    def is_open(self, model: str) -> bool:
        """Return True if this provider's circuit is tripped — caller must use fallback."""
        return model in self._open
