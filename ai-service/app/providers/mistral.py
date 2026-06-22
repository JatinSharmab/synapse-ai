import time
from collections.abc import Callable, Sequence
from typing import Any, TypeVar, cast

import httpx
from mistralai.client import Mistral
from mistralai.client.errors import MistralError, NoResponseError
from mistralai.client.models.chatcompletionrequest import ChatCompletionRequestMessageTypedDict
from mistralai.client.utils.retries import BackoffStrategy, RetryConfig
from pydantic import BaseModel, ValidationError

from app.providers.base import LLMProvider
from app.providers.errors import (
    ProviderRateLimitError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderTransientError,
)
from app.schemas.inference import (
    EmbeddingResult,
    GenerationResult,
    InferenceMetadata,
    InferenceOperation,
    ProviderInfo,
    ProviderModels,
    StructuredGenerationResult,
    TokenUsage,
)

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)
ResponseValue = TypeVar("ResponseValue")


class MistralProvider(LLMProvider):
    """Mistral SDK adapter with bounded, explicitly controlled retries."""

    def __init__(
        self,
        *,
        api_key: str,
        chat_model: str,
        vision_model: str,
        embedding_model: str,
        timeout_seconds: float,
        max_transient_retries: int,
    ) -> None:
        self._chat_model = chat_model
        self._vision_model = vision_model
        self._embedding_model = embedding_model
        self._timeout_ms = round(timeout_seconds * 1_000)
        self._max_transient_retries = max_transient_retries
        self._sdk_retry_config = RetryConfig(
            strategy="none",
            backoff=BackoffStrategy(
                initial_interval=0,
                max_interval=0,
                exponent=1,
                max_elapsed_time=0,
            ),
            retry_connection_errors=False,
        )
        self._client = Mistral(
            api_key=api_key,
            retry_config=self._sdk_retry_config,
            timeout_ms=self._timeout_ms,
        )

    def generate(self, *, system_prompt: str, user_prompt: str) -> GenerationResult:
        started = time.perf_counter()
        response, retry_count = self._request_with_retry(
            lambda: self._client.chat.complete(
                model=self._chat_model,
                messages=self._text_messages(system_prompt, user_prompt),
                retries=self._sdk_retry_config,
                timeout_ms=self._timeout_ms,
            )
        )
        text = self._extract_text(response)
        return GenerationResult(
            text=text,
            metadata=self._metadata(
                operation="generate",
                model=getattr(response, "model", self._chat_model),
                started=started,
                retry_count=retry_count,
                usage=getattr(response, "usage", None),
            ),
        )

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredModel],
    ) -> StructuredGenerationResult[StructuredModel]:
        started = time.perf_counter()
        response, retry_count = self._request_with_retry(
            lambda: self._client.chat.parse(
                response_format=response_model,
                model=self._chat_model,
                messages=self._text_messages(system_prompt, user_prompt),
                retries=self._sdk_retry_config,
                timeout_ms=self._timeout_ms,
            )
        )
        choices = getattr(response, "choices", None)
        if not choices or choices[0].message is None or choices[0].message.parsed is None:
            raise ProviderResponseError("Mistral returned no valid structured response.")
        try:
            value = response_model.model_validate(choices[0].message.parsed)
        except ValidationError as error:
            raise ProviderResponseError(
                "Mistral structured output did not match the requested schema."
            ) from error
        return StructuredGenerationResult[StructuredModel](
            value=value,
            metadata=self._metadata(
                operation="generate_structured",
                model=getattr(response, "model", self._chat_model),
                started=started,
                retry_count=retry_count,
                usage=getattr(response, "usage", None),
            ),
        )

    def describe_image(self, *, image_url: str, prompt: str) -> GenerationResult:
        started = time.perf_counter()
        messages = [
            {"role": "system", "content": "Describe the image accurately and concisely."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": image_url},
                ],
            },
        ]
        response, retry_count = self._request_with_retry(
            lambda: self._client.chat.complete(
                model=self._vision_model,
                messages=cast(Any, messages),
                retries=self._sdk_retry_config,
                timeout_ms=self._timeout_ms,
            )
        )
        text = self._extract_text(response)
        return GenerationResult(
            text=text,
            metadata=self._metadata(
                operation="describe_image",
                model=getattr(response, "model", self._vision_model),
                started=started,
                retry_count=retry_count,
                usage=getattr(response, "usage", None),
            ),
        )

    def embed(self, *, texts: Sequence[str]) -> EmbeddingResult:
        started = time.perf_counter()
        response, retry_count = self._request_with_retry(
            lambda: self._client.embeddings.create(
                model=self._embedding_model,
                inputs=list(texts),
                retries=self._sdk_retry_config,
                timeout_ms=self._timeout_ms,
            )
        )
        vectors = [item.embedding for item in response.data]
        if any(vector is None for vector in vectors):
            raise ProviderResponseError("Mistral returned an invalid embedding response.")
        return EmbeddingResult(
            vectors=cast(list[list[float]], vectors),
            metadata=self._metadata(
                operation="embed",
                model=getattr(response, "model", self._embedding_model),
                started=started,
                retry_count=retry_count,
                usage=getattr(response, "usage", None),
            ),
        )

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider="mistral",
            models=ProviderModels(
                chat=self._chat_model,
                vision=self._vision_model,
                embedding=self._embedding_model,
            ),
            mock=False,
        )

    @staticmethod
    def _text_messages(
        system_prompt: str,
        user_prompt: str,
    ) -> list[ChatCompletionRequestMessageTypedDict]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    @staticmethod
    def _extract_text(response: Any) -> str:
        choices = getattr(response, "choices", None)
        if not choices or choices[0].message is None:
            raise ProviderResponseError("Mistral returned no response message.")
        content = choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError("Mistral returned no text content.")
        return content.strip()

    def _request_with_retry(
        self,
        request: Callable[[], ResponseValue],
    ) -> tuple[ResponseValue, int]:
        for retry_count in range(self._max_transient_retries + 1):
            try:
                return request(), retry_count
            except MistralError as error:
                if error.status_code == 429:
                    raise ProviderRateLimitError(
                        "Mistral rate limit or quota was reached; the request was not retried."
                    ) from error
                is_transient = 500 <= error.status_code < 600
                if not is_transient:
                    raise ProviderRequestError("Mistral rejected the request.") from error
                if retry_count >= self._max_transient_retries:
                    raise ProviderTransientError("Mistral is temporarily unavailable.") from error
            except (NoResponseError, httpx.NetworkError, httpx.TimeoutException) as error:
                if retry_count >= self._max_transient_retries:
                    raise ProviderTransientError("Mistral could not be reached.") from error

            time.sleep(0.25 * (2**retry_count))

        raise ProviderTransientError("Mistral retry policy terminated unexpectedly.")

    @staticmethod
    def _metadata(
        *,
        operation: InferenceOperation,
        model: str,
        started: float,
        retry_count: int,
        usage: Any,
    ) -> InferenceMetadata:
        token_usage = None
        if usage is not None:
            input_tokens = getattr(usage, "prompt_tokens", None)
            output_tokens = getattr(usage, "completion_tokens", None)
            total_tokens = getattr(usage, "total_tokens", None)
            if all(isinstance(value, int) for value in (input_tokens, output_tokens, total_tokens)):
                token_usage = TokenUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                )
        return InferenceMetadata(
            provider="mistral",
            operation=operation,
            model=model,
            latency_ms=round((time.perf_counter() - started) * 1_000, 3),
            retry_count=retry_count,
            token_usage=token_usage,
        )
