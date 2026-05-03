from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Player model config — any LiteLLM-compatible model strings
    # LiteLLM reads OPENAI_API_KEY, ANTHROPIC_API_KEY etc. directly from os.environ
    player_models: list[str] = [
        "openai/gpt-4o",
        "anthropic/claude-3-5-haiku-20241022",
        "gemini/gemini-2.0-flash",
        "ollama_chat/llama3",
    ]
    llm_timeout_seconds: int = 8
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
