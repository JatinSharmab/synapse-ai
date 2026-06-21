from pydantic import BaseModel, ConfigDict

from app.prompts.router import ROUTER_SYSTEM_PROMPT
from app.providers.errors import ProviderResponseError
from app.providers.mock import MockProvider
from app.schemas.inference import RouterClassification


class UnsupportedFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


def test_mock_provider_supports_all_provider_operations_without_network() -> None:
    provider = MockProvider()

    structured = provider.generate_structured(
        system_prompt=ROUTER_SYSTEM_PROMPT,
        user_prompt="Find this policy in my document",
        response_model=RouterClassification,
    )
    generated = provider.generate(
        system_prompt="test",
        user_prompt=(
            '{"rewrite_count":0,"route":"direct_answer","tool_result":null,'
            '"user_query":"Explain RAG"}'
        ),
    )
    described = provider.describe_image(image_url="data:image/png;base64,AA==", prompt="Describe")
    embedded = provider.embed(texts=["alpha", "beta"])

    assert structured.value.route.value == "document_search"
    assert "retrieval-augmented generation" in generated.text
    assert described.metadata.model == "mock-vision-v1"
    assert len(embedded.vectors) == 2
    assert provider.call_history == [
        "generate_structured",
        "generate",
        "describe_image",
        "embed",
    ]


def test_mock_structured_generation_rejects_unconfigured_schema() -> None:
    provider = MockProvider()

    try:
        provider.generate_structured(
            system_prompt="test",
            user_prompt="test",
            response_model=UnsupportedFixture,
        )
    except ProviderResponseError as error:
        assert error.code == "AI_PROVIDER_INVALID_RESPONSE"
    else:
        raise AssertionError("MockProvider must reject structured schemas without fixtures.")
