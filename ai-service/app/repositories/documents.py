import os
from abc import ABC, abstractmethod
from pathlib import Path
from threading import RLock

from pydantic import BaseModel, ConfigDict, Field

from app.models.documents import DocumentChunk, DocumentRecord, StoredDocumentChunk


class DocumentRepository(ABC):
    @abstractmethod
    def save(self, document: DocumentRecord, chunks: list[StoredDocumentChunk]) -> None:
        """Persist one document and all of its chunks atomically."""

    @abstractmethod
    def list_documents(self) -> list[DocumentRecord]:
        """Return documents in stable newest-first order."""

    @abstractmethod
    def get_document(self, document_id: str) -> DocumentRecord | None:
        """Return a document by opaque identifier."""

    @abstractmethod
    def get_chunks(self, document_id: str) -> list[StoredDocumentChunk]:
        """Return all chunks for a document in chunk-index order."""

    @abstractmethod
    def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[StoredDocumentChunk]:
        """Return trusted chunk records for vector matches."""

    @abstractmethod
    def list_chunks(self, document_ids: list[str] | None = None) -> list[StoredDocumentChunk]:
        """Return the trusted lexical corpus, optionally restricted to documents."""

    @abstractmethod
    def delete(self, document_id: str) -> bool:
        """Delete metadata and chunks, returning whether a document existed."""


class InMemoryDocumentRepository(DocumentRepository):
    def __init__(self) -> None:
        self._documents: dict[str, DocumentRecord] = {}
        self._chunks: dict[str, StoredDocumentChunk] = {}
        self._lock = RLock()

    def save(self, document: DocumentRecord, chunks: list[StoredDocumentChunk]) -> None:
        with self._lock:
            if document.document_id in self._documents:
                raise ValueError("document identifier already exists")
            self._documents[document.document_id] = document
            self._chunks.update({item.chunk.chunk_id: item for item in chunks})

    def list_documents(self) -> list[DocumentRecord]:
        with self._lock:
            return sorted(
                self._documents.values(),
                key=lambda item: (item.created_at, item.document_id),
                reverse=True,
            )

    def get_document(self, document_id: str) -> DocumentRecord | None:
        with self._lock:
            return self._documents.get(document_id)

    def get_chunks(self, document_id: str) -> list[StoredDocumentChunk]:
        with self._lock:
            return sorted(
                (item for item in self._chunks.values() if item.chunk.document_id == document_id),
                key=lambda item: item.chunk.chunk_index,
            )

    def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[StoredDocumentChunk]:
        with self._lock:
            return [self._chunks[chunk_id] for chunk_id in chunk_ids if chunk_id in self._chunks]

    def list_chunks(self, document_ids: list[str] | None = None) -> list[StoredDocumentChunk]:
        with self._lock:
            allowed = set(document_ids) if document_ids is not None else None
            return sorted(
                (
                    item
                    for item in self._chunks.values()
                    if allowed is None or item.chunk.document_id in allowed
                ),
                key=lambda item: (item.chunk.document_id, item.chunk.chunk_index),
            )

    def delete(self, document_id: str) -> bool:
        with self._lock:
            if self._documents.pop(document_id, None) is None:
                return False
            self._chunks = {
                chunk_id: item
                for chunk_id, item in self._chunks.items()
                if item.chunk.document_id != document_id
            }
            return True


class _RepositorySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documents: list[DocumentRecord] = Field(default_factory=list)
    chunks: list[StoredDocumentChunk] = Field(default_factory=list)


class JsonDocumentRepository(InMemoryDocumentRepository):
    """Small local-development repository with atomic snapshot replacement."""

    def __init__(self, path: Path) -> None:
        self._path = path
        super().__init__()
        self._load()

    def save(self, document: DocumentRecord, chunks: list[StoredDocumentChunk]) -> None:
        with self._lock:
            super().save(document, chunks)
            try:
                self._flush()
            except Exception:
                super().delete(document.document_id)
                raise

    def delete(self, document_id: str) -> bool:
        with self._lock:
            document = self._documents.get(document_id)
            chunks = self.get_chunks(document_id)
            if not super().delete(document_id):
                return False
            try:
                self._flush()
            except Exception:
                if document is not None:
                    self._documents[document_id] = document
                    self._chunks.update({item.chunk.chunk_id: item for item in chunks})
                raise
            return True

    def _load(self) -> None:
        if not self._path.exists():
            return
        snapshot = _RepositorySnapshot.model_validate_json(self._path.read_text(encoding="utf-8"))
        self._documents = {item.document_id: item for item in snapshot.documents}
        self._chunks = {item.chunk.chunk_id: item for item in snapshot.chunks}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = _RepositorySnapshot(
            documents=list(self._documents.values()),
            chunks=list(self._chunks.values()),
        )
        temporary_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary_path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary_path, self._path)


def public_chunks(items: list[StoredDocumentChunk]) -> list[DocumentChunk]:
    return [item.chunk for item in items]
