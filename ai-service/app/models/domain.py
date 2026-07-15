from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictDomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Intent(StrEnum):
    DOCUMENT = "document"
    VIDEO = "video"
    ANALYTICS = "analytics"
    DIRECT = "direct"


class Route(StrEnum):
    DOCUMENT_SEARCH = "document_search"
    VIDEO_SEARCH = "video_search"
    DATA_ANALYTICS = "data_analytics"
    DIRECT_ANSWER = "direct_answer"


class ToolStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_IMPLEMENTED = "not_implemented"


class GuardrailDecision(StrEnum):
    APPROVE = "approve"
    REWRITE = "rewrite"
    BLOCK = "block"


class DocumentRetrievedContext(StrictDomainModel):
    context_id: str
    modality: Literal["document"] = "document"
    content: str
    document_id: str
    filename: str
    page: int = Field(ge=1)
    chunk_id: str
    similarity_score: float = Field(ge=0, le=1)


class VideoRetrievedContext(StrictDomainModel):
    context_id: str
    modality: Literal["video"] = "video"
    content: str
    video_id: str
    filename: str
    segment_id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    similarity_score: float = Field(ge=0, le=1)


RetrievedContext = Annotated[
    DocumentRetrievedContext | VideoRetrievedContext,
    Field(discriminator="modality"),
]


class ToolResult(StrictDomainModel):
    tool: Route
    status: ToolStatus
    summary: str


class DocumentCitation(StrictDomainModel):
    citation_id: str
    source_type: Literal["document"] = "document"
    document_id: str
    filename: str
    page: int = Field(ge=1)
    chunk_id: str
    locator: str


class VideoCitation(StrictDomainModel):
    citation_id: str
    source_type: Literal["video"] = "video"
    video_id: str
    filename: str
    segment_id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    locator: str


Citation = Annotated[
    DocumentCitation | VideoCitation,
    Field(discriminator="source_type"),
]


class GuardrailResult(StrictDomainModel):
    decision: GuardrailDecision
    groundedness_score: float = Field(ge=0, le=1)
    citation_coverage: float = Field(ge=0, le=1)
    prompt_injection_detected: bool
    schema_valid: bool
    reasons: tuple[str, ...] = Field(min_length=1, max_length=20)
    rewrite_required: bool


class ErrorRecord(StrictDomainModel):
    code: str
    message: str
