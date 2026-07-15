import json
import re
from collections import deque
from collections.abc import Sequence
from hashlib import sha256
from math import sqrt
from typing import TypeVar

from pydantic import BaseModel

from app.models.domain import Route
from app.providers.base import LLMProvider
from app.providers.errors import ProviderResponseError
from app.schemas.analytics import AnalyticsPlan
from app.schemas.genui import GenUIResponse
from app.schemas.guardrails import SemanticGroundingJudgement
from app.schemas.inference import (
    EmbeddingResult,
    GenerationResult,
    InferenceMetadata,
    InferenceOperation,
    ProviderInfo,
    ProviderModels,
    RouterClassification,
    StructuredGenerationResult,
    TokenUsage,
)
from app.services.analytics_planning import plan_for_mock
from app.services.genui import genui_for_mock
from app.services.routing_rules import classify_for_mock

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)
MOCK_EMBEDDING_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "document",
        "documents",
        "find",
        "for",
        "in",
        "is",
        "my",
        "of",
        "on",
        "the",
        "this",
        "to",
        "what",
    }
)


class MockProvider(LLMProvider):
    """Deterministic provider used for local development and every automated test."""

    CHAT_MODEL = "mock-chat-v1"
    VISION_MODEL = "mock-vision-v1"
    EMBEDDING_MODEL = "mock-embedding-v1"

    def __init__(self, *, generated_responses: Sequence[str] = ()) -> None:
        self._generated_responses = deque(generated_responses)
        self.call_history: list[str] = []

    @staticmethod
    def _usage(input_text: str, output_text: str = "") -> TokenUsage:
        input_tokens = len(input_text.split())
        output_tokens = len(output_text.split())
        return TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )

    def _metadata(
        self,
        *,
        operation: InferenceOperation,
        model: str,
        input_text: str,
        output_text: str = "",
    ) -> InferenceMetadata:
        return InferenceMetadata(
            provider="mock",
            operation=operation,
            model=model,
            latency_ms=0,
            retry_count=0,
            token_usage=self._usage(input_text, output_text),
        )

    def generate(self, *, system_prompt: str, user_prompt: str) -> GenerationResult:
        del system_prompt
        self.call_history.append("generate")
        if self._generated_responses:
            text = self._generated_responses.popleft()
        else:
            text = self._synthesize(user_prompt)
        return GenerationResult(
            text=text,
            metadata=self._metadata(
                operation="generate",
                model=self.CHAT_MODEL,
                input_text=user_prompt,
                output_text=text,
            ),
        )

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredModel],
    ) -> StructuredGenerationResult[StructuredModel]:
        del system_prompt
        self.call_history.append("generate_structured")
        if response_model is GenUIResponse:
            proposal = genui_for_mock(user_prompt)
            value = response_model.model_validate(proposal.model_dump(mode="json"))
        elif response_model is SemanticGroundingJudgement:
            value = response_model.model_validate(
                {
                    "claim_supported": True,
                    "context_relevant": True,
                    "reason_code": "supported",
                }
            )
        elif response_model is AnalyticsPlan:
            plan = plan_for_mock(user_prompt)
            value = response_model.model_validate(plan.model_dump(mode="json"))
        elif response_model is RouterClassification:
            classification = classify_for_mock(user_prompt)
            value = response_model.model_validate(classification.model_dump(mode="json"))
        else:
            raise ProviderResponseError("MockProvider has no fixture for this structured schema.")
        return StructuredGenerationResult[StructuredModel](
            value=value,
            metadata=self._metadata(
                operation="generate_structured",
                model=self.CHAT_MODEL,
                input_text=user_prompt,
                output_text=value.model_dump_json(),
            ),
        )

    def describe_image(self, *, image_url: str, prompt: str) -> GenerationResult:
        del image_url
        self.call_history.append("describe_image")
        text = "Mock image description; no image data was sent to a network service."
        return GenerationResult(
            text=text,
            metadata=self._metadata(
                operation="describe_image",
                model=self.VISION_MODEL,
                input_text=prompt,
                output_text=text,
            ),
        )

    def embed(self, *, texts: Sequence[str]) -> EmbeddingResult:
        self.call_history.append("embed")
        vectors = [self._deterministic_vector(text) for text in texts]
        joined = " ".join(texts)
        return EmbeddingResult(
            vectors=vectors,
            metadata=self._metadata(
                operation="embed",
                model=self.EMBEDDING_MODEL,
                input_text=joined,
            ),
        )

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider="mock",
            models=ProviderModels(
                chat=self.CHAT_MODEL,
                vision=self.VISION_MODEL,
                embedding=self.EMBEDDING_MODEL,
            ),
            mock=True,
        )

    @staticmethod
    def _deterministic_vector(text: str) -> list[float]:
        vector = [0.0] * 256
        for token in re.findall(r"\w+", text.casefold()):
            if token in MOCK_EMBEDDING_STOP_WORDS:
                continue
            digest = sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:2]) % len(vector)] += 1.0
        magnitude = sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            vector[0] = 1.0
            return vector
        return [value / magnitude for value in vector]

    @staticmethod
    def _synthesize(user_prompt: str) -> str:
        try:
            payload = json.loads(user_prompt)
        except json.JSONDecodeError as error:
            raise ProviderResponseError("Mock synthesis input was not valid JSON.") from error

        query = str(payload.get("user_query", ""))
        route = payload.get("route")
        tool_result = payload.get("tool_result")
        if route == Route.DIRECT_ANSWER.value:
            if "rag" in query.casefold():
                return (
                    "RAG means retrieval-augmented generation: a system retrieves relevant "
                    "evidence and gives it to a language model before the model answers."
                )
            return f"Mock mode generated a direct response for: {query}"

        if route == Route.DOCUMENT_SEARCH.value:
            retrieved_context = payload.get("retrieved_context")
            if isinstance(retrieved_context, list) and retrieved_context:
                first = retrieved_context[0]
                if isinstance(first, dict) and isinstance(first.get("content"), str):
                    return f"Retrieved document evidence states: {first['content']}"
            return "No indexed document evidence was found for this request."

        if route == Route.VIDEO_SEARCH.value:
            retrieved_context = payload.get("retrieved_context")
            if isinstance(retrieved_context, list) and retrieved_context:
                first = retrieved_context[0]
                if isinstance(first, dict) and isinstance(first.get("content"), str):
                    return f"Retrieved timestamped video evidence states: {first['content']}"
            return "No indexed timestamped video evidence was found for this request."

        summary = "The selected capability is not implemented."
        if isinstance(tool_result, dict) and isinstance(tool_result.get("summary"), str):
            summary = tool_result["summary"]
        return f"Synapse selected {route}. {summary} No retrieval result was fabricated."
