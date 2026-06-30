from app.core.config import Settings
from app.transcription.base import TranscriptionProvider
from app.transcription.providers import DisabledTranscriptionProvider, MockTranscriptionProvider


def create_transcription_provider(settings: Settings) -> TranscriptionProvider:
    if settings.transcription_provider == "mock":
        return MockTranscriptionProvider()
    return DisabledTranscriptionProvider()
