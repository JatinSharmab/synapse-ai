from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_chat_invoke_returns_safe_graph_state_summary() -> None:
    app = create_app(Settings(app_env="test", ai_provider="mock"))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat/invoke",
            json={
                "message": "Find the relevant page in the PDF document",
                "thread_id": "thread-api",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["thread_id"] == "thread-api"
    assert payload["route"] == "document_search"
    assert payload["trace"] == [
        "guardrail.input=pass",
        "router.selected=document_search",
        "provider.router=mock",
        "tool=document_search",
        "retrieval.count=0",
        "synthesizer=draft",
        "provider.synthesizer=mock",
        "guardrail.grounding=pass",
        "guardrail.output=pass",
        "sentinel=approve",
    ]
    assert payload["guardrail_result"] == {
        "decision": "approve",
        "groundedness_score": 1.0,
        "citation_coverage": 1.0,
        "prompt_injection_detected": False,
        "schema_valid": True,
        "reasons": ["GUARDRAILS_PASSED"],
        "rewrite_required": False,
    }
    assert [item["operation"] for item in payload["inference_metadata"]] == [
        "generate_structured",
        "generate",
    ]
    assert "user_query" not in payload
    assert "draft_response" not in payload
    assert "retrieved_context" not in payload
    assert "tool_results" not in payload


def test_chat_invoke_rejects_unknown_fields() -> None:
    app = create_app(Settings(app_env="test", ai_provider="mock"))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat/invoke",
            json={
                "message": "Hello",
                "thread_id": "thread-api",
                "private_reasoning": "return this",
            },
        )

    assert response.status_code == 422
