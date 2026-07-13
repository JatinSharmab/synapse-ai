from pathlib import Path

import mongomock
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.evaluation.models import EvaluationSummary, SynapseEvaluationDataset
from app.evaluation.repository import (
    InMemoryEvaluationSummaryRepository,
    JsonEvaluationSummaryRepository,
    MongoEvaluationSummaryRepository,
)
from app.evaluation.system import EvaluationDependencies, SystemEvaluator
from app.main import create_app
from app.providers.mock import MockProvider

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA_ROOT = REPOSITORY_ROOT / "sample-data"
DATASET_PATH = SAMPLE_DATA_ROOT / "evaluations" / "synapse-evaluation.v1.json"


@pytest.fixture(scope="module")
def evaluation_summary() -> EvaluationSummary:
    provider = MockProvider()
    application = create_app(Settings(app_env="test", ai_provider="mock"), provider=provider)
    return SystemEvaluator(sample_data_root=SAMPLE_DATA_ROOT).run(
        dataset=SynapseEvaluationDataset.from_path(DATASET_PATH),
        dependencies=EvaluationDependencies(
            settings=application.state.settings,
            provider=provider,
            orchestrator=application.state.orchestrator,
            documents=application.state.document_service,
            analytics=application.state.analytics_service,
        ),
        retrieval_k=3,
    )


def test_reproducible_suite_calculates_all_metric_groups(
    evaluation_summary: EvaluationSummary,
) -> None:
    summary = evaluation_summary

    assert summary.provider == "mock"
    assert summary.model_identifier == "mock-chat-v1"
    assert summary.configuration.deterministic is True
    assert summary.configuration.retrieval_modes == ("vector_only", "hybrid")
    assert summary.retrieval.vector_only.recall_at_k == 1
    assert summary.retrieval.hybrid.recall_at_k == 1
    assert summary.retrieval.hybrid.average_latency_ms >= 0
    assert summary.routing.route_accuracy == 1
    assert summary.routing.tool_selection_accuracy == 1
    assert summary.generation.groundedness >= 0.9
    assert summary.generation.citation_coverage == 1
    assert summary.generation.answer_relevance_proxy == 1
    assert summary.guardrails.injection_detection_accuracy == 1
    assert summary.guardrails.unsupported_claim_detection_accuracy == 1
    assert summary.system.invocation_count == 6
    assert summary.system.provider_calls > 0
    assert summary.system.estimated_token_usage > 0
    assert summary.system.total_latency_ms >= summary.system.generation_latency_ms


def test_summary_excludes_prompts_answers_and_hidden_reasoning(
    evaluation_summary: EvaluationSummary,
) -> None:
    serialized = evaluation_summary.model_dump_json().casefold()

    assert "system_prompt" not in serialized
    assert "user_prompt" not in serialized
    assert "final_response" not in serialized
    assert "chain_of_thought" not in serialized
    assert "hidden_reasoning" not in serialized


def test_json_repository_round_trips_summary(
    tmp_path: Path, evaluation_summary: EvaluationSummary
) -> None:
    path = tmp_path / "evaluations.json"
    repository = JsonEvaluationSummaryRepository(path)
    repository.save(evaluation_summary)

    restored = JsonEvaluationSummaryRepository(path).recent(1)

    assert restored == [evaluation_summary]


def test_mongo_repository_round_trips_summary(evaluation_summary: EvaluationSummary) -> None:
    repository = MongoEvaluationSummaryRepository(
        uri="mongodb://unused",
        database_name="synapse_test",
        client=mongomock.MongoClient(),
    )
    repository.save(evaluation_summary)

    restored = repository.recent(1)[0]
    assert restored.run_id == evaluation_summary.run_id
    assert restored.retrieval == evaluation_summary.retrieval


def test_recent_summaries_api_is_bounded_and_safe(
    evaluation_summary: EvaluationSummary,
) -> None:
    repository = InMemoryEvaluationSummaryRepository()
    repository.save(evaluation_summary)
    application = create_app(
        Settings(app_env="test", ai_provider="mock", evaluation_recent_limit=1),
        evaluation_repository=repository,
    )

    with TestClient(application) as client:
        response = client.get("/api/v1/evaluations/summaries?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert len(body["summaries"]) == 1
    assert body["summaries"][0]["run_id"] == evaluation_summary.run_id
    assert "final_response" not in body["summaries"][0]
