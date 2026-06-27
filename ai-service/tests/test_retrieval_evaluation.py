from pathlib import Path

from app.core.config import Settings
from app.evaluation.retrieval import RetrievalEvaluationDataset, RetrievalEvaluator
from app.providers.mock import MockProvider
from app.services.document_factory import create_document_rag_service

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = REPOSITORY_ROOT / "sample-data" / "evaluations" / "document-retrieval.v1.json"


def test_versioned_dataset_compares_vector_only_and_hybrid_metrics() -> None:
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

    assert report.dataset_id == "synapse-document-retrieval-v1"
    assert report.vector_only.query_count == 3
    assert report.hybrid.query_count == 3
    assert report.vector_only.recall_at_k == 1.0
    assert report.hybrid.recall_at_k == 1.0
    assert report.vector_only.mrr == 1.0
    assert report.hybrid.mrr == 1.0
