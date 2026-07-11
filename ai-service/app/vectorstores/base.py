from abc import ABC, abstractmethod
from math import sqrt
from threading import RLock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.documents import DocumentChunk

VectorNamespace = Literal["documents", "videos"]
VectorMetadataValue = str | int | float | bool


class VectorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    vector_id: str
    owner_id: str
    text: str
    embedding: list[float] = Field(min_length=1)
    metadata: dict[str, VectorMetadataValue]


class VectorSearchMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    vector_id: str
    distance: float = Field(ge=0)


class VectorStore(ABC):
    """Replaceable active-index contract; never the durable provenance authority."""

    @abstractmethod
    def upsert_records(self, namespace: VectorNamespace, records: list[VectorRecord]) -> None: ...

    @abstractmethod
    def query_records(
        self,
        namespace: VectorNamespace,
        embedding: list[float],
        *,
        top_k: int,
        owner_ids: list[str] | None = None,
    ) -> list[VectorSearchMatch]: ...

    @abstractmethod
    def delete_owner(self, namespace: VectorNamespace, owner_id: str) -> None: ...

    @abstractmethod
    def list_ids(self, namespace: VectorNamespace) -> set[str]: ...

    @abstractmethod
    def clear(self, namespace: VectorNamespace) -> None: ...

    def count(self, namespace: VectorNamespace) -> int:
        return len(self.list_ids(namespace))


class InMemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self._records: dict[VectorNamespace, dict[str, VectorRecord]] = {
            "documents": {},
            "videos": {},
        }
        self._lock = RLock()

    def upsert_records(self, namespace: VectorNamespace, records: list[VectorRecord]) -> None:
        with self._lock:
            self._records[namespace].update({item.vector_id: item for item in records})

    def query_records(
        self,
        namespace: VectorNamespace,
        embedding: list[float],
        *,
        top_k: int,
        owner_ids: list[str] | None = None,
    ) -> list[VectorSearchMatch]:
        allowed = set(owner_ids) if owner_ids is not None else None
        with self._lock:
            matches = [
                VectorSearchMatch(
                    vector_id=item.vector_id,
                    distance=self._cosine_distance(embedding, item.embedding),
                )
                for item in self._records[namespace].values()
                if allowed is None or item.owner_id in allowed
            ]
        return sorted(matches, key=lambda item: (item.distance, item.vector_id))[:top_k]

    def delete_owner(self, namespace: VectorNamespace, owner_id: str) -> None:
        with self._lock:
            self._records[namespace] = {
                key: item
                for key, item in self._records[namespace].items()
                if item.owner_id != owner_id
            }

    def list_ids(self, namespace: VectorNamespace) -> set[str]:
        with self._lock:
            return set(self._records[namespace])

    def clear(self, namespace: VectorNamespace) -> None:
        with self._lock:
            self._records[namespace].clear()

    @staticmethod
    def _cosine_distance(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return 2.0
        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 1.0
        similarity = sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)
        return max(0.0, 1.0 - similarity)


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

    @abstractmethod
    def list_ids(self) -> set[str]:
        """Return every indexed chunk identifier."""

    @abstractmethod
    def clear(self) -> None:
        """Remove every document vector from the active index."""
