from enum import StrEnum
from typing import Literal

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
    NOT_IMPLEMENTED = "not_implemented"


class GuardrailDecision(StrEnum):
    APPROVE = "approve"
    REWRITE = "rewrite"
    BLOCK = "block"


class RetrievedContext(StrictDomainModel):
    context_id: str
    modality: Literal["document", "video", "analytics"]
    content: str


class ToolResult(StrictDomainModel):
    tool: Route
    status: ToolStatus
    summary: str


class Citation(StrictDomainModel):
    citation_id: str
    source_type: Literal["document", "video", "analytics"]
    locator: str


class GenUIComponent(StrictDomainModel):
    component_id: str
    component_type: str
    data: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class GuardrailResult(StrictDomainModel):
    decision: GuardrailDecision
    reason_code: str


class ErrorRecord(StrictDomainModel):
    code: str
    message: str
