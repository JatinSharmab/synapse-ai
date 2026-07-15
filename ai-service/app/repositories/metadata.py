from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from app.models.datasets import DatasetRecord, StoredDataset
from app.models.documents import DocumentRecord, StoredDocumentChunk
from app.models.persistence import UploadIntent
from app.models.videos import StoredTemporalSegment, VideoRecord
from app.repositories.datasets import (
    DatasetRepository,
    InMemoryDatasetRepository,
    JsonDatasetRepository,
)
from app.repositories.documents import (
    DocumentRepository,
    InMemoryDocumentRepository,
    JsonDocumentRepository,
)
from app.repositories.videos import InMemoryVideoRepository, JsonVideoRepository, VideoRepository


class MetadataRepository(ABC):
    """Durable authority for metadata and embedding-backed reconstruction records."""

    @abstractmethod
    def save_document(
        self, document: DocumentRecord, chunks: list[StoredDocumentChunk]
    ) -> None: ...

    @abstractmethod
    def list_documents(self) -> list[DocumentRecord]: ...

    @abstractmethod
    def get_document(self, document_id: str) -> DocumentRecord | None: ...

    @abstractmethod
    def get_document_chunks(self, document_id: str) -> list[StoredDocumentChunk]: ...

    @abstractmethod
    def get_document_chunks_by_ids(self, chunk_ids: list[str]) -> list[StoredDocumentChunk]: ...

    @abstractmethod
    def list_document_chunks(
        self, document_ids: list[str] | None = None
    ) -> list[StoredDocumentChunk]: ...

    @abstractmethod
    def delete_document(self, document_id: str) -> bool: ...

    @abstractmethod
    def save_video(self, video: VideoRecord, segments: list[StoredTemporalSegment]) -> None: ...

    @abstractmethod
    def list_videos(self) -> list[VideoRecord]: ...

    @abstractmethod
    def list_video_segments(self) -> list[StoredTemporalSegment]: ...

    @abstractmethod
    def get_video_segments_by_ids(self, segment_ids: list[str]) -> list[StoredTemporalSegment]: ...

    @abstractmethod
    def save_dataset(self, dataset: StoredDataset) -> None: ...

    @abstractmethod
    def list_datasets(self) -> list[DatasetRecord]: ...

    @abstractmethod
    def get_dataset(self, dataset_id: str) -> StoredDataset | None: ...

    @abstractmethod
    def delete_dataset(self, dataset_id: str) -> bool: ...

    @abstractmethod
    def save_upload_intent(self, intent: UploadIntent) -> None: ...

    @abstractmethod
    def get_upload_intent(self, object_path: str) -> UploadIntent | None: ...

    @abstractmethod
    def consume_upload_intent(self, object_path: str, consumed_at: datetime) -> bool: ...


class LocalMetadataRepository(MetadataRepository):
    """Composes existing local JSON repositories behind the shared metadata contract."""

    def __init__(
        self,
        documents: DocumentRepository,
        videos: VideoRepository,
        datasets: DatasetRepository,
    ) -> None:
        self._documents = documents
        self._videos = videos
        self._datasets = datasets
        self._uploads: dict[str, UploadIntent] = {}

    @classmethod
    def in_memory(cls) -> "LocalMetadataRepository":
        return cls(
            InMemoryDocumentRepository(),
            InMemoryVideoRepository(),
            InMemoryDatasetRepository(),
        )

    @classmethod
    def json(
        cls, *, document_path: Path, video_path: Path, dataset_path: Path
    ) -> "LocalMetadataRepository":
        return cls(
            JsonDocumentRepository(Path(document_path)),
            JsonVideoRepository(Path(video_path)),
            JsonDatasetRepository(Path(dataset_path)),
        )

    def save_document(self, document: DocumentRecord, chunks: list[StoredDocumentChunk]) -> None:
        self._documents.save(document, chunks)

    def list_documents(self) -> list[DocumentRecord]:
        return self._documents.list_documents()

    def get_document(self, document_id: str) -> DocumentRecord | None:
        return self._documents.get_document(document_id)

    def get_document_chunks(self, document_id: str) -> list[StoredDocumentChunk]:
        return self._documents.get_chunks(document_id)

    def get_document_chunks_by_ids(self, chunk_ids: list[str]) -> list[StoredDocumentChunk]:
        return self._documents.get_chunks_by_ids(chunk_ids)

    def list_document_chunks(
        self, document_ids: list[str] | None = None
    ) -> list[StoredDocumentChunk]:
        return self._documents.list_chunks(document_ids)

    def delete_document(self, document_id: str) -> bool:
        return self._documents.delete(document_id)

    def save_video(self, video: VideoRecord, segments: list[StoredTemporalSegment]) -> None:
        self._videos.save(video, segments)

    def list_videos(self) -> list[VideoRecord]:
        return self._videos.list_videos()

    def list_video_segments(self) -> list[StoredTemporalSegment]:
        return self._videos.list_segments()

    def get_video_segments_by_ids(self, segment_ids: list[str]) -> list[StoredTemporalSegment]:
        return self._videos.get_segments_by_ids(segment_ids)

    def save_dataset(self, dataset: StoredDataset) -> None:
        self._datasets.save(dataset)

    def list_datasets(self) -> list[DatasetRecord]:
        return self._datasets.list_datasets()

    def get_dataset(self, dataset_id: str) -> StoredDataset | None:
        return self._datasets.get(dataset_id)

    def delete_dataset(self, dataset_id: str) -> bool:
        return self._datasets.delete(dataset_id)

    def save_upload_intent(self, intent: UploadIntent) -> None:
        if intent.object_path in self._uploads:
            raise ValueError("upload object path already exists")
        self._uploads[intent.object_path] = intent

    def get_upload_intent(self, object_path: str) -> UploadIntent | None:
        return self._uploads.get(object_path)

    def consume_upload_intent(self, object_path: str, consumed_at: datetime) -> bool:
        current = self._uploads.get(object_path)
        if current is None or current.consumed_at is not None:
            return False
        self._uploads[object_path] = current.model_copy(update={"consumed_at": consumed_at})
        return True


class DocumentMetadataAdapter(DocumentRepository):
    def __init__(self, repository: MetadataRepository) -> None:
        self._repository = repository

    def save(self, document: DocumentRecord, chunks: list[StoredDocumentChunk]) -> None:
        self._repository.save_document(document, chunks)

    def list_documents(self) -> list[DocumentRecord]:
        return self._repository.list_documents()

    def get_document(self, document_id: str) -> DocumentRecord | None:
        return self._repository.get_document(document_id)

    def get_chunks(self, document_id: str) -> list[StoredDocumentChunk]:
        return self._repository.get_document_chunks(document_id)

    def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[StoredDocumentChunk]:
        return self._repository.get_document_chunks_by_ids(chunk_ids)

    def list_chunks(self, document_ids: list[str] | None = None) -> list[StoredDocumentChunk]:
        return self._repository.list_document_chunks(document_ids)

    def delete(self, document_id: str) -> bool:
        return self._repository.delete_document(document_id)


class VideoMetadataAdapter(VideoRepository):
    def __init__(self, repository: MetadataRepository) -> None:
        self._repository = repository

    def save(self, video: VideoRecord, segments: list[StoredTemporalSegment]) -> None:
        self._repository.save_video(video, segments)

    def list_videos(self) -> list[VideoRecord]:
        return self._repository.list_videos()

    def list_segments(self) -> list[StoredTemporalSegment]:
        return self._repository.list_video_segments()

    def get_segments_by_ids(self, segment_ids: list[str]) -> list[StoredTemporalSegment]:
        return self._repository.get_video_segments_by_ids(segment_ids)


class DatasetMetadataAdapter(DatasetRepository):
    def __init__(self, repository: MetadataRepository) -> None:
        self._repository = repository

    def save(self, dataset: StoredDataset) -> None:
        self._repository.save_dataset(dataset)

    def list_datasets(self) -> list[DatasetRecord]:
        return self._repository.list_datasets()

    def get(self, dataset_id: str) -> StoredDataset | None:
        return self._repository.get_dataset(dataset_id)

    def delete(self, dataset_id: str) -> bool:
        return self._repository.delete_dataset(dataset_id)
