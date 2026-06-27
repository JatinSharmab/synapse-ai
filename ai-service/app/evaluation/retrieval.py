from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.models.documents import DocumentChunk
from app.retrieval.models import RetrievalMode
from app.services.document_rag import DocumentRAGService


class StrictEvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvaluationDocument(StrictEvaluationModel):
    filename: str
    path: str


class RetrievalEvaluationCase(StrictEvaluationModel):
    case_id: str
    query: str
    relevant_document: str
    relevant_page: int = Field(ge=1)
    relevant_chunk_index: int = Field(ge=0)


class RetrievalEvaluationDataset(StrictEvaluationModel):
    schema_version: str
    dataset_id: str
    documents: list[EvaluationDocument] = Field(min_length=1)
    cases: list[RetrievalEvaluationCase] = Field(min_length=1)

    @classmethod
    def from_path(cls, path: Path) -> "RetrievalEvaluationDataset":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class RetrievalMetrics(StrictEvaluationModel):
    mode: RetrievalMode
    k: int = Field(ge=1)
    query_count: int = Field(ge=1)
    recall_at_k: float = Field(ge=0, le=1)
    mrr: float = Field(ge=0, le=1)


class RetrievalComparison(StrictEvaluationModel):
    dataset_id: str
    schema_version: str
    vector_only: RetrievalMetrics
    hybrid: RetrievalMetrics


class RetrievalEvaluator:
    def evaluate(
        self,
        service: DocumentRAGService,
        dataset: RetrievalEvaluationDataset,
        *,
        k: int,
    ) -> RetrievalComparison:
        chunks = {
            chunk.chunk_id: chunk
            for document in service.list_documents()
            for chunk in service.get_chunks(document.document_id)
        }
        return RetrievalComparison(
            dataset_id=dataset.dataset_id,
            schema_version=dataset.schema_version,
            vector_only=self._evaluate_mode(service, dataset, chunks, mode="vector_only", k=k),
            hybrid=self._evaluate_mode(service, dataset, chunks, mode="hybrid", k=k),
        )

    @staticmethod
    def _evaluate_mode(
        service: DocumentRAGService,
        dataset: RetrievalEvaluationDataset,
        chunks: dict[str, DocumentChunk],
        *,
        mode: RetrievalMode,
        k: int,
    ) -> RetrievalMetrics:
        hits = 0
        reciprocal_ranks = 0.0
        for case in dataset.cases:
            execution = service.search(case.query, top_k=k, mode=mode)
            relevant_rank = next(
                (
                    rank
                    for rank, result in enumerate(execution.results[:k], start=1)
                    if RetrievalEvaluator._is_relevant(result.chunk_id, case, chunks)
                ),
                None,
            )
            if relevant_rank is not None:
                hits += 1
                reciprocal_ranks += 1.0 / relevant_rank
        query_count = len(dataset.cases)
        return RetrievalMetrics(
            mode=mode,
            k=k,
            query_count=query_count,
            recall_at_k=hits / query_count,
            mrr=reciprocal_ranks / query_count,
        )

    @staticmethod
    def _is_relevant(
        chunk_id: str,
        case: RetrievalEvaluationCase,
        chunks: dict[str, DocumentChunk],
    ) -> bool:
        chunk = chunks.get(chunk_id)
        return bool(
            chunk
            and chunk.filename == case.relevant_document
            and chunk.page_number == case.relevant_page
            and chunk.chunk_index == case.relevant_chunk_index
        )
