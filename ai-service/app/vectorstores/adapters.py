from app.models.documents import DocumentChunk
from app.models.videos import TemporalSegment
from app.vectorstores.base import (
    DocumentVectorStore,
    VectorMatch,
    VectorRecord,
    VectorStore,
)
from app.vectorstores.videos import VideoVectorMatch, VideoVectorStore


class DocumentVectorStoreAdapter(DocumentVectorStore):
    def __init__(self, store: VectorStore) -> None:
        self._store = store

    def upsert(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunk and embedding counts must match")
        self._store.upsert_records(
            "documents",
            [
                VectorRecord(
                    vector_id=chunk.chunk_id,
                    owner_id=chunk.document_id,
                    text=chunk.text,
                    embedding=embedding,
                    metadata={
                        "document_id": chunk.document_id,
                        "filename": chunk.filename,
                        "page_number": chunk.page_number,
                        "chunk_index": chunk.chunk_index,
                        "checksum": chunk.checksum,
                        "created_at": chunk.created_at.isoformat(),
                    },
                )
                for chunk, embedding in zip(chunks, embeddings, strict=True)
            ],
        )

    def query(
        self,
        embedding: list[float],
        *,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[VectorMatch]:
        return [
            VectorMatch(chunk_id=item.vector_id, distance=item.distance)
            for item in self._store.query_records(
                "documents", embedding, top_k=top_k, owner_ids=document_ids
            )
        ]

    def delete_document(self, document_id: str) -> None:
        self._store.delete_owner("documents", document_id)

    def count(self) -> int:
        return self._store.count("documents")

    def list_ids(self) -> set[str]:
        return self._store.list_ids("documents")

    def clear(self) -> None:
        self._store.clear("documents")


class VideoVectorStoreAdapter(VideoVectorStore):
    def __init__(self, store: VectorStore) -> None:
        self._store = store

    def upsert(self, segments: list[TemporalSegment], embeddings: list[list[float]]) -> None:
        if len(segments) != len(embeddings):
            raise ValueError("segment and embedding counts must match")
        self._store.upsert_records(
            "videos",
            [
                VectorRecord(
                    vector_id=segment.segment_id,
                    owner_id=segment.video_id,
                    text=segment.combined_text,
                    embedding=embedding,
                    metadata={
                        "video_id": segment.video_id,
                        "filename": segment.filename,
                        "start_seconds": segment.start_seconds,
                        "end_seconds": segment.end_seconds,
                        "embedding_model": segment.embedding_metadata.model,
                    },
                )
                for segment, embedding in zip(segments, embeddings, strict=True)
            ],
        )

    def query(self, embedding: list[float], *, top_k: int) -> list[VideoVectorMatch]:
        return [
            VideoVectorMatch(segment_id=item.vector_id, distance=item.distance)
            for item in self._store.query_records("videos", embedding, top_k=top_k)
        ]

    def delete_video(self, video_id: str) -> None:
        self._store.delete_owner("videos", video_id)

    def count(self) -> int:
        return self._store.count("videos")

    def list_ids(self) -> set[str]:
        return self._store.list_ids("videos")

    def clear(self) -> None:
        self._store.clear("videos")
