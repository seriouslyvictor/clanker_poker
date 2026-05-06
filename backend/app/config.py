import json
import pathlib
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_MODELS_CONFIG = pathlib.Path(__file__).parent.parent.parent / "models.config.json"


def _default_player_models() -> list[str]:
    with open(_MODELS_CONFIG) as f:
        return [m["litellmModel"] for m in json.load(f)]


class Settings(BaseSettings):
    # Player model config — defaults from models.config.json; override via PLAYER_MODELS env var
    player_models: list[str] = Field(default_factory=_default_player_models)
    llm_timeout_seconds: int = 8
    cors_origins: list[str] = ["http://localhost:3000"]
    redis_url: str = "redis://localhost:6379"
    hand_delay_seconds: int = 3  # D-11: seconds between hands in continuous game loop

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
