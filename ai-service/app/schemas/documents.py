from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.documents import DocumentRecord, DocumentSearchResult
from app.retrieval.models import RetrievalDebugCandidate, RetrievalMode
from app.schemas.inference import InferenceMetadata


class DocumentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[DocumentRecord]


class DocumentSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2_000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    document_ids: list[str] | None = Field(default=None, max_length=50)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized

    @field_validator("document_ids")
    @classmethod
    def validate_document_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = list(dict.fromkeys(item.strip() for item in value))
        if any(not item for item in normalized):
            raise ValueError("document identifiers must not be blank")
        return normalized


class DocumentSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[DocumentSearchResult]
    inference_metadata: InferenceMetadata | None


class RetrievalDebugRequest(DocumentSearchRequest):
    mode: RetrievalMode = "hybrid"


class RetrievalDebugResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    normalized_query: str
    mode: RetrievalMode
    vector_candidates: list[RetrievalDebugCandidate]
    bm25_candidates: list[RetrievalDebugCandidate]
    fused_candidates: list[RetrievalDebugCandidate]
    reranked_candidates: list[RetrievalDebugCandidate]
    final_context: list[RetrievalDebugCandidate]
    inference_metadata: InferenceMetadata | None
