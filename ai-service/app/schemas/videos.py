from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.videos import VideoRecord, VideoSearchResult
from app.schemas.inference import InferenceMetadata


class VideoListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    videos: list[VideoRecord]


class VideoSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2_000)
    top_k: int | None = Field(default=None, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized


class VideoSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[VideoSearchResult]
    inference_metadata: InferenceMetadata | None
