from datetime import datetime
from hashlib import sha256
from threading import RLock
from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection

from app.models.datasets import DatasetRecord, StoredDataset
from app.models.documents import DocumentRecord, StoredDocumentChunk
from app.models.persistence import UploadIntent
from app.models.videos import StoredTemporalSegment, VideoRecord
from app.repositories.metadata import MetadataRepository


class MongoMetadataRepository(MetadataRepository):
    """MongoDB-backed durable authority using one discriminator-indexed collection."""

    def __init__(
        self,
        *,
        uri: str,
        database_name: str,
        connect_timeout_ms: int = 5_000,
        client: Any | None = None,
    ) -> None:
        self._client = client or MongoClient(
            uri,
            connect=False,
            connectTimeoutMS=connect_timeout_ms,
            serverSelectionTimeoutMS=connect_timeout_ms,
        )
        self._records: Collection[dict[str, Any]] = self._client[database_name]["metadata_records"]
        self._indexes_ready = False
        self._index_lock = RLock()

    def _ensure_indexes(self) -> None:
        with self._index_lock:
            if self._indexes_ready:
                return
            self._records.create_index(
                [("kind", ASCENDING), ("record_id", ASCENDING)],
                unique=True,
                name="kind_record_unique",
            )
            self._records.create_index(
                [("kind", ASCENDING), ("owner_id", ASCENDING)],
                name="kind_owner",
            )
            self._indexes_ready = True

    @staticmethod
    def _base(kind: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"kind": kind, "record_id": record_id, "payload": payload}

    def save_document(self, document: DocumentRecord, chunks: list[StoredDocumentChunk]) -> None:
        self._ensure_indexes()
        document_record = self._base(
            "document", document.document_id, document.model_dump(mode="python")
        )
        chunk_records = []
        for item in chunks:
            metadata = item.embedding_metadata
            record = self._base(
                "document_chunk", item.chunk.chunk_id, item.model_dump(mode="python")
            )
            record.update(
                {
                    "owner_id": item.chunk.document_id,
                    "text": item.chunk.text,
                    "checksum": item.chunk.checksum,
                    "created_at": item.chunk.created_at,
                    "embedding": item.embedding,
                    "embedding_model": metadata.model if metadata else "unknown",
                    "embedding_provider": metadata.provider if metadata else "unknown",
                }
            )
            chunk_records.append(record)
        try:
            self._records.insert_one(document_record)
            if chunk_records:
                self._records.insert_many(chunk_records, ordered=True)
        except Exception:
            self._records.delete_many(
                {
                    "$or": [
                        {"kind": "document", "record_id": document.document_id},
                        {"kind": "document_chunk", "owner_id": document.document_id},
                    ]
                }
            )
            raise

    def list_documents(self) -> list[DocumentRecord]:
        self._ensure_indexes()
        items = [
            DocumentRecord.model_validate(item["payload"])
            for item in self._records.find({"kind": "document"})
        ]
        return sorted(items, key=lambda item: (item.created_at, item.document_id), reverse=True)

    def get_document(self, document_id: str) -> DocumentRecord | None:
        self._ensure_indexes()
        item = self._records.find_one({"kind": "document", "record_id": document_id})
        return DocumentRecord.model_validate(item["payload"]) if item else None

    def get_document_chunks(self, document_id: str) -> list[StoredDocumentChunk]:
        self._ensure_indexes()
        return sorted(
            [
                StoredDocumentChunk.model_validate(item["payload"])
                for item in self._records.find({"kind": "document_chunk", "owner_id": document_id})
            ],
            key=lambda item: item.chunk.chunk_index,
        )

    def get_document_chunks_by_ids(self, chunk_ids: list[str]) -> list[StoredDocumentChunk]:
        self._ensure_indexes()
        if not chunk_ids:
            return []
        found = {
            item["record_id"]: StoredDocumentChunk.model_validate(item["payload"])
            for item in self._records.find(
                {"kind": "document_chunk", "record_id": {"$in": chunk_ids}}
            )
        }
        return [found[item] for item in chunk_ids if item in found]

    def list_document_chunks(
        self, document_ids: list[str] | None = None
    ) -> list[StoredDocumentChunk]:
        self._ensure_indexes()
        query: dict[str, Any] = {"kind": "document_chunk"}
        if document_ids is not None:
            query["owner_id"] = {"$in": document_ids}
        items = [
            StoredDocumentChunk.model_validate(item["payload"])
            for item in self._records.find(query)
        ]
        return sorted(items, key=lambda item: (item.chunk.document_id, item.chunk.chunk_index))

    def delete_document(self, document_id: str) -> bool:
        self._ensure_indexes()
        result = self._records.delete_one({"kind": "document", "record_id": document_id})
        self._records.delete_many({"kind": "document_chunk", "owner_id": document_id})
        return bool(result.deleted_count)

    def save_video(self, video: VideoRecord, segments: list[StoredTemporalSegment]) -> None:
        self._ensure_indexes()
        video_record = self._base("video", video.video_id, video.model_dump(mode="python"))
        segment_records = []
        for item in segments:
            metadata = item.segment.embedding_metadata
            record = self._base(
                "video_segment", item.segment.segment_id, item.model_dump(mode="python")
            )
            record.update(
                {
                    "owner_id": item.segment.video_id,
                    "text": item.segment.combined_text,
                    "checksum": sha256(item.segment.combined_text.encode("utf-8")).hexdigest(),
                    "created_at": video.created_at,
                    "embedding": item.embedding,
                    "embedding_model": metadata.model,
                    "embedding_provider": metadata.provider,
                }
            )
            segment_records.append(record)
        try:
            self._records.insert_one(video_record)
            if segment_records:
                self._records.insert_many(segment_records, ordered=True)
        except Exception:
            self._records.delete_many(
                {
                    "$or": [
                        {"kind": "video", "record_id": video.video_id},
                        {"kind": "video_segment", "owner_id": video.video_id},
                    ]
                }
            )
            raise

    def list_videos(self) -> list[VideoRecord]:
        self._ensure_indexes()
        items = [
            VideoRecord.model_validate(item["payload"])
            for item in self._records.find({"kind": "video"})
        ]
        return sorted(items, key=lambda item: (item.created_at, item.video_id), reverse=True)

    def list_video_segments(self) -> list[StoredTemporalSegment]:
        self._ensure_indexes()
        items = [
            StoredTemporalSegment.model_validate(item["payload"])
            for item in self._records.find({"kind": "video_segment"})
        ]
        return sorted(items, key=lambda item: (item.segment.video_id, item.segment.start_seconds))

    def get_video_segments_by_ids(self, segment_ids: list[str]) -> list[StoredTemporalSegment]:
        self._ensure_indexes()
        if not segment_ids:
            return []
        found = {
            item["record_id"]: StoredTemporalSegment.model_validate(item["payload"])
            for item in self._records.find(
                {"kind": "video_segment", "record_id": {"$in": segment_ids}}
            )
        }
        return [found[item] for item in segment_ids if item in found]

    def save_dataset(self, dataset: StoredDataset) -> None:
        self._ensure_indexes()
        self._records.insert_one(
            self._base("dataset", dataset.dataset.dataset_id, dataset.model_dump(mode="python"))
        )

    def list_datasets(self) -> list[DatasetRecord]:
        self._ensure_indexes()
        items = [
            StoredDataset.model_validate(item["payload"]).dataset
            for item in self._records.find({"kind": "dataset"})
        ]
        return sorted(items, key=lambda item: (item.created_at, item.dataset_id), reverse=True)

    def get_dataset(self, dataset_id: str) -> StoredDataset | None:
        self._ensure_indexes()
        item = self._records.find_one({"kind": "dataset", "record_id": dataset_id})
        return StoredDataset.model_validate(item["payload"]) if item else None

    def delete_dataset(self, dataset_id: str) -> bool:
        self._ensure_indexes()
        result = self._records.delete_one({"kind": "dataset", "record_id": dataset_id})
        return bool(result.deleted_count)

    def save_upload_intent(self, intent: UploadIntent) -> None:
        self._ensure_indexes()
        record = self._base("upload_intent", intent.object_path, intent.model_dump(mode="python"))
        record.update(
            {
                "owner_id": intent.upload_id,
                "expires_at": intent.expires_at,
                "consumed_at": intent.consumed_at,
            }
        )
        self._records.insert_one(record)

    def get_upload_intent(self, object_path: str) -> UploadIntent | None:
        self._ensure_indexes()
        item = self._records.find_one({"kind": "upload_intent", "record_id": object_path})
        return UploadIntent.model_validate(item["payload"]) if item else None

    def consume_upload_intent(self, object_path: str, consumed_at: datetime) -> bool:
        self._ensure_indexes()
        result = self._records.update_one(
            {"kind": "upload_intent", "record_id": object_path, "consumed_at": None},
            {"$set": {"consumed_at": consumed_at, "payload.consumed_at": consumed_at}},
        )
        return bool(result.modified_count)
