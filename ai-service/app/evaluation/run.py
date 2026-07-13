import argparse
from pathlib import Path

from app.core.config import Settings
from app.evaluation.models import EvaluationSummary, SynapseEvaluationDataset
from app.evaluation.repository import create_evaluation_repository
from app.evaluation.system import EvaluationDependencies, SystemEvaluator
from app.main import create_app
from app.providers.factory import create_llm_provider
from app.providers.mock import MockProvider

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_DATA_ROOT = REPOSITORY_ROOT / "sample-data"
DEFAULT_DATASET = SAMPLE_DATA_ROOT / "evaluations" / "synapse-evaluation.v1.json"


def run_evaluation(
    *,
    dataset_path: Path = DEFAULT_DATASET,
    retrieval_k: int = 3,
    use_configured_provider: bool = False,
) -> EvaluationSummary:
    runtime = Settings()
    provider = create_llm_provider(runtime) if use_configured_provider else MockProvider()
    isolated = runtime.model_copy(
        update={
            "app_env": "test",
            "ai_provider": provider.info().provider,
            "metadata_backend": "local",
            "object_storage_provider": "local",
        }
    )
    application = create_app(settings=isolated, provider=provider)
    dataset = SynapseEvaluationDataset.from_path(dataset_path.resolve())
    summary = SystemEvaluator(sample_data_root=SAMPLE_DATA_ROOT).run(
        dataset=dataset,
        dependencies=EvaluationDependencies(
            settings=isolated,
            provider=provider,
            orchestrator=application.state.orchestrator,
            documents=application.state.document_service,
            analytics=application.state.analytics_service,
        ),
        retrieval_k=retrieval_k,
    )
    create_evaluation_repository(runtime).save(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the reproducible Synapse evaluation suite.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--retrieval-k", type=int, default=3)
    parser.add_argument(
        "--provider",
        choices=("mock", "configured"),
        default="mock",
        help="Use deterministic mock inference by default; configured honors AI_PROVIDER.",
    )
    arguments = parser.parse_args()
    if arguments.retrieval_k < 1:
        parser.error("--retrieval-k must be at least 1")
    summary = run_evaluation(
        dataset_path=arguments.dataset,
        retrieval_k=arguments.retrieval_k,
        use_configured_provider=arguments.provider == "configured",
    )
    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
