from app.core.config import Settings
from app.providers.base import LLMProvider
from app.providers.errors import ProviderConfigurationError
from app.providers.mistral import MistralProvider
from app.providers.mock import MockProvider


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.ai_provider == "mock":
        return MockProvider()

    api_key = settings.mistral_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        raise ProviderConfigurationError("MISTRAL_API_KEY must be set when AI_PROVIDER=mistral.")
    return MistralProvider(
        api_key=api_key.get_secret_value(),
        chat_model=settings.mistral_chat_model,
        vision_model=settings.mistral_vision_model,
        embedding_model=settings.mistral_embed_model,
        timeout_seconds=settings.ai_request_timeout_seconds,
        max_transient_retries=settings.ai_max_transient_retries,
    )
