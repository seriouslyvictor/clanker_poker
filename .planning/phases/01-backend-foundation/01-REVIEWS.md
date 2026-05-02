# Phase 1: Backend Foundation — Reviews

**Source:** Developer inline feedback on /gsd-plan-phase 1 --reviews
**Date:** 2026-05-02
**Reviewer:** Developer (project owner)

---

## Critical Issue: Provider Lock-In

### Finding

The current plans assume exactly 4 LLM providers (OpenAI, Anthropic, Google/Gemini, Ollama) and bake this assumption into code that must be modified to change providers:

- **Plan 01 (`config.py`)**: `Settings` class declares `openai_api_key`, `anthropic_api_key`, `gemini_api_key`, `ollama_api_base` as hardcoded fields — adding any other provider requires modifying the Settings class
- **Plan 03 (`test_litellm_providers.py`)**: 4 hardcoded test functions, one per provider, with hardcoded model strings
- **Plan 03 (`.env.example`)**: Documents only those 4 providers as if they are the definitive list

### User Feedback (verbatim)

> "The plan is coming from a missconception that we will use the same 4 providers as the sketch outlined, this is not true, the ideia is to make the provider switch as easy as possible, be it open source or with API, we shall not make ANY decisions based on a single llm provider and definitely not set any of them in stone as immutable"

### Required Fix

The design must be **fully provider-agnostic**:

1. **`config.py` Settings class**: Remove all provider-specific key fields (`openai_api_key`, `anthropic_api_key`, `gemini_api_key`, `ollama_api_base`). LiteLLM reads provider keys directly from `os.environ` — no pydantic-settings wrapper needed. Add instead:
   - `player_models: list[str]` — configurable list of LiteLLM model strings (defaults can reference the 4 current defaults but the field is a list of strings, not provider-specific fields)
   - `llm_timeout_seconds: int = 8` — global LLM timeout for budget protection (INFRA-05)
   - Keep `cors_origins: list[str]`

2. **`.env.example`**: Document `PLAYER_MODELS` as the primary config point. List common provider keys below it with a comment explaining "add only the keys for providers you're using — LiteLLM reads these automatically." The file should make it obvious that ANY LiteLLM-supported provider works.

3. **`test_litellm_providers.py`**: Replace 4 hardcoded provider tests with a single provider-agnostic connectivity test:
   - Reads `LITELLM_TEST_MODEL` env var (or first entry from `PLAYER_MODELS`) to know which model to test
   - Skips when neither is configured (CI-safe)
   - Handles Ollama's `api_base` requirement generically (any `ollama*`-prefixed model string)
   - Name the file `test_litellm_connectivity.py` (or keep `test_litellm_providers.py` but replace content)

### What Must NOT Change

- Directory structure (D-01, D-02, D-03) — unchanged
- Health endpoint, CORS middleware wiring — unchanged  
- Poker math engine (Plan 02) — unchanged entirely
- The `extra="ignore"` config — still correct (LiteLLM-set env vars won't cause startup errors)
- Skip-not-fail testing pattern — keep, just make it generic
- Security properties: .env gitignored, no hardcoded secrets — unchanged

### Rationale

`REQUIREMENTS.md AI-01` already mandates this: "any OpenAI-compatible or LiteLLM-supported model can be swapped in without code changes; players called sequentially per decision phase." The original plans violated this requirement by putting provider identity into the Settings schema.

LiteLLM is designed to be the provider abstraction layer — it reads `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. directly from `os.environ`. The pydantic-settings layer should only manage app-level configuration (what models to use, timeouts, CORS) — not forward every possible provider's key through a class that will need updating whenever a new provider is added.
