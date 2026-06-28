from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.inference import InferenceMetadata


class StrictVideoModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProcessingStatus(StrEnum):
    READY = "ready"
    PARTIAL = "partial"


class EnrichmentStatus(StrEnum):
    COMPLETED = "completed"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


class VideoRecord(StrictVideoModel):
    video_id: str
    filename: str = Field(min_length=1, max_length=255)
    duration_seconds: float = Field(gt=0)
    size_bytes: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    has_audio: bool
    segment_count: int = Field(ge=1)
    processing_status: ProcessingStatus
    visual_enrichment: EnrichmentStatus
    transcription: EnrichmentStatus
    created_at: datetime


class TemporalSegment(StrictVideoModel):
    video_id: str
    filename: str
    segment_id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    transcript: str
    visual_description: str
    combined_text: str = Field(min_length=1)
    keyframe_path: str
    embedding_metadata: InferenceMetadata


class StoredTemporalSegment(StrictVideoModel):
    segment: TemporalSegment
    embedding: list[float] = Field(min_length=1)


class VideoSearchResult(StrictVideoModel):
    video_id: str
    filename: str
    segment_id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    description: str
    score: float = Field(ge=0, le=1)
