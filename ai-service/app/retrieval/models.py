from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.documents import DocumentChunk

RetrievalMode = Literal["vector_only", "hybrid"]


class StrictRetrievalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RankedChunk(StrictRetrievalModel):
    chunk: DocumentChunk
    score: float = Field(allow_inf_nan=False)
    rank: int = Field(ge=1)


class FusedChunk(StrictRetrievalModel):
    chunk: DocumentChunk
    score: float = Field(ge=0, allow_inf_nan=False)
    vector_rank: int | None = Field(default=None, ge=1)
    bm25_rank: int | None = Field(default=None, ge=1)


class RerankedChunk(StrictRetrievalModel):
    chunk: DocumentChunk
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    rrf_score: float = Field(ge=0, allow_inf_nan=False)
    query_coverage: float = Field(ge=0, le=1)
    exact_phrase: bool


class RetrievalDebugCandidate(StrictRetrievalModel):
    rank: int = Field(ge=1)
    chunk_id: str
    document_id: str
    filename: str
    page: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    score: float = Field(allow_inf_nan=False)
    text: str


class RetrievalDebug(StrictRetrievalModel):
    query: str
    normalized_query: str
    mode: RetrievalMode
    vector_candidates: list[RetrievalDebugCandidate]
    bm25_candidates: list[RetrievalDebugCandidate]
    fused_candidates: list[RetrievalDebugCandidate]
    reranked_candidates: list[RetrievalDebugCandidate]
    final_context: list[RetrievalDebugCandidate]
