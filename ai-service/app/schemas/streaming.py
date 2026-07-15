from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.domain import Citation, GuardrailResult, Route
from app.schemas.genui import GenUIComponent


class StreamEventBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    request_id: str = Field(min_length=1, max_length=128)
    correlation_id: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=1)


class RequestStartedEvent(StreamEventBase):
    type: Literal["request.started"] = "request.started"
    thread_id: str = Field(min_length=1, max_length=128)


class RouteSelectedEvent(StreamEventBase):
    type: Literal["route.selected"] = "route.selected"
    route: Route


class RetrievalStartedEvent(StreamEventBase):
    type: Literal["retrieval.started"] = "retrieval.started"
    tool: Literal["document_search", "video_search"]


class RetrievalCompletedEvent(StreamEventBase):
    type: Literal["retrieval.completed"] = "retrieval.completed"
    tool: Literal["document_search", "video_search"]
    candidate_count: int = Field(ge=0, le=100)
    latency_ms: int = Field(ge=0)


class GenerationStartedEvent(StreamEventBase):
    type: Literal["generation.started"] = "generation.started"
    route: Route


class GenerationTokenEvent(StreamEventBase):
    type: Literal["generation.token"] = "generation.token"
    token: str = Field(min_length=1, max_length=1_000)
    index: int = Field(ge=0)


class GenUICreatedEvent(StreamEventBase):
    type: Literal["genui.created"] = "genui.created"
    components: list[GenUIComponent] = Field(min_length=1, max_length=5)


class GuardrailCompletedEvent(StreamEventBase):
    type: Literal["guardrail.completed"] = "guardrail.completed"
    result: GuardrailResult
    rewrite_count: int = Field(ge=0, le=1)


class ResponseCompletedEvent(StreamEventBase):
    type: Literal["response.completed"] = "response.completed"
    final_response: str = Field(min_length=1, max_length=8_000)
    citations: list[Citation] = Field(max_length=20)
    citation_count: int = Field(ge=0, le=20)
    latency_ms: int = Field(ge=0)
    rewrite_count: int = Field(ge=0, le=1)


class StreamErrorEvent(StreamEventBase):
    type: Literal["error"] = "error"
    code: Literal["STREAM_TIMEOUT", "STREAM_FAILED"]
    message: str = Field(min_length=1, max_length=300)
    retryable: bool


StreamEvent = Annotated[
    RequestStartedEvent
    | RouteSelectedEvent
    | RetrievalStartedEvent
    | RetrievalCompletedEvent
    | GenerationStartedEvent
    | GenerationTokenEvent
    | GenUICreatedEvent
    | GuardrailCompletedEvent
    | ResponseCompletedEvent
    | StreamErrorEvent,
    Field(discriminator="type"),
]
