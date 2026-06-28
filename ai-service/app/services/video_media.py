import json
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.video_errors import VideoDependencyError, VideoProcessingError


class VideoProbeMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    duration_seconds: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    has_audio: bool


class VideoMediaProcessor(ABC):
    @abstractmethod
    def probe(self, video_path: Path) -> VideoProbeMetadata:
        """Validate the media container and return trusted stream metadata."""

    @abstractmethod
    def extract_keyframe(
        self,
        video_path: Path,
        output_path: Path,
        *,
        timestamp_seconds: float,
    ) -> None:
        """Extract one representative frame at a trusted timestamp."""

    @abstractmethod
    def extract_audio(self, video_path: Path, output_path: Path) -> None:
        """Extract bounded mono PCM audio for a transcription provider."""


class FFmpegMediaProcessor(VideoMediaProcessor):
    def __init__(
        self,
        *,
        storage_root: Path,
        ffmpeg_path: str,
        ffprobe_path: str,
        timeout_seconds: float,
    ) -> None:
        self._storage_root = storage_root.resolve()
        self._storage_root.mkdir(parents=True, exist_ok=True)
        self._ffmpeg_path = ffmpeg_path
        self._ffprobe_path = ffprobe_path
        self._timeout_seconds = timeout_seconds

    def probe(self, video_path: Path) -> VideoProbeMetadata:
        safe_input = self._safe_existing_path(video_path)
        completed = self._run(
            [
                self._ffprobe_path,
                "-v",
                "error",
                "-of",
                "json",
                "-show_format",
                "-show_streams",
                str(safe_input),
            ]
        )
        try:
            payload = json.loads(completed.stdout)
            streams = payload["streams"]
            video_stream = next(item for item in streams if item.get("codec_type") == "video")
            audio_streams = [item for item in streams if item.get("codec_type") == "audio"]
            format_data = payload["format"]
            format_name = str(format_data.get("format_name", ""))
            if "mp4" not in format_name and "mov" not in format_name:
                raise VideoProcessingError("The uploaded media is not an MP4 container.")
            return VideoProbeMetadata(
                duration_seconds=float(format_data["duration"]),
                width=int(video_stream["width"]),
                height=int(video_stream["height"]),
                has_audio=bool(audio_streams),
            )
        except (
            KeyError,
            StopIteration,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ValidationError,
        ) as error:
            raise VideoProcessingError("ffprobe returned invalid video metadata.") from error

    def extract_keyframe(
        self,
        video_path: Path,
        output_path: Path,
        *,
        timestamp_seconds: float,
    ) -> None:
        safe_input = self._safe_existing_path(video_path)
        safe_output = self._safe_output_path(output_path)
        self._run(
            [
                self._ffmpeg_path,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{timestamp_seconds:.3f}",
                "-i",
                str(safe_input),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(safe_output),
            ]
        )
        if not safe_output.is_file() or safe_output.stat().st_size == 0:
            raise VideoProcessingError("FFmpeg did not produce a representative keyframe.")

    def extract_audio(self, video_path: Path, output_path: Path) -> None:
        safe_input = self._safe_existing_path(video_path)
        safe_output = self._safe_output_path(output_path)
        self._run(
            [
                self._ffmpeg_path,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(safe_input),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(safe_output),
            ]
        )
        if not safe_output.is_file() or safe_output.stat().st_size == 0:
            raise VideoProcessingError("FFmpeg did not produce an audio artifact.")

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                command,
                shell=False,
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
        except FileNotFoundError as error:
            raise VideoDependencyError("FFmpeg and ffprobe must be installed locally.") from error
        except subprocess.TimeoutExpired as error:
            raise VideoProcessingError(
                "Video processing exceeded the configured timeout."
            ) from error
        if completed.returncode != 0:
            raise VideoProcessingError("FFmpeg could not process the uploaded video.")
        return completed

    def _safe_existing_path(self, path: Path) -> Path:
        resolved = self._inside_storage(path)
        if not resolved.is_file():
            raise VideoProcessingError("The staged video artifact is unavailable.")
        return resolved

    def _safe_output_path(self, path: Path) -> Path:
        resolved = self._inside_storage(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def _inside_storage(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(self._storage_root):
            raise VideoProcessingError("Video processing path escaped the configured storage root.")
        return resolved
