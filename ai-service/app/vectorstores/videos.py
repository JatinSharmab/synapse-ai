from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings
from pydantic import BaseModel, ConfigDict, Field

from app.models.videos import TemporalSegment


class VideoVectorMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    segment_id: str
    distance: float = Field(ge=0)


class VideoVectorStore(ABC):
    @abstractmethod
    def upsert(self, segments: list[TemporalSegment], embeddings: list[list[float]]) -> None: ...

    @abstractmethod
    def query(self, embedding: list[float], *, top_k: int) -> list[VideoVectorMatch]: ...

    @abstractmethod
    def delete_video(self, video_id: str) -> None: ...

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def list_ids(self) -> set[str]: ...

    @abstractmethod
    def clear(self) -> None: ...


class ChromaVideoVectorStore(VideoVectorStore):
    def __init__(self, *, collection_name: str, persist_path: Path | None) -> None:
        settings = ChromaSettings(anonymized_telemetry=False)
        self._client: ClientAPI
        if persist_path is None:
            self._client = chromadb.EphemeralClient(settings=settings)
        else:
            persist_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=persist_path, settings=settings)
        self._collection: Collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, segments: list[TemporalSegment], embeddings: list[list[float]]) -> None:
        if len(segments) != len(embeddings):
            raise ValueError("segment and embedding counts must match")
        if not segments:
            return
        metadatas: list[dict[str, str | float]] = [
            {
                "video_id": item.video_id,
                "filename": item.filename,
                "segment_id": item.segment_id,
                "start_seconds": item.start_seconds,
                "end_seconds": item.end_seconds,
            }
            for item in segments
        ]
        self._collection.upsert(
            ids=[item.segment_id for item in segments],
            embeddings=embeddings,
            metadatas=metadatas,
            documents=[item.combined_text for item in segments],
        )

    def query(self, embedding: list[float], *, top_k: int) -> list[VideoVectorMatch]:
        available = self.count()
        if available == 0:
            return []
        result: dict[str, Any] = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, available),
            include=["distances"],
        )
        ids = result.get("ids") or []
        distances = result.get("distances") or []
        if not ids or not distances:
            return []
        return [
            VideoVectorMatch(segment_id=segment_id, distance=float(distance))
            for segment_id, distance in zip(ids[0], distances[0], strict=True)
        ]

    def delete_video(self, video_id: str) -> None:
        self._collection.delete(where={"video_id": video_id})

    def count(self) -> int:
        return int(self._collection.count())

    def list_ids(self) -> set[str]:
        result = self._collection.get(include=[])
        return set(result.get("ids") or [])

    def clear(self) -> None:
        identifiers = list(self.list_ids())
        if identifiers:
            self._collection.delete(ids=identifiers)
