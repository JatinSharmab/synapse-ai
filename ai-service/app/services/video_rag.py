import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.models.videos import (
    EnrichmentStatus,
    ProcessingStatus,
    StoredTemporalSegment,
    TemporalSegment,
    VideoRecord,
    VideoSearchResult,
)
from app.providers.base import LLMProvider
from app.providers.errors import ProviderError
from app.repositories.videos import VideoRepository
from app.schemas.inference import InferenceMetadata
from app.services.video_errors import (
    VideoDurationError,
    VideoMediaTypeError,
    VideoProcessingError,
    VideoStorageError,
    VideoTooLargeError,
    VideoValidationError,
)
from app.services.video_media import VideoMediaProcessor
from app.transcription.base import TranscriptionProvider, TranscriptionSpan
from app.vectorstores.videos import ChromaVideoVectorStore

MP4_MEDIA_TYPES = frozenset({"video/mp4", "application/mp4"})


@dataclass(frozen=True)
class VideoSearchExecution:
    results: list[VideoSearchResult]
    inference_metadata: InferenceMetadata | None


class VideoRetriever(Protocol):
    def search(self, query: str, *, top_k: int) -> VideoSearchExecution: ...


class EmptyVideoRetriever:
    def search(self, query: str, *, top_k: int) -> VideoSearchExecution:
        del query, top_k
        return VideoSearchExecution(results=[], inference_metadata=None)


@dataclass(frozen=True)
class _SegmentDraft:
    start_seconds: float
    end_seconds: float
    transcript: str
    visual_description: str
    combined_text: str
    keyframe_path: Path


class VideoRAGService:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        transcription_provider: TranscriptionProvider,
        repository: VideoRepository,
        vector_store: ChromaVideoVectorStore,
        media_processor: VideoMediaProcessor,
        storage_root: Path,
        max_video_size_bytes: int,
        max_duration_seconds: float,
        max_keyframes: int,
        keyframe_interval_seconds: float,
        vision_enabled: bool,
        transcription_enabled: bool,
        minimum_similarity_score: float,
    ) -> None:
        self._provider = provider
        self._transcription_provider = transcription_provider
        self._repository = repository
        self._vector_store = vector_store
        self._media_processor = media_processor
        self._storage_root = storage_root.resolve()
        self._storage_root.mkdir(parents=True, exist_ok=True)
        self._max_video_size_bytes = max_video_size_bytes
        self._max_duration_seconds = max_duration_seconds
        self._max_keyframes = max_keyframes
        self._keyframe_interval_seconds = keyframe_interval_seconds
        self._vision_enabled = vision_enabled
        self._transcription_enabled = transcription_enabled
        self._minimum_similarity_score = minimum_similarity_score

    def ingest_mp4(self, *, filename: str, content_type: str | None, data: bytes) -> VideoRecord:
        safe_filename = self._validate_upload(filename, content_type, data)
        video_id = f"video_{uuid4().hex}"
        artifact_root = self._storage_root / video_id
        artifact_root.mkdir(parents=True, exist_ok=False)
        video_path = artifact_root / "source.mp4"
        video_path.write_bytes(data)

        metadata = self._media_processor.probe(video_path)
        if metadata.duration_seconds > self._max_duration_seconds:
            raise VideoDurationError("The video exceeds the configured duration limit.")

        timestamps = self._representative_timestamps(metadata.duration_seconds)
        keyframes: list[Path] = []
        for index, timestamp in enumerate(timestamps):
            keyframe_path = artifact_root / f"keyframe-{index:03d}.jpg"
            self._media_processor.extract_keyframe(
                video_path,
                keyframe_path,
                timestamp_seconds=timestamp,
            )
            keyframes.append(keyframe_path)

        visual_descriptions, visual_status = self._describe_keyframes(keyframes)
        transcript_spans, transcription_status = self._transcribe(
            video_path=video_path,
            audio_path=artifact_root / "audio.wav",
            duration_seconds=metadata.duration_seconds,
            has_audio=metadata.has_audio,
        )
        drafts = self._build_segment_drafts(
            timestamps=timestamps,
            duration_seconds=metadata.duration_seconds,
            keyframes=keyframes,
            visual_descriptions=visual_descriptions,
            transcript_spans=transcript_spans,
        )
        embedding_result = self._provider.embed(texts=[item.combined_text for item in drafts])
        if len(embedding_result.vectors) != len(drafts) or any(
            not vector for vector in embedding_result.vectors
        ):
            raise VideoStorageError("The embedding provider returned an invalid video batch.")

        segments = [
            TemporalSegment(
                video_id=video_id,
                filename=safe_filename,
                segment_id=self._segment_id(video_id, draft.start_seconds, draft.end_seconds),
                start_seconds=draft.start_seconds,
                end_seconds=draft.end_seconds,
                transcript=draft.transcript,
                visual_description=draft.visual_description,
                combined_text=draft.combined_text,
                keyframe_path=self._relative_artifact_path(draft.keyframe_path),
                embedding_metadata=embedding_result.metadata,
            )
            for draft in drafts
        ]
        processing_status = (
            ProcessingStatus.PARTIAL
            if EnrichmentStatus.UNAVAILABLE in (visual_status, transcription_status)
            else ProcessingStatus.READY
        )
        video = VideoRecord(
            video_id=video_id,
            filename=safe_filename,
            duration_seconds=metadata.duration_seconds,
            size_bytes=len(data),
            width=metadata.width,
            height=metadata.height,
            has_audio=metadata.has_audio,
            segment_count=len(segments),
            processing_status=processing_status,
            visual_enrichment=visual_status,
            transcription=transcription_status,
            created_at=datetime.now(UTC),
        )
        self._vector_store.upsert(segments, embedding_result.vectors)
        stored = [
            StoredTemporalSegment(segment=segment, embedding=embedding)
            for segment, embedding in zip(segments, embedding_result.vectors, strict=True)
        ]
        try:
            self._repository.save(video, stored)
        except Exception as error:
            self._vector_store.delete_video(video_id)
            raise VideoStorageError("Video metadata could not be persisted.") from error
        return video

    def list_videos(self) -> list[VideoRecord]:
        return self._repository.list_videos()

    def list_segments(self) -> list[TemporalSegment]:
        """Expose persisted segment metadata without exposing stored embedding vectors."""

        return [item.segment for item in self._repository.list_segments()]

    def search(self, query: str, *, top_k: int) -> VideoSearchExecution:
        if self._vector_store.count() == 0:
            return VideoSearchExecution(results=[], inference_metadata=None)
        embedding_result = self._provider.embed(texts=[" ".join(query.split())])
        if len(embedding_result.vectors) != 1 or not embedding_result.vectors[0]:
            raise VideoStorageError("The embedding provider returned an invalid video query.")
        matches = self._vector_store.query(embedding_result.vectors[0], top_k=top_k)
        trusted = {
            item.segment.segment_id: item.segment
            for item in self._repository.get_segments_by_ids(
                [match.segment_id for match in matches]
            )
        }
        results: list[VideoSearchResult] = []
        for match in matches:
            segment = trusted.get(match.segment_id)
            if segment is None:
                continue
            score = max(0.0, min(1.0, 1.0 - match.distance))
            if score < self._minimum_similarity_score:
                continue
            results.append(
                VideoSearchResult(
                    video_id=segment.video_id,
                    filename=segment.filename,
                    segment_id=segment.segment_id,
                    start_seconds=segment.start_seconds,
                    end_seconds=segment.end_seconds,
                    description=segment.combined_text,
                    score=score,
                )
            )
        return VideoSearchExecution(results=results, inference_metadata=embedding_result.metadata)

    def rebuild_index_if_needed(self) -> None:
        stored = self._repository.list_segments()
        if self._vector_store.count() == len(stored):
            return
        self._vector_store.upsert(
            [item.segment for item in stored],
            [item.embedding for item in stored],
        )

    def _validate_upload(self, filename: str, content_type: str | None, data: bytes) -> str:
        safe_filename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
        if not safe_filename or len(safe_filename) > 255:
            raise VideoValidationError("The MP4 filename is invalid.")
        if not safe_filename.casefold().endswith(".mp4"):
            raise VideoMediaTypeError("The uploaded filename must use the .mp4 extension.")
        if content_type not in MP4_MEDIA_TYPES:
            raise VideoMediaTypeError("Only video/mp4 uploads are accepted.")
        if not data:
            raise VideoValidationError("The uploaded MP4 is empty.")
        if len(data) > self._max_video_size_bytes:
            raise VideoTooLargeError("The uploaded MP4 exceeds the configured size limit.")
        if b"ftyp" not in data[4:32]:
            raise VideoMediaTypeError("The uploaded file does not contain an MP4 signature.")
        return safe_filename

    def _representative_timestamps(self, duration_seconds: float) -> list[float]:
        timestamps: list[float] = []
        current = 0.0
        while current < duration_seconds and len(timestamps) < self._max_keyframes:
            timestamps.append(round(current, 3))
            current += self._keyframe_interval_seconds
        return timestamps or [0.0]

    def _describe_keyframes(
        self,
        keyframes: list[Path],
    ) -> tuple[list[str], EnrichmentStatus]:
        if not self._vision_enabled:
            return ["Visual enrichment disabled." for _ in keyframes], EnrichmentStatus.DISABLED
        descriptions: list[str] = []
        for index, keyframe in enumerate(keyframes):
            try:
                encoded = base64.b64encode(keyframe.read_bytes()).decode("ascii")
                result = self._provider.describe_image(
                    image_url=f"data:image/jpeg;base64,{encoded}",
                    prompt=(
                        "Describe only the visible scene for timestamp retrieval in one sentence."
                    ),
                )
                descriptions.append(result.text)
            except (ProviderError, OSError):
                descriptions.extend("Visual enrichment unavailable." for _ in keyframes[index:])
                return descriptions, EnrichmentStatus.UNAVAILABLE
        return descriptions, EnrichmentStatus.COMPLETED

    def _transcribe(
        self,
        *,
        video_path: Path,
        audio_path: Path,
        duration_seconds: float,
        has_audio: bool,
    ) -> tuple[list[TranscriptionSpan], EnrichmentStatus]:
        if not self._transcription_enabled:
            return [], EnrichmentStatus.DISABLED
        if not has_audio:
            return [], EnrichmentStatus.UNAVAILABLE
        try:
            self._media_processor.extract_audio(video_path, audio_path)
            result = self._transcription_provider.transcribe(
                audio_path=audio_path,
                duration_seconds=duration_seconds,
            )
        except Exception:
            return [], EnrichmentStatus.UNAVAILABLE
        if not result.available:
            return [], EnrichmentStatus.UNAVAILABLE
        return result.spans, EnrichmentStatus.COMPLETED

    def _build_segment_drafts(
        self,
        *,
        timestamps: list[float],
        duration_seconds: float,
        keyframes: list[Path],
        visual_descriptions: list[str],
        transcript_spans: list[TranscriptionSpan],
    ) -> list[_SegmentDraft]:
        drafts: list[_SegmentDraft] = []
        for index, start_seconds in enumerate(timestamps):
            end_seconds = timestamps[index + 1] if index + 1 < len(timestamps) else duration_seconds
            transcript = " ".join(
                span.text
                for span in transcript_spans
                if span.start_seconds < end_seconds and span.end_seconds > start_seconds
            )
            visual = visual_descriptions[index]
            useful_visual = "" if visual.endswith(("disabled.", "unavailable.")) else visual
            combined = " ".join(item for item in (transcript, useful_visual) if item).strip()
            if not combined:
                combined = (
                    f"Video segment from {start_seconds:.3f} to {end_seconds:.3f} seconds; {visual}"
                )
            drafts.append(
                _SegmentDraft(
                    start_seconds=start_seconds,
                    end_seconds=end_seconds,
                    transcript=transcript,
                    visual_description=visual,
                    combined_text=combined,
                    keyframe_path=keyframes[index],
                )
            )
        return drafts

    def _relative_artifact_path(self, path: Path) -> str:
        resolved = path.resolve()
        if not resolved.is_relative_to(self._storage_root):
            raise VideoProcessingError("Keyframe path escaped the video storage root.")
        return resolved.relative_to(self._storage_root).as_posix()

    @staticmethod
    def _segment_id(video_id: str, start_seconds: float, end_seconds: float) -> str:
        digest = sha256(f"{video_id}:{start_seconds:.3f}:{end_seconds:.3f}".encode()).hexdigest()
        return f"segment_{digest[:24]}"
