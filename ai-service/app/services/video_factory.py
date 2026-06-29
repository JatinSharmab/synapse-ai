from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from app.core.config import Settings
from app.providers.base import LLMProvider
from app.repositories.videos import InMemoryVideoRepository, JsonVideoRepository, VideoRepository
from app.services.video_media import FFmpegMediaProcessor, VideoMediaProcessor
from app.services.video_rag import VideoRAGService
from app.transcription.base import TranscriptionProvider
from app.transcription.factory import create_transcription_provider
from app.vectorstores.videos import ChromaVideoVectorStore


def create_video_rag_service(
    settings: Settings,
    provider: LLMProvider,
    *,
    media_processor: VideoMediaProcessor | None = None,
    transcription_provider: TranscriptionProvider | None = None,
    repository: VideoRepository | None = None,
) -> VideoRAGService:
    if settings.app_env == "test":
        active_repository = repository or InMemoryVideoRepository()
        persist_path = None
        storage_root = Path(gettempdir()) / "synapse-video-tests" / uuid4().hex
        collection_name = f"phase6_test_{uuid4().hex}"
    else:
        active_repository = repository or JsonVideoRepository(settings.video_metadata_path)
        persist_path = settings.chroma_persist_path
        storage_root = settings.video_storage_path
        collection_name = settings.chroma_video_collection

    active_media_processor = media_processor or FFmpegMediaProcessor(
        storage_root=storage_root,
        ffmpeg_path=settings.ffmpeg_path,
        ffprobe_path=settings.ffprobe_path,
        timeout_seconds=settings.video_subprocess_timeout_seconds,
    )
    service = VideoRAGService(
        provider=provider,
        transcription_provider=(transcription_provider or create_transcription_provider(settings)),
        repository=active_repository,
        vector_store=ChromaVideoVectorStore(
            collection_name=collection_name,
            persist_path=persist_path,
        ),
        media_processor=active_media_processor,
        storage_root=storage_root,
        max_video_size_bytes=settings.max_video_size_mb * 1024 * 1024,
        max_duration_seconds=settings.max_video_duration_seconds,
        max_keyframes=settings.max_keyframes,
        keyframe_interval_seconds=settings.keyframe_interval_seconds,
        vision_enabled=settings.video_vision_enabled,
        transcription_enabled=settings.video_transcription_enabled,
        minimum_similarity_score=settings.video_min_similarity_score,
    )
    service.rebuild_index_if_needed()
    return service
