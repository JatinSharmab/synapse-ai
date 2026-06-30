from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class TranscriptionSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    text: str = Field(min_length=1)


class TranscriptionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    available: bool
    spans: list[TranscriptionSpan]
    reason: str | None = None


class TranscriptionProvider(ABC):
    @abstractmethod
    def transcribe(self, *, audio_path: Path, duration_seconds: float) -> TranscriptionResult:
        """Return timestamped transcript spans without exposing provider internals."""
