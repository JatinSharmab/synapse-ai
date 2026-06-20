from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import AIProviderName
from app.models.domain import Intent, Route

InferenceOperation = Literal["generate", "generate_structured", "describe_image", "embed"]


class StrictInferenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TokenUsage(StrictInferenceModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class InferenceMetadata(StrictInferenceModel):
    provider: AIProviderName
    operation: InferenceOperation
    model: str
    latency_ms: float = Field(ge=0)
    retry_count: int = Field(ge=0)
    token_usage: TokenUsage | None = None


class ProviderModels(StrictInferenceModel):
    chat: str
    vision: str
    embedding: str


class ProviderInfo(StrictInferenceModel):
    provider: AIProviderName
    models: ProviderModels
    mock: bool


class GenerationResult(StrictInferenceModel):
    text: str = Field(min_length=1)
    metadata: InferenceMetadata


StructuredValue = TypeVar("StructuredValue", bound=BaseModel)


class StructuredGenerationResult(StrictInferenceModel, Generic[StructuredValue]):
    value: StructuredValue
    metadata: InferenceMetadata


class EmbeddingResult(StrictInferenceModel):
    vectors: list[list[float]]
    metadata: InferenceMetadata


class RouterClassification(StrictInferenceModel):
    intent: Intent
    route: Route
    confidence: float = Field(ge=0, le=1)
    rationale_code: Literal[
        "document_signal",
        "video_signal",
        "analytics_signal",
        "direct_fallback",
    ]

    @model_validator(mode="after")
    def validate_intent_route_pair(self) -> "RouterClassification":
        expected_routes = {
            Intent.DOCUMENT: Route.DOCUMENT_SEARCH,
            Intent.VIDEO: Route.VIDEO_SEARCH,
            Intent.ANALYTICS: Route.DATA_ANALYTICS,
            Intent.DIRECT: Route.DIRECT_ANSWER,
        }
        if expected_routes[self.intent] != self.route:
            raise ValueError("intent and route must identify the same execution path")
        return self
