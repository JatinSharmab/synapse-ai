from functools import lru_cache
from pathlib import Path
from tempfile import gettempdir
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
AIProviderName = Literal["mistral", "mock"]
TranscriptionProviderName = Literal["disabled", "mock"]


class Settings(BaseSettings):
    """Typed runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Environment = "development"
    app_version: str = Field(default="0.6.0", min_length=1)
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=8000, ge=1, le=65_535)
    debug: bool = False
    ai_provider: AIProviderName = "mock"
    mistral_api_key: SecretStr | None = None
    mistral_chat_model: str = Field(default="mistral-small-latest", min_length=1)
    mistral_vision_model: str = Field(default="mistral-small-latest", min_length=1)
    mistral_embed_model: str = Field(default="mistral-embed", min_length=1)
    ai_request_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    ai_max_transient_retries: int = Field(default=2, ge=0, le=3)
    document_max_upload_bytes: int = Field(default=10_485_760, ge=1, le=52_428_800)
    document_max_pages: int = Field(default=200, ge=1, le=1_000)
    document_min_extractable_chars: int = Field(default=40, ge=1, le=10_000)
    document_chunk_max_tokens: int = Field(default=400, ge=32, le=2_000)
    document_chunk_min_tokens: int = Field(default=80, ge=1, le=1_000)
    document_chunk_overlap_tokens: int = Field(default=40, ge=0, le=500)
    document_min_similarity_score: float = Field(default=0.25, ge=0, le=1)
    vector_top_k: int = Field(default=20, ge=1, le=100)
    bm25_top_k: int = Field(default=20, ge=1, le=100)
    rerank_top_k: int = Field(default=10, ge=1, le=100)
    final_context_k: int = Field(default=5, ge=1, le=20)
    document_metadata_path: Path = Path(gettempdir()) / "synapse-ai" / "documents.json"
    chroma_persist_path: Path = Path(gettempdir()) / "synapse-ai" / "chroma"
    chroma_document_collection: str = Field(
        default="synapse_document_chunks",
        min_length=3,
        max_length=63,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9]$",
    )
    max_video_size_mb: int = Field(default=25, ge=1, le=100)
    max_video_duration_seconds: float = Field(default=300, gt=0, le=3_600)
    max_keyframes: int = Field(default=6, ge=1, le=20)
    keyframe_interval_seconds: float = Field(default=30, gt=0, le=600)
    video_subprocess_timeout_seconds: float = Field(default=30, gt=0, le=300)
    ffmpeg_path: str = Field(default="ffmpeg", min_length=1)
    ffprobe_path: str = Field(default="ffprobe", min_length=1)
    video_vision_enabled: bool = False
    video_transcription_enabled: bool = False
    transcription_provider: TranscriptionProviderName = "disabled"
    video_search_top_k: int = Field(default=5, ge=1, le=20)
    video_min_similarity_score: float = Field(default=0.1, ge=0, le=1)
    video_metadata_path: Path = Path(gettempdir()) / "synapse-ai" / "videos.json"
    video_storage_path: Path = Path(gettempdir()) / "synapse-ai" / "videos"
    chroma_video_collection: str = Field(
        default="synapse_video_segments",
        min_length=3,
        max_length=63,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9]$",
    )

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().casefold() in {"1", "true", "yes", "on"}
        return value

    @model_validator(mode="after")
    def validate_chunking_limits(self) -> "Settings":
        if self.document_chunk_min_tokens > self.document_chunk_max_tokens:
            raise ValueError("document chunk minimum cannot exceed maximum")
        if self.document_chunk_overlap_tokens >= self.document_chunk_max_tokens:
            raise ValueError("document chunk overlap must be smaller than maximum")
        if self.final_context_k > self.rerank_top_k:
            raise ValueError("final context count cannot exceed rerank candidate count")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
