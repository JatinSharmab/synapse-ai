import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.core.config import Settings
from app.evaluation.models import (
    EvaluationConfiguration,
    EvaluationSummary,
    GenerationEvaluationMetrics,
    GuardrailEvaluationMetrics,
    InvocationObservation,
    RetrievalEvaluationMetrics,
    RetrievalModeMetrics,
    RoutingEvaluationMetrics,
    SynapseEvaluationDataset,
    SystemEvaluationMetrics,
)
from app.evaluation.retrieval import RetrievalEvaluationDataset, RetrievalEvaluator
from app.models.domain import DocumentCitation, DocumentRetrievedContext, Route
from app.models.state import SynapseState, create_initial_state
from app.providers.base import LLMProvider
from app.schemas.chat import ChatStateSummary
from app.services.analytics_service import AnalyticsService
from app.services.document_rag import DocumentRAGService
from app.services.guardrails import GroundingGuard, InputGuard
from app.services.orchestrator import SynapseOrchestrator

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", re.I)


@dataclass(frozen=True)
class EvaluationDependencies:
    settings: Settings
    provider: LLMProvider
    orchestrator: SynapseOrchestrator
    documents: DocumentRAGService
    analytics: AnalyticsService


class SystemEvaluator:
    """Runs a deterministic, versioned benchmark and emits aggregate operational metrics."""

    def __init__(self, *, sample_data_root: Path) -> None:
        self._sample_data_root = sample_data_root.resolve()

    def run(
        self,
        *,
        dataset: SynapseEvaluationDataset,
        dependencies: EvaluationDependencies,
        retrieval_k: int,
    ) -> EvaluationSummary:
        retrieval_dataset = RetrievalEvaluationDataset.from_path(
            self._resolve_asset(dataset.retrieval.path)
        )
        self._ingest_assets(dataset, retrieval_dataset, dependencies)
        retrieval = RetrievalEvaluator().evaluate(
            dependencies.documents, retrieval_dataset, k=retrieval_k
        )

        observations: list[InvocationObservation] = []
        route_hits = 0
        tool_hits = 0
        for routing_case in dataset.routing_cases:
            summary, observation = self._invoke_observed(
                dependencies.orchestrator, routing_case.query, routing_case.case_id
            )
            observations.append(observation)
            route_hits += int(summary.route == routing_case.expected_route)
            tool_hits += int(f"tool={routing_case.expected_tool.value}" in summary.trace)

        groundedness = 0.0
        citation_coverage = 0.0
        relevance = 0.0
        for generation_case in dataset.generation_cases:
            summary, observation = self._invoke_observed(
                dependencies.orchestrator, generation_case.query, generation_case.case_id
            )
            observations.append(observation)
            groundedness += summary.guardrail_result.groundedness_score
            citation_coverage += summary.guardrail_result.citation_coverage
            relevance += self._relevance_proxy(
                summary.final_response, generation_case.relevance_terms
            )

        input_guard = InputGuard()
        grounding_guard = GroundingGuard()
        injection_hits = 0
        block_count = 0
        for input_case in dataset.input_guard_cases:
            input_outcome = input_guard.evaluate(input_case.query)
            injection_hits += int(
                input_outcome.prompt_injection_detected == input_case.injection_expected
            )
            block_count += int(not input_outcome.passed)

        unsupported_hits = 0
        rewrite_count = 0
        for index, grounding_case in enumerate(dataset.grounding_guard_cases):
            state = self._grounding_state(
                index=index,
                evidence=grounding_case.evidence,
                answer=grounding_case.answer,
            )
            grounding_outcome = grounding_guard.evaluate(state)
            predicted = "GROUNDING_UNSUPPORTED_CLAIM" in grounding_outcome.reasons
            unsupported_hits += int(
                predicted == grounding_case.unsupported_claim_expected
            )
            block_count += int(grounding_outcome.block_required)
            rewrite_count += int(grounding_outcome.rewrite_required)

        provider_info = dependencies.provider.info()
        asset_paths: list[str] = [item.path for item in retrieval_dataset.documents]
        asset_paths.extend(item.path for item in dataset.datasets)
        asset_checksums = {
            path: sha256(self._resolve_asset(path).read_bytes()).hexdigest()
            for path in asset_paths
        }
        dataset_checksum = sha256(
            json.dumps(
                {
                    "suite": dataset.model_dump(mode="json"),
                    "retrieval": retrieval_dataset.model_dump(mode="json"),
                    "assets": asset_checksums,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        configuration_payload = {
            "dataset_id": dataset.dataset_id,
            "dataset_version": dataset.schema_version,
            "dataset_checksum": dataset_checksum,
            "retrieval_k": retrieval_k,
            "retrieval_modes": ["vector_only", "hybrid"],
            "vector_top_k": dependencies.settings.vector_top_k,
            "bm25_top_k": dependencies.settings.bm25_top_k,
            "rerank_top_k": dependencies.settings.rerank_top_k,
            "final_context_k": dependencies.settings.final_context_k,
            "provider": provider_info.provider,
            "model": provider_info.models.chat,
            "random_seed": 0,
        }
        fingerprint = sha256(
            json.dumps(configuration_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        routing_count = len(dataset.routing_cases)
        generation_count = len(dataset.generation_cases)
        guard_count = len(dataset.input_guard_cases) + len(dataset.grounding_guard_cases)

        return EvaluationSummary(
            run_id=f"eval_{uuid4().hex}",
            timestamp=datetime.now(UTC),
            configuration=EvaluationConfiguration(
                dataset_id=dataset.dataset_id,
                dataset_version=dataset.schema_version,
                dataset_checksum=dataset_checksum,
                retrieval_k=retrieval_k,
                retrieval_modes=("vector_only", "hybrid"),
                vector_top_k=dependencies.settings.vector_top_k,
                bm25_top_k=dependencies.settings.bm25_top_k,
                rerank_top_k=dependencies.settings.rerank_top_k,
                final_context_k=dependencies.settings.final_context_k,
                deterministic=True,
                random_seed=0,
                fingerprint=fingerprint,
            ),
            provider=provider_info.provider,
            model_identifier=provider_info.models.chat,
            retrieval=RetrievalEvaluationMetrics(
                k=retrieval_k,
                query_count=retrieval.vector_only.query_count,
                vector_only=RetrievalModeMetrics(
                    recall_at_k=retrieval.vector_only.recall_at_k,
                    mrr=retrieval.vector_only.mrr,
                    average_latency_ms=retrieval.vector_only.average_latency_ms,
                ),
                hybrid=RetrievalModeMetrics(
                    recall_at_k=retrieval.hybrid.recall_at_k,
                    mrr=retrieval.hybrid.mrr,
                    average_latency_ms=retrieval.hybrid.average_latency_ms,
                ),
            ),
            routing=RoutingEvaluationMetrics(
                case_count=routing_count,
                route_accuracy=round(route_hits / routing_count, 4),
                tool_selection_accuracy=round(tool_hits / routing_count, 4),
            ),
            generation=GenerationEvaluationMetrics(
                case_count=generation_count,
                groundedness=round(groundedness / generation_count, 4),
                citation_coverage=round(citation_coverage / generation_count, 4),
                answer_relevance_proxy=round(relevance / generation_count, 4),
            ),
            guardrails=GuardrailEvaluationMetrics(
                case_count=guard_count,
                injection_detection_accuracy=round(
                    injection_hits / len(dataset.input_guard_cases), 4
                ),
                unsupported_claim_detection_accuracy=round(
                    unsupported_hits / len(dataset.grounding_guard_cases), 4
                ),
                block_rate=round(block_count / guard_count, 4),
                rewrite_rate=round(rewrite_count / guard_count, 4),
            ),
            system=self._system_metrics(observations),
        )

    def _ingest_assets(
        self,
        dataset: SynapseEvaluationDataset,
        retrieval: RetrievalEvaluationDataset,
        dependencies: EvaluationDependencies,
    ) -> None:
        for document in retrieval.documents:
            path = self._resolve_asset(document.path)
            dependencies.documents.ingest_pdf(
                filename=document.filename,
                content_type="application/pdf",
                data=path.read_bytes(),
            )
        for item in dataset.datasets:
            path = self._resolve_asset(item.path)
            dependencies.analytics.ingest_csv(
                filename=item.filename,
                content_type="text/csv",
                data=path.read_bytes(),
            )

    def _resolve_asset(self, relative_path: str) -> Path:
        candidate = (self._sample_data_root / relative_path).resolve()
        if self._sample_data_root not in candidate.parents:
            raise ValueError("evaluation asset path escapes the sample-data directory")
        if not candidate.is_file():
            raise FileNotFoundError(f"evaluation asset does not exist: {relative_path}")
        return candidate

    @staticmethod
    def _invoke_observed(
        orchestrator: SynapseOrchestrator,
        query: str,
        case_id: str,
    ) -> tuple[ChatStateSummary, InvocationObservation]:
        started = perf_counter()
        route_at: float | None = None
        tool_at: float | None = None
        draft_at: float | None = None

        def observe(state: SynapseState) -> None:
            nonlocal route_at, tool_at, draft_at
            now = perf_counter()
            if route_at is None and state["route"] is not None:
                route_at = now
            if tool_at is None and state["tool_results"]:
                tool_at = now
            if draft_at is None and state["draft_response"] is not None:
                draft_at = now

        summary = orchestrator.invoke_with_observer(
            message=query,
            thread_id=f"evaluation-{case_id}",
            observer=observe,
        )
        ended = perf_counter()
        generation_start = tool_at or route_at or started
        generation_end = draft_at or ended
        retrieval_latency = 0.0
        if summary.route in {Route.DOCUMENT_SEARCH, Route.VIDEO_SEARCH} and route_at and tool_at:
            retrieval_latency = (tool_at - route_at) * 1_000
        token_usage = sum(
            metadata.token_usage.total_tokens
            for metadata in summary.inference_metadata
            if metadata.token_usage is not None
        )
        observation = InvocationObservation(
            route=summary.route,
            total_latency_ms=round((ended - started) * 1_000, 3),
            retrieval_latency_ms=round(max(0.0, retrieval_latency), 3),
            generation_latency_ms=round(max(0.0, (generation_end - generation_start) * 1_000), 3),
            guardrail_latency_ms=round(max(0.0, (ended - generation_end) * 1_000), 3),
            provider_calls=len(summary.inference_metadata),
            estimated_token_usage=token_usage,
        )
        return summary, observation

    @staticmethod
    def _grounding_state(*, index: int, evidence: str, answer: str) -> SynapseState:
        chunk_id = f"evaluation_chunk_{index}"
        state = create_initial_state(
            request_id=f"evaluation_{index}",
            thread_id=f"evaluation_grounding_{index}",
            user_query="What does the evidence say about refund approval?",
        )
        state["input_guard_passed"] = True
        state["route"] = Route.DOCUMENT_SEARCH
        state["retrieved_context"] = [
            DocumentRetrievedContext(
                context_id=chunk_id,
                content=evidence,
                document_id="evaluation_document",
                filename="evaluation.pdf",
                page=1,
                chunk_id=chunk_id,
                similarity_score=1,
            )
        ]
        state["citations"] = [
            DocumentCitation(
                citation_id=f"citation_{chunk_id}",
                document_id="evaluation_document",
                filename="evaluation.pdf",
                page=1,
                chunk_id=chunk_id,
                locator="evaluation.pdf, page 1",
            )
        ]
        state["draft_response"] = answer
        return state

    @staticmethod
    def _relevance_proxy(answer: str, terms: tuple[str, ...]) -> float:
        normalized_answer = " ".join(TOKEN_PATTERN.findall(answer.casefold()))
        matches = sum(
            1
            for term in terms
            if " ".join(TOKEN_PATTERN.findall(term.casefold())) in normalized_answer
        )
        return matches / len(terms)

    @staticmethod
    def _system_metrics(observations: list[InvocationObservation]) -> SystemEvaluationMetrics:
        return SystemEvaluationMetrics(
            invocation_count=len(observations),
            total_latency_ms=round(sum(item.total_latency_ms for item in observations), 3),
            retrieval_latency_ms=round(
                sum(item.retrieval_latency_ms for item in observations), 3
            ),
            generation_latency_ms=round(
                sum(item.generation_latency_ms for item in observations), 3
            ),
            guardrail_latency_ms=round(
                sum(item.guardrail_latency_ms for item in observations), 3
            ),
            provider_calls=sum(item.provider_calls for item in observations),
            estimated_token_usage=sum(item.estimated_token_usage for item in observations),
        )
