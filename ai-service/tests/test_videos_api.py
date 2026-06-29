import json
import subprocess
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.providers.errors import ProviderTransientError
from app.providers.mock import MockProvider
from app.services.video_factory import create_video_rag_service
from app.services.video_media import (
    FFmpegMediaProcessor,
    VideoMediaProcessor,
    VideoProbeMetadata,
)
from app.services.video_rag import VideoRAGService
from app.transcription.providers import MockTranscriptionProvider

SYNTHETIC_MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41"


class FakeMediaProcessor(VideoMediaProcessor):
    def __init__(self, *, duration_seconds: float = 6.0, has_audio: bool = True) -> None:
        self.duration_seconds = duration_seconds
        self.has_audio = has_audio
        self.keyframe_timestamps: list[float] = []

    def probe(self, video_path: Path) -> VideoProbeMetadata:
        assert video_path.is_file()
        return VideoProbeMetadata(
            duration_seconds=self.duration_seconds,
            width=640,
            height=360,
            has_audio=self.has_audio,
        )

    def extract_keyframe(
        self,
        video_path: Path,
        output_path: Path,
        *,
        timestamp_seconds: float,
    ) -> None:
        assert video_path.is_file()
        self.keyframe_timestamps.append(timestamp_seconds)
        output_path.write_bytes(b"synthetic-jpeg")

    def extract_audio(self, video_path: Path, output_path: Path) -> None:
        assert video_path.is_file()
        output_path.write_bytes(b"synthetic-wave")


class UnavailableVisionProvider(MockProvider):
    def describe_image(self, *, image_url: str, prompt: str):  # type: ignore[no-untyped-def]
        del image_url, prompt
        self.call_history.append("describe_image")
        raise ProviderTransientError("Vision is unavailable for this test.")


def _settings(*, vision_enabled: bool = True) -> Settings:
    return Settings(
        app_env="test",
        ai_provider="mock",
        max_video_size_mb=1,
        max_video_duration_seconds=60,
        max_keyframes=3,
        keyframe_interval_seconds=2,
        video_vision_enabled=vision_enabled,
        video_transcription_enabled=True,
        transcription_provider="mock",
        video_search_top_k=3,
        video_min_similarity_score=0,
    )


def _application(
    *,
    provider: MockProvider | None = None,
    media_processor: VideoMediaProcessor | None = None,
) -> FastAPI:
    settings = _settings()
    active_provider = provider or MockProvider()
    service = create_video_rag_service(
        settings,
        active_provider,
        media_processor=media_processor or FakeMediaProcessor(),
        transcription_provider=MockTranscriptionProvider(),
    )
    return create_app(settings, active_provider, video_service=service)


def _upload(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/videos",
        files={"file": ("portfolio.mp4", SYNTHETIC_MP4, "video/mp4")},
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def test_video_ingestion_uses_bounded_representative_keyframes_and_lists_video() -> None:
    media = FakeMediaProcessor()
    app = _application(media_processor=media)

    with TestClient(app) as client:
        uploaded = _upload(client)
        listed = client.get("/api/v1/videos")

    assert media.keyframe_timestamps == [0.0, 2.0, 4.0]
    assert uploaded["filename"] == "portfolio.mp4"
    assert uploaded["duration_seconds"] == 6.0
    assert uploaded["segment_count"] == 3
    assert uploaded["processing_status"] == "ready"
    assert uploaded["visual_enrichment"] == "completed"
    assert uploaded["transcription"] == "completed"
    assert listed.status_code == 200
    assert listed.json()["videos"] == [uploaded]


def test_temporal_segments_and_search_preserve_timestamp_provenance() -> None:
    app = _application()

    with TestClient(app) as client:
        uploaded = _upload(client)
        response = client.post(
            "/api/v1/search/videos",
            json={"query": "ORION-VIDEO", "top_k": 3},
        )

    service = cast(VideoRAGService, app.state.video_service)
    segments = service.list_segments()
    assert [(item.start_seconds, item.end_seconds) for item in segments] == [
        (0.0, 2.0),
        (2.0, 4.0),
        (4.0, 6.0),
    ]
    assert all(item.video_id == uploaded["video_id"] for item in segments)
    assert all(item.filename == "portfolio.mp4" for item in segments)
    assert all(item.keyframe_path.endswith(".jpg") for item in segments)
    assert all(item.embedding_metadata.provider == "mock" for item in segments)

    assert response.status_code == 200
    result = response.json()["results"][0]
    trusted = {item.segment_id: item for item in segments}[result["segment_id"]]
    assert result["video_id"] == trusted.video_id
    assert result["filename"] == trusted.filename
    assert result["start_seconds"] == trusted.start_seconds
    assert result["end_seconds"] == trusted.end_seconds
    assert 0 <= result["score"] <= 1


def test_graph_video_search_uses_actual_retriever_and_trusted_citation() -> None:
    app = _application()

    with TestClient(app) as client:
        _upload(client)
        response = client.post(
            "/api/v1/chat/invoke",
            json={
                "message": "What happened with ORION-VIDEO at 4 seconds in the uploaded video?",
                "thread_id": "video-provenance",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "video_search"
    assert "ORION-VIDEO" in payload["final_response"]
    assert "tool=video_search" in payload["trace"]
    citation = payload["citations"][0]
    service = cast(VideoRAGService, app.state.video_service)
    trusted = {item.segment_id: item for item in service.list_segments()}[citation["segment_id"]]
    assert citation["source_type"] == "video"
    assert citation["video_id"] == trusted.video_id
    assert citation["start_seconds"] == trusted.start_seconds
    assert citation["end_seconds"] == trusted.end_seconds


def test_unavailable_vision_preserves_partial_ingestion_and_stops_extra_calls() -> None:
    provider = UnavailableVisionProvider()
    app = _application(provider=provider)

    with TestClient(app) as client:
        uploaded = _upload(client)

    assert uploaded["processing_status"] == "partial"
    assert uploaded["visual_enrichment"] == "unavailable"
    assert uploaded["transcription"] == "completed"
    assert provider.call_history.count("describe_image") == 1
    service = cast(VideoRAGService, app.state.video_service)
    assert all(
        segment.visual_description == "Visual enrichment unavailable."
        for segment in service.list_segments()
    )


def test_invalid_and_masquerading_video_uploads_are_rejected() -> None:
    app = _application()

    with TestClient(app) as client:
        masquerading = client.post(
            "/api/v1/videos",
            files={"file": ("pretend.mp4", b"plain text", "video/mp4")},
        )
        wrong_extension = client.post(
            "/api/v1/videos",
            files={"file": ("video.txt", SYNTHETIC_MP4, "text/plain")},
        )

    assert masquerading.status_code == 415
    assert masquerading.json()["error"]["code"] == "INVALID_VIDEO_MEDIA_TYPE"
    assert wrong_extension.status_code == 415


def test_duration_limit_is_enforced_from_ffprobe_metadata() -> None:
    app = _application(media_processor=FakeMediaProcessor(duration_seconds=61))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/videos",
            files={"file": ("too-long.mp4", SYNTHETIC_MP4, "video/mp4")},
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "VIDEO_DURATION_EXCEEDED"


def test_ffprobe_invocation_uses_argument_list_timeout_and_no_shell(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = tmp_path / "videos"
    storage.mkdir()
    source = storage / "source.mp4"
    source.write_bytes(SYNTHETIC_MP4)
    observed: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed.update(kwargs)
        payload = {
            "streams": [
                {"codec_type": "video", "width": 640, "height": 360},
                {"codec_type": "audio"},
            ],
            "format": {"format_name": "mov,mp4,m4a", "duration": "6.0"},
        }
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    processor = FFmpegMediaProcessor(
        storage_root=storage,
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
        timeout_seconds=7,
    )
    metadata = processor.probe(source)

    assert metadata.duration_seconds == 6
    assert observed["command"] == [
        "ffprobe",
        "-v",
        "error",
        "-of",
        "json",
        "-show_format",
        "-show_streams",
        str(source.resolve()),
    ]
    assert observed["shell"] is False
    assert observed["timeout"] == 7


def test_media_processor_rejects_paths_outside_storage(tmp_path: Path) -> None:
    storage = tmp_path / "videos"
    storage.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(SYNTHETIC_MP4)
    processor = FFmpegMediaProcessor(
        storage_root=storage,
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
        timeout_seconds=7,
    )

    with pytest.raises(Exception, match="escaped the configured storage root"):
        processor.probe(outside)
