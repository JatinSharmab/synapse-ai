from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

from app.models.documents import DocumentChunk


class VectorMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    distance: float = Field(ge=0)


class DocumentVectorStore(ABC):
    @abstractmethod
    def upsert(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        """Index chunks with caller-provided embeddings."""

    @abstractmethod
    def query(
        self,
        embedding: list[float],
        *,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[VectorMatch]:
        """Return nearest chunk identifiers and distances."""

    @abstractmethod
    def delete_document(self, document_id: str) -> None:
        """Delete every vector belonging to a document."""

    @abstractmethod
    def count(self) -> int:
        """Return indexed vector count."""
