from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TypeVar

from pydantic import BaseModel

from app.schemas.inference import (
    EmbeddingResult,
    GenerationResult,
    ProviderInfo,
    StructuredGenerationResult,
)

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class LLMProvider(ABC):
    """Typed boundary around all model-provider operations."""

    @abstractmethod
    def generate(self, *, system_prompt: str, user_prompt: str) -> GenerationResult:
        """Generate a text response."""

    @abstractmethod
    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredModel],
    ) -> StructuredGenerationResult[StructuredModel]:
        """Generate and validate a response against a Pydantic model."""

    @abstractmethod
    def describe_image(
        self,
        *,
        image_url: str,
        prompt: str,
    ) -> GenerationResult:
        """Describe an image provided as a URL or data URL."""

    @abstractmethod
    def embed(self, *, texts: Sequence[str]) -> EmbeddingResult:
        """Create embedding vectors for input text."""

    @abstractmethod
    def info(self) -> ProviderInfo:
        """Return a credential-free provider description."""
