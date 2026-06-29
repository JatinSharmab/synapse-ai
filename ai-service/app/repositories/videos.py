import os
from abc import ABC, abstractmethod
from pathlib import Path
from threading import RLock

from pydantic import BaseModel, ConfigDict, Field

from app.models.videos import StoredTemporalSegment, VideoRecord


class VideoRepository(ABC):
    @abstractmethod
    def save(self, video: VideoRecord, segments: list[StoredTemporalSegment]) -> None: ...

    @abstractmethod
    def list_videos(self) -> list[VideoRecord]: ...

    @abstractmethod
    def list_segments(self) -> list[StoredTemporalSegment]: ...

    @abstractmethod
    def get_segments_by_ids(self, segment_ids: list[str]) -> list[StoredTemporalSegment]: ...


class InMemoryVideoRepository(VideoRepository):
    def __init__(self) -> None:
        self._videos: dict[str, VideoRecord] = {}
        self._segments: dict[str, StoredTemporalSegment] = {}
        self._lock = RLock()

    def save(self, video: VideoRecord, segments: list[StoredTemporalSegment]) -> None:
        with self._lock:
            if video.video_id in self._videos:
                raise ValueError("video identifier already exists")
            self._videos[video.video_id] = video
            self._segments.update({item.segment.segment_id: item for item in segments})

    def list_videos(self) -> list[VideoRecord]:
        with self._lock:
            return sorted(
                self._videos.values(),
                key=lambda item: (item.created_at, item.video_id),
                reverse=True,
            )

    def list_segments(self) -> list[StoredTemporalSegment]:
        with self._lock:
            return sorted(
                self._segments.values(),
                key=lambda item: (item.segment.video_id, item.segment.start_seconds),
            )

    def get_segments_by_ids(self, segment_ids: list[str]) -> list[StoredTemporalSegment]:
        with self._lock:
            return [self._segments[item] for item in segment_ids if item in self._segments]


class _VideoSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    videos: list[VideoRecord] = Field(default_factory=list)
    segments: list[StoredTemporalSegment] = Field(default_factory=list)


class JsonVideoRepository(InMemoryVideoRepository):
    def __init__(self, path: Path) -> None:
        self._path = path
        super().__init__()
        self._load()

    def save(self, video: VideoRecord, segments: list[StoredTemporalSegment]) -> None:
        with self._lock:
            super().save(video, segments)
            try:
                self._flush()
            except Exception:
                self._videos.pop(video.video_id, None)
                self._segments = {
                    key: item
                    for key, item in self._segments.items()
                    if item.segment.video_id != video.video_id
                }
                raise

    def _load(self) -> None:
        if not self._path.exists():
            return
        snapshot = _VideoSnapshot.model_validate_json(self._path.read_text(encoding="utf-8"))
        self._videos = {item.video_id: item for item in snapshot.videos}
        self._segments = {item.segment.segment_id: item for item in snapshot.segments}

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = _VideoSnapshot(
            videos=list(self._videos.values()),
            segments=list(self._segments.values()),
        )
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, self._path)
