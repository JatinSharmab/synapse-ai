from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
AIProviderName = Literal["mistral", "mock"]


class Settings(BaseSettings):
    """Typed runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Environment = "development"
    app_version: str = Field(default="0.3.0", min_length=1)
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=8000, ge=1, le=65_535)
    ai_provider: AIProviderName = "mock"
    mistral_api_key: SecretStr | None = None
    mistral_chat_model: str = Field(default="mistral-small-latest", min_length=1)
    mistral_vision_model: str = Field(default="mistral-small-latest", min_length=1)
    mistral_embed_model: str = Field(default="mistral-embed", min_length=1)
    ai_request_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    ai_max_transient_retries: int = Field(default=2, ge=0, le=3)


@lru_cache
def get_settings() -> Settings:
    return Settings()
