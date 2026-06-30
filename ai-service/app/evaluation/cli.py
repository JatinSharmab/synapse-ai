from pathlib import Path

from app.core.config import Settings
from app.evaluation.retrieval import RetrievalEvaluationDataset, RetrievalEvaluator
from app.providers.mock import MockProvider
from app.services.document_factory import create_document_rag_service

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DATASET_PATH = REPOSITORY_ROOT / "sample-data" / "evaluations" / "document-retrieval.v1.json"


def main() -> None:
    dataset = RetrievalEvaluationDataset.from_path(DATASET_PATH)
    service = create_document_rag_service(
        Settings(
            app_env="test",
            ai_provider="mock",
            vector_top_k=10,
            bm25_top_k=10,
            rerank_top_k=5,
            final_context_k=3,
        ),
        MockProvider(),
    )
    for document in dataset.documents:
        path = REPOSITORY_ROOT / "sample-data" / document.path
        service.ingest_pdf(
            filename=document.filename,
            content_type="application/pdf",
            data=path.read_bytes(),
        )
    report = RetrievalEvaluator().evaluate(service, dataset, k=3)
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
