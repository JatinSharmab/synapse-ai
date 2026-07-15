from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.domain import (
    Citation,
    ErrorRecord,
    GuardrailResult,
    Intent,
    Route,
)
from app.schemas.genui import GenUIComponent
from app.schemas.inference import InferenceMetadata


class ChatInvokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4_000)
    thread_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")

    @field_validator("message", "thread_id")
    @classmethod
    def strip_and_reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ChatStateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    thread_id: str
    intent: Intent | None
    route: Route | None
    final_response: str
    citations: list[Citation]
    genui: list[GenUIComponent]
    guardrail_result: GuardrailResult
    errors: list[ErrorRecord]
    inference_metadata: list[InferenceMetadata]
    trace: list[str]
    rewrite_count: int = Field(ge=0, le=1)
