"""
ai/ — LLM decision engine for Phase 4.

Modules:
  archetypes: Archetype config and assignment (D-09, D-10)
  budget:     BudgetTracker + CircuitBreaker (D-15, D-16, INFRA-05)
  models:     LLMDecisionResponse + ReasoningEntry Pydantic models
  prompt:     build_system_prompt() + build_user_prompt() (Plan 03)
  decision:   make_llm_decision_fn() closure (Plan 03)
"""
