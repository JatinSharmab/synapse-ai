from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import AIProviderName
from app.models.domain import Route
from app.retrieval.models import RetrievalMode


class StrictEvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvaluationDatasetReference(StrictEvaluationModel):
    path: str


class EvaluationAsset(StrictEvaluationModel):
    filename: str
    path: str


class RoutingEvaluationCase(StrictEvaluationModel):
    case_id: str
    query: str
    expected_route: Route
    expected_tool: Route


class GenerationEvaluationCase(StrictEvaluationModel):
    case_id: str
    query: str
    relevance_terms: tuple[str, ...] = Field(min_length=1)


class InputGuardEvaluationCase(StrictEvaluationModel):
    case_id: str
    query: str
    injection_expected: bool


class GroundingGuardEvaluationCase(StrictEvaluationModel):
    case_id: str
    evidence: str
    answer: str
    unsupported_claim_expected: bool


class SynapseEvaluationDataset(StrictEvaluationModel):
    schema_version: str
    dataset_id: str
    retrieval: EvaluationDatasetReference
    datasets: tuple[EvaluationAsset, ...] = ()
    routing_cases: tuple[RoutingEvaluationCase, ...] = Field(min_length=1)
    generation_cases: tuple[GenerationEvaluationCase, ...] = Field(min_length=1)
    input_guard_cases: tuple[InputGuardEvaluationCase, ...] = Field(min_length=1)
    grounding_guard_cases: tuple[GroundingGuardEvaluationCase, ...] = Field(min_length=1)

    @classmethod
    def from_path(cls, path: Path) -> "SynapseEvaluationDataset":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


class RetrievalModeMetrics(StrictEvaluationModel):
    recall_at_k: float = Field(ge=0, le=1)
    mrr: float = Field(ge=0, le=1)
    average_latency_ms: float = Field(ge=0)


class RetrievalEvaluationMetrics(StrictEvaluationModel):
    k: int = Field(ge=1)
    query_count: int = Field(ge=1)
    vector_only: RetrievalModeMetrics
    hybrid: RetrievalModeMetrics


class RoutingEvaluationMetrics(StrictEvaluationModel):
    case_count: int = Field(ge=1)
    route_accuracy: float = Field(ge=0, le=1)
    tool_selection_accuracy: float = Field(ge=0, le=1)


class GenerationEvaluationMetrics(StrictEvaluationModel):
    case_count: int = Field(ge=1)
    groundedness: float = Field(ge=0, le=1)
    citation_coverage: float = Field(ge=0, le=1)
    answer_relevance_proxy: float = Field(ge=0, le=1)


class GuardrailEvaluationMetrics(StrictEvaluationModel):
    case_count: int = Field(ge=1)
    injection_detection_accuracy: float = Field(ge=0, le=1)
    unsupported_claim_detection_accuracy: float = Field(ge=0, le=1)
    block_rate: float = Field(ge=0, le=1)
    rewrite_rate: float = Field(ge=0, le=1)


class SystemEvaluationMetrics(StrictEvaluationModel):
    invocation_count: int = Field(ge=1)
    total_latency_ms: float = Field(ge=0)
    retrieval_latency_ms: float = Field(ge=0)
    generation_latency_ms: float = Field(ge=0)
    guardrail_latency_ms: float = Field(ge=0)
    provider_calls: int = Field(ge=0)
    estimated_token_usage: int = Field(ge=0)


class EvaluationConfiguration(StrictEvaluationModel):
    dataset_id: str
    dataset_version: str
    dataset_checksum: str = Field(default="0" * 64, pattern=r"^[a-f0-9]{64}$")
    retrieval_k: int = Field(ge=1)
    retrieval_modes: tuple[RetrievalMode, ...]
    vector_top_k: int = Field(default=20, ge=1)
    bm25_top_k: int = Field(default=20, ge=1)
    rerank_top_k: int = Field(default=10, ge=1)
    final_context_k: int = Field(default=5, ge=1)
    deterministic: bool
    random_seed: int
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class EvaluationSummary(StrictEvaluationModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(pattern=r"^eval_[a-f0-9]{32}$")
    timestamp: datetime
    status: Literal["completed"] = "completed"
    configuration: EvaluationConfiguration
    retrieval_mode: Literal["vector_only_and_hybrid"] = "vector_only_and_hybrid"
    provider: AIProviderName
    model_identifier: str
    retrieval: RetrievalEvaluationMetrics
    routing: RoutingEvaluationMetrics
    generation: GenerationEvaluationMetrics
    guardrails: GuardrailEvaluationMetrics
    system: SystemEvaluationMetrics


class RecentEvaluationSummaries(StrictEvaluationModel):
    summaries: tuple[EvaluationSummary, ...]


class InvocationObservation(StrictEvaluationModel):
    route: Route | None
    total_latency_ms: float = Field(ge=0)
    retrieval_latency_ms: float = Field(ge=0)
    generation_latency_ms: float = Field(ge=0)
    guardrail_latency_ms: float = Field(ge=0)
    provider_calls: int = Field(ge=0)
    estimated_token_usage: int = Field(ge=0)
