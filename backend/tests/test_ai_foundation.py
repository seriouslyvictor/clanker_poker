"""
test_ai_foundation.py — Tests for backend/app/ai/ package (Plan 04-01).

Covers:
  - archetypes.py: ARCHETYPES list, assign_archetypes(), Archetype dataclass
  - budget.py: BudgetTracker.record() + summary(), CircuitBreaker error/open/reset
  - models.py: LLMDecisionResponse validation, ReasoningEntry camelCase serialization
"""
import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# archetypes.py
# ---------------------------------------------------------------------------

class TestArchetypes:
    def test_archetypes_list_has_4_entries(self):
        from app.ai.archetypes import ARCHETYPES
        assert len(ARCHETYPES) == 4

    def test_archetype_names(self):
        from app.ai.archetypes import ARCHETYPES
        names = {a.name for a in ARCHETYPES}
        assert "Gunslinger" in names
        assert "Rock" in names
        assert "Grinder" in names
        assert "Chaotic Optimist" in names

    def test_archetype_is_frozen_dataclass(self):
        from app.ai.archetypes import ARCHETYPES
        arch = ARCHETYPES[0]
        with pytest.raises((AttributeError, TypeError)):
            arch.name = "modified"  # type: ignore[misc]

    def test_archetype_has_required_fields(self):
        from app.ai.archetypes import ARCHETYPES
        for arch in ARCHETYPES:
            assert hasattr(arch, "name")
            assert hasattr(arch, "description")
            assert hasattr(arch, "hand_looseness")
            assert hasattr(arch, "raise_freq")
            assert hasattr(arch, "bluff_freq")
            assert hasattr(arch, "tilt_threshold")
            assert isinstance(arch.hand_looseness, float)
            assert isinstance(arch.raise_freq, float)
            assert isinstance(arch.bluff_freq, float)
            assert isinstance(arch.tilt_threshold, float)

    def test_gunslinger_bias_params(self):
        from app.ai.archetypes import ARCHETYPES
        gunslinger = next(a for a in ARCHETYPES if a.name == "Gunslinger")
        # Gunslinger should be aggressive: loose threshold, high raise freq
        assert gunslinger.hand_looseness <= 0.40  # calls with wide range
        assert gunslinger.raise_freq <= 0.50      # raises frequently
        assert gunslinger.bluff_freq >= 0.10      # bluffs meaningfully

    def test_rock_bias_params(self):
        from app.ai.archetypes import ARCHETYPES
        rock = next(a for a in ARCHETYPES if a.name == "Rock")
        # Rock should be tight: high threshold, low bluff
        assert rock.hand_looseness >= 0.55       # only plays strong hands
        assert rock.bluff_freq <= 0.05           # rarely bluffs

    def test_assign_archetypes_returns_unique_mapping(self):
        from app.ai.archetypes import assign_archetypes
        from app.engine.models import Player

        players = [
            Player(id="gpt4",     name="A", org="o", color="c", deck="d", chips=1000),
            Player(id="gemini",   name="B", org="o", color="c", deck="d", chips=1000),
            Player(id="deepseek", name="C", org="o", color="c", deck="d", chips=1000),
            Player(id="grok",     name="D", org="o", color="c", deck="d", chips=1000),
        ]
        mapping = assign_archetypes(players)

        assert len(mapping) == 4
        assert set(mapping.keys()) == {"gpt4", "gemini", "deepseek", "grok"}
        # All archetypes must be unique — no two players share one
        assert len(set(mapping.values())) == 4

    def test_assign_archetypes_covers_all_player_ids(self):
        from app.ai.archetypes import assign_archetypes
        from app.engine.models import Player

        players = [
            Player(id="gpt4", name="A", org="o", color="c", deck="d", chips=1000),
            Player(id="gemini", name="B", org="o", color="c", deck="d", chips=1000),
        ]
        mapping = assign_archetypes(players)
        assert "gpt4" in mapping
        assert "gemini" in mapping
        assert mapping["gpt4"] != mapping["gemini"]

    def test_assign_archetypes_randomizes_on_each_call(self):
        """Different calls should (usually) produce different assignments."""
        from app.ai.archetypes import assign_archetypes
        from app.engine.models import Player

        players = [
            Player(id="gpt4",     name="A", org="o", color="c", deck="d", chips=1000),
            Player(id="gemini",   name="B", org="o", color="c", deck="d", chips=1000),
            Player(id="deepseek", name="C", org="o", color="c", deck="d", chips=1000),
            Player(id="grok",     name="D", org="o", color="c", deck="d", chips=1000),
        ]
        results = set()
        for _ in range(20):
            mapping = assign_archetypes(players)
            results.add(mapping["gpt4"].name)

        # Over 20 runs, we should see more than 1 different archetype for gpt4
        assert len(results) > 1


# ---------------------------------------------------------------------------
# budget.py
# ---------------------------------------------------------------------------

class TestBudgetTracker:
    def test_initial_spend_is_zero(self):
        from app.ai.budget import BudgetTracker
        bt = BudgetTracker()
        assert bt.total_spend == 0.0

    def test_record_increases_spend(self):
        from app.ai.budget import BudgetTracker
        bt = BudgetTracker()
        bt.record("openai/gpt-5-nano", 100, 50)
        assert bt.total_spend > 0.0

    def test_record_accumulates_multiple_calls(self):
        from app.ai.budget import BudgetTracker
        bt = BudgetTracker()
        bt.record("openai/gpt-5-nano", 100, 50)
        spend_after_1 = bt.total_spend
        bt.record("openai/gpt-5-nano", 200, 100)
        assert bt.total_spend > spend_after_1

    def test_summary_has_required_keys(self):
        from app.ai.budget import BudgetTracker
        bt = BudgetTracker()
        bt.record("openai/gpt-5-nano", 100, 50)
        s = bt.summary()
        assert "total_usd" in s
        assert "tokens_by_provider" in s

    def test_summary_tokens_by_provider(self):
        from app.ai.budget import BudgetTracker
        bt = BudgetTracker()
        bt.record("openai/gpt-5-nano", 100, 50)
        bt.record("gemini/gemini-3.1-flash-lite-preview", 200, 80)
        s = bt.summary()
        assert "openai" in s["tokens_by_provider"]
        assert "gemini" in s["tokens_by_provider"]
        assert s["tokens_by_provider"]["openai"] == 150
        assert s["tokens_by_provider"]["gemini"] == 280

    def test_unknown_provider_uses_fallback_rate(self):
        from app.ai.budget import BudgetTracker
        bt = BudgetTracker()
        bt.record("unknown-provider/model", 1000, 0)
        # Should not raise; uses default rate
        assert bt.total_spend > 0.0

    def test_summary_total_usd_is_rounded(self):
        from app.ai.budget import BudgetTracker
        bt = BudgetTracker()
        bt.record("openai/gpt-5-nano", 100, 50)
        s = bt.summary()
        # total_usd should be a float rounded to ≤6 decimal places
        assert isinstance(s["total_usd"], float)


class TestCircuitBreaker:
    def test_initially_closed(self):
        from app.ai.budget import CircuitBreaker
        cb = CircuitBreaker()
        assert not cb.is_open("openai/gpt-5-nano")

    def test_not_open_after_fewer_than_threshold_errors(self):
        from app.ai.budget import CircuitBreaker
        cb = CircuitBreaker(threshold=3)
        cb.record_error("openai/gpt-5-nano")
        cb.record_error("openai/gpt-5-nano")
        assert not cb.is_open("openai/gpt-5-nano")

    def test_opens_after_threshold_consecutive_errors(self):
        from app.ai.budget import CircuitBreaker
        cb = CircuitBreaker(threshold=3)
        cb.record_error("openai/gpt-5-nano")
        cb.record_error("openai/gpt-5-nano")
        cb.record_error("openai/gpt-5-nano")
        assert cb.is_open("openai/gpt-5-nano")

    def test_success_does_not_close_open_breaker(self):
        from app.ai.budget import CircuitBreaker
        cb = CircuitBreaker(threshold=3)
        cb.record_error("openai/gpt-5-nano")
        cb.record_error("openai/gpt-5-nano")
        cb.record_error("openai/gpt-5-nano")
        assert cb.is_open("openai/gpt-5-nano")
        cb.record_success("openai/gpt-5-nano")
        # Once open, stays open for the session
        assert cb.is_open("openai/gpt-5-nano")

    def test_success_resets_consecutive_error_streak(self):
        from app.ai.budget import CircuitBreaker
        cb = CircuitBreaker(threshold=3)
        cb.record_error("openai/gpt-5-nano")
        cb.record_error("openai/gpt-5-nano")
        cb.record_success("openai/gpt-5-nano")
        # Streak reset — 2 more errors shouldn't open it
        cb.record_error("openai/gpt-5-nano")
        cb.record_error("openai/gpt-5-nano")
        assert not cb.is_open("openai/gpt-5-nano")

    def test_different_models_are_independent(self):
        from app.ai.budget import CircuitBreaker
        cb = CircuitBreaker(threshold=3)
        cb.record_error("openai/gpt-5-nano")
        cb.record_error("openai/gpt-5-nano")
        cb.record_error("openai/gpt-5-nano")
        # gpt-5-nano is open but gemini should not be
        assert cb.is_open("openai/gpt-5-nano")
        assert not cb.is_open("gemini/gemini-3.1-flash-lite-preview")

    def test_custom_threshold(self):
        from app.ai.budget import CircuitBreaker
        cb = CircuitBreaker(threshold=5)
        for _ in range(4):
            cb.record_error("openai/gpt-5-nano")
        assert not cb.is_open("openai/gpt-5-nano")
        cb.record_error("openai/gpt-5-nano")
        assert cb.is_open("openai/gpt-5-nano")


# ---------------------------------------------------------------------------
# models.py
# ---------------------------------------------------------------------------

class TestLLMDecisionResponse:
    def test_valid_raise_action(self):
        from app.ai.models import LLMDecisionResponse
        r = LLMDecisionResponse(action="raise", amount=80, reasoning="Going all in")
        assert r.action == "raise"
        assert r.amount == 80
        assert r.reasoning == "Going all in"

    def test_valid_fold_action(self):
        from app.ai.models import LLMDecisionResponse
        r = LLMDecisionResponse(action="fold", amount=0, reasoning="Bad hand")
        assert r.action == "fold"

    def test_valid_call_action_with_default_amount(self):
        from app.ai.models import LLMDecisionResponse
        r = LLMDecisionResponse(action="call", reasoning="Pot odds are good")
        assert r.action == "call"
        assert r.amount == 0

    def test_valid_check_action(self):
        from app.ai.models import LLMDecisionResponse
        r = LLMDecisionResponse(action="check", reasoning="No bet to call")
        assert r.action == "check"

    def test_invalid_action_raises_validation_error(self):
        from app.ai.models import LLMDecisionResponse
        with pytest.raises(ValidationError):
            LLMDecisionResponse(action="shove", amount=0, reasoning="All in!")  # type: ignore[arg-type]

    def test_negative_amount_raises_validation_error(self):
        from app.ai.models import LLMDecisionResponse
        with pytest.raises(ValidationError):
            LLMDecisionResponse(action="raise", amount=-10, reasoning="Negative bet")

    def test_empty_reasoning_raises_validation_error(self):
        from app.ai.models import LLMDecisionResponse
        with pytest.raises(ValidationError):
            LLMDecisionResponse(action="call", reasoning="")

    def test_reasoning_is_stripped(self):
        from app.ai.models import LLMDecisionResponse
        r = LLMDecisionResponse(action="call", reasoning="  thinking hard  ")
        assert r.reasoning == "thinking hard"


class TestReasoningEntry:
    def test_basic_construction(self):
        from app.ai.models import ReasoningEntry
        entry = ReasoningEntry(player_id="gpt4", phase="flop", text="thinking")
        assert entry.player_id == "gpt4"
        assert entry.phase == "flop"
        assert entry.text == "thinking"

    def test_id_auto_generated(self):
        from app.ai.models import ReasoningEntry
        entry1 = ReasoningEntry(player_id="gpt4", phase="flop")
        entry2 = ReasoningEntry(player_id="gpt4", phase="flop")
        assert entry1.id != entry2.id  # UUIDs are unique

    def test_serializes_to_camel_case(self):
        from app.ai.models import ReasoningEntry
        entry = ReasoningEntry(player_id="gpt4", phase="flop", text="thinking")
        dumped = entry.model_dump(by_alias=True)
        assert "playerId" in dumped
        assert "player_id" not in dumped
        assert dumped["playerId"] == "gpt4"

    def test_all_camel_case_fields_present(self):
        from app.ai.models import ReasoningEntry
        entry = ReasoningEntry(player_id="gpt4", phase="flop")
        dumped = entry.model_dump(by_alias=True)
        # Must match TypeScript ReasoningEntry interface exactly
        assert "id" in dumped
        assert "playerId" in dumped
        assert "text" in dumped
        assert "phase" in dumped
        assert "streaming" in dumped
        assert "action" in dumped
        assert "amount" in dumped

    def test_default_values(self):
        from app.ai.models import ReasoningEntry
        entry = ReasoningEntry(player_id="gpt4", phase="pre-flop")
        assert entry.text == ""
        assert entry.streaming is True
        assert entry.action is None
        assert entry.amount == 0

    def test_streaming_false_with_action(self):
        from app.ai.models import ReasoningEntry
        entry = ReasoningEntry(
            player_id="gemini",
            phase="turn",
            text="I will raise",
            streaming=False,
            action="raise",
            amount=100,
        )
        dumped = entry.model_dump(by_alias=True)
        assert dumped["streaming"] is False
        assert dumped["action"] == "raise"
        assert dumped["amount"] == 100

    def test_player_id_matches_model_ids(self):
        """player_id values must match ModelId: gpt4|gemini|deepseek|grok"""
        from app.ai.models import ReasoningEntry
        for pid in ["gpt4", "gemini", "deepseek", "grok"]:
            entry = ReasoningEntry(player_id=pid, phase="flop")
            dumped = entry.model_dump(by_alias=True)
            assert dumped["playerId"] == pid
