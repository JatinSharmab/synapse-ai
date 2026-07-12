from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.config import Settings
from app.models.documents import DocumentRecord
from app.models.persistence import AssetType, UploadIntent
from app.models.videos import VideoRecord
from app.repositories.metadata import MetadataRepository
from app.schemas.uploads import PresignUploadRequest, PresignUploadResponse
from app.services.document_rag import DocumentRAGService
from app.services.video_rag import MP4_MEDIA_TYPES, VideoRAGService
from app.storage.base import ObjectStorageProvider

PDF_MEDIA_TYPES = frozenset({"application/pdf"})


class UploadIntentError(ValueError):
    pass


class UploadCoordinator:
    def __init__(
        self,
        *,
        settings: Settings,
        metadata: MetadataRepository,
        objects: ObjectStorageProvider,
        documents: DocumentRAGService,
        videos: VideoRAGService,
    ) -> None:
        self._settings = settings
        self._metadata = metadata
        self._objects = objects
        self._documents = documents
        self._videos = videos

    def presign(self, request: PresignUploadRequest) -> PresignUploadResponse:
        self._validate_request(request)
        upload_id = uuid4().hex
        prefix = "documents" if request.asset_type == AssetType.DOCUMENT else "videos"
        object_path = f"{prefix}/{upload_id}/{request.filename}"
        signed = self._objects.create_signed_upload(object_path)
        now = datetime.now(UTC)
        intent = UploadIntent(
            upload_id=upload_id,
            asset_type=request.asset_type,
            object_path=object_path,
            filename=request.filename,
            content_type=request.content_type,
            size_bytes=request.size_bytes,
            created_at=now,
            expires_at=min(
                signed.expires_at,
                now + timedelta(seconds=self._settings.upload_intent_ttl_seconds),
            ),
        )
        self._metadata.save_upload_intent(intent)
        return PresignUploadResponse(
            signed_upload_url=signed.url,
            object_path=object_path,
            expires_at=intent.expires_at,
        )

    def ingest_document(self, object_path: str) -> DocumentRecord:
        intent = self._intent(object_path, AssetType.DOCUMENT)
        data = self._download(intent, self._settings.document_max_upload_bytes)
        result = self._documents.ingest_pdf(
            filename=intent.filename,
            content_type=intent.content_type,
            data=data,
        )
        self._consume(intent)
        return result

    def ingest_video(self, object_path: str) -> VideoRecord:
        intent = self._intent(object_path, AssetType.VIDEO)
        data = self._download(intent, self._settings.max_video_size_mb * 1024 * 1024)
        result = self._videos.ingest_mp4(
            filename=intent.filename,
            content_type=intent.content_type,
            data=data,
        )
        self._consume(intent)
        return result

    def _validate_request(self, request: PresignUploadRequest) -> None:
        if request.asset_type == AssetType.DOCUMENT:
            valid = (
                request.filename.casefold().endswith(".pdf")
                and request.content_type in PDF_MEDIA_TYPES
            )
            limit = self._settings.document_max_upload_bytes
        else:
            valid = (
                request.filename.casefold().endswith(".mp4")
                and request.content_type in MP4_MEDIA_TYPES
            )
            limit = self._settings.max_video_size_mb * 1024 * 1024
        if not valid:
            raise UploadIntentError(
                "The filename or media type is not allowed for this asset type."
            )
        if request.size_bytes > limit:
            raise UploadIntentError("The proposed upload exceeds the configured size limit.")

    def _intent(self, object_path: str, expected: AssetType) -> UploadIntent:
        intent = self._metadata.get_upload_intent(object_path)
        if intent is None or intent.asset_type != expected:
            raise UploadIntentError("No matching upload authorization exists.")
        if intent.consumed_at is not None:
            raise UploadIntentError("The upload authorization has already been consumed.")
        if intent.expires_at <= datetime.now(UTC):
            raise UploadIntentError("The upload authorization has expired.")
        return intent

    def _download(self, intent: UploadIntent, limit: int) -> bytes:
        data = self._objects.download(intent.object_path, max_bytes=limit)
        if len(data) != intent.size_bytes:
            raise UploadIntentError(
                "The stored object size does not match its upload authorization."
            )
        return data

    def _consume(self, intent: UploadIntent) -> None:
        if not self._metadata.consume_upload_intent(intent.object_path, datetime.now(UTC)):
            raise UploadIntentError("The upload authorization could not be consumed.")
