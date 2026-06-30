from pathlib import Path

from app.transcription.base import TranscriptionProvider, TranscriptionResult, TranscriptionSpan


class DisabledTranscriptionProvider(TranscriptionProvider):
    def transcribe(self, *, audio_path: Path, duration_seconds: float) -> TranscriptionResult:
        del audio_path, duration_seconds
        return TranscriptionResult(
            provider="disabled",
            available=False,
            spans=[],
            reason="Transcription is disabled.",
        )


class MockTranscriptionProvider(TranscriptionProvider):
    """Deterministic offline transcription used by tests and local demos."""

    def transcribe(self, *, audio_path: Path, duration_seconds: float) -> TranscriptionResult:
        del audio_path
        midpoint = max(0.001, duration_seconds / 2)
        return TranscriptionResult(
            provider="mock",
            available=True,
            spans=[
                TranscriptionSpan(
                    start_seconds=0,
                    end_seconds=midpoint,
                    text="The portfolio video introduces the Synapse roadmap.",
                ),
                TranscriptionSpan(
                    start_seconds=midpoint,
                    end_seconds=duration_seconds,
                    text="The demonstration closes with marker ORION-VIDEO.",
                ),
            ],
        )
