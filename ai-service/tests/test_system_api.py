from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.providers.errors import ProviderRateLimitError
from app.providers.mock import MockProvider
from app.schemas.inference import GenerationResult


class RateLimitedMockProvider(MockProvider):
    def __init__(self) -> None:
        super().__init__()
        self.generation_attempts = 0

    def generate(self, *, system_prompt: str, user_prompt: str) -> GenerationResult:
        del system_prompt, user_prompt
        self.generation_attempts += 1
        raise ProviderRateLimitError("Provider quota or rate limit was reached.")


def test_provider_endpoint_returns_safe_mock_configuration() -> None:
    settings = Settings(
        app_env="test",
        ai_provider="mock",
        mistral_api_key="must-never-be-returned",
        mistral_chat_model="private-unused-chat-setting",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/system/ai-provider")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "mock",
        "models": {
            "chat": "mock-chat-v1",
            "vision": "mock-vision-v1",
            "embedding": "mock-embedding-v1",
        },
        "mock": True,
    }
    assert "must-never-be-returned" not in response.text
    assert "api_key" not in response.text


def test_application_starts_in_mock_mode_without_mistral_credentials() -> None:
    settings = Settings(app_env="test", ai_provider="mock", mistral_api_key=None)

    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200


def test_provider_rate_limit_returns_safe_429_without_retry() -> None:
    provider = RateLimitedMockProvider()
    app = create_app(Settings(app_env="test", ai_provider="mock"), provider=provider)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat/invoke",
            json={"message": "Explain RAG", "thread_id": "rate-limit-test"},
        )

    assert response.status_code == 429
    assert response.json() == {
        "error": {
            "code": "AI_PROVIDER_RATE_LIMITED",
            "message": "Provider quota or rate limit was reached.",
            "retryable": False,
        }
    }
    assert provider.generation_attempts == 1
