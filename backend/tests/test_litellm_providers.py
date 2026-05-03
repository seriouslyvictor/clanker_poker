"""
Integration test for LiteLLM connectivity.

Reads LITELLM_TEST_MODEL (or first entry from PLAYER_MODELS) to determine
which model to test. Skipped when neither env var is set.

CI passes with no env vars configured (all tests skip).

To run with a real model:
  export LITELLM_TEST_MODEL="openai/gpt-4o"
  uv run pytest tests/test_litellm_providers.py -v

Or set PLAYER_MODELS and the first model will be used as the test target.
Any LiteLLM-supported model works: https://docs.litellm.ai/docs/providers
"""
import json
import os
import pytest
from litellm import completion


def _get_test_model() -> str | None:
    if m := os.getenv("LITELLM_TEST_MODEL"):
        return m
    if raw := os.getenv("PLAYER_MODELS"):
        try:
            models = json.loads(raw)
            return models[0] if models else None
        except (json.JSONDecodeError, IndexError):
            return None
    return None


_TEST_MODEL = _get_test_model()


@pytest.mark.skipif(
    not _TEST_MODEL,
    reason="No test model configured — set LITELLM_TEST_MODEL or PLAYER_MODELS",
)
def test_litellm_connectivity():
    """Verify LiteLLM can call the configured model and return a response."""
    kwargs: dict = {
        "model": _TEST_MODEL,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
    }
    if _TEST_MODEL and _TEST_MODEL.startswith("ollama"):
        kwargs["api_base"] = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
    response = completion(**kwargs)
    assert response.choices[0].message.content is not None
