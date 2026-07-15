from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings

from app.models.documents import DocumentChunk
from app.vectorstores.base import DocumentVectorStore, VectorMatch


class ChromaDocumentVectorStore(DocumentVectorStore):
    """Chroma adapter that never delegates embedding to Chroma."""

    def __init__(
        self,
        *,
        collection_name: str,
        persist_path: Path | None = None,
    ) -> None:
        self._client: ClientAPI
        client_settings = ChromaSettings(anonymized_telemetry=False)
        if persist_path is None:
            self._client = chromadb.EphemeralClient(settings=client_settings)
        else:
            persist_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=persist_path, settings=client_settings)
        self._collection: Collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunk and embedding counts must match")
        if not chunks:
            return
        metadatas: list[dict[str, str | int]] = [
            {
                "document_id": chunk.document_id,
                "filename": chunk.filename,
                "page_number": chunk.page_number,
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "token_estimate": chunk.token_estimate,
                "checksum": chunk.checksum,
                "created_at": chunk.created_at.isoformat(),
            }
            for chunk in chunks
        ]
        self._collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=embeddings,
            metadatas=metadatas,
            documents=[chunk.text for chunk in chunks],
        )

    def query(
        self,
        embedding: list[float],
        *,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[VectorMatch]:
        available = self.count()
        if available == 0:
            return []
        where: Any = None
        if document_ids:
            where = {"document_id": {"$in": document_ids}}
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, available),
            where=where,
            include=["distances"],
        )
        ids = result.get("ids") or []
        distances = result.get("distances") or []
        if not ids or not distances:
            return []
        return [
            VectorMatch(chunk_id=chunk_id, distance=float(distance))
            for chunk_id, distance in zip(ids[0], distances[0], strict=True)
        ]

    def delete_document(self, document_id: str) -> None:
        self._collection.delete(where=cast(Any, {"document_id": document_id}))

    def count(self) -> int:
        return int(self._collection.count())

    def list_ids(self) -> set[str]:
        result = self._collection.get(include=[])
        return set(result.get("ids") or [])

    def clear(self) -> None:
        identifiers = list(self.list_ids())
        if identifiers:
            self._collection.delete(ids=identifiers)
