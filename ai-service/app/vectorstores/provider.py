from pathlib import Path
from typing import Any

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings

from app.vectorstores.base import (
    VectorNamespace,
    VectorRecord,
    VectorSearchMatch,
    VectorStore,
)


class ChromaVectorStore(VectorStore):
    """Multi-namespace Chroma active index using caller-supplied embeddings only."""

    def __init__(
        self,
        *,
        collection_names: dict[VectorNamespace, str],
        persist_path: Path | None,
    ) -> None:
        settings = ChromaSettings(anonymized_telemetry=False)
        self._client: ClientAPI
        if persist_path is None:
            self._client = chromadb.EphemeralClient(settings=settings)
        else:
            persist_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=persist_path, settings=settings)
        self._collections: dict[VectorNamespace, Collection] = {
            namespace: self._client.get_or_create_collection(
                name=name,
                embedding_function=None,
                metadata={"hnsw:space": "cosine"},
            )
            for namespace, name in collection_names.items()
        }

    def upsert_records(self, namespace: VectorNamespace, records: list[VectorRecord]) -> None:
        if not records:
            return
        self._collections[namespace].upsert(
            ids=[item.vector_id for item in records],
            embeddings=[item.embedding for item in records],
            documents=[item.text for item in records],
            metadatas=[{"owner_id": item.owner_id, **item.metadata} for item in records],
        )

    def query_records(
        self,
        namespace: VectorNamespace,
        embedding: list[float],
        *,
        top_k: int,
        owner_ids: list[str] | None = None,
    ) -> list[VectorSearchMatch]:
        available = self.count(namespace)
        if available == 0:
            return []
        where: Any = None
        if owner_ids:
            where = {"owner_id": {"$in": owner_ids}}
        result = self._collections[namespace].query(
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
            VectorSearchMatch(vector_id=vector_id, distance=float(distance))
            for vector_id, distance in zip(ids[0], distances[0], strict=True)
        ]

    def delete_owner(self, namespace: VectorNamespace, owner_id: str) -> None:
        self._collections[namespace].delete(where={"owner_id": owner_id})

    def list_ids(self, namespace: VectorNamespace) -> set[str]:
        result = self._collections[namespace].get(include=[])
        return set(result.get("ids") or [])

    def clear(self, namespace: VectorNamespace) -> None:
        identifiers = list(self.list_ids(namespace))
        if identifiers:
            self._collections[namespace].delete(ids=identifiers)
