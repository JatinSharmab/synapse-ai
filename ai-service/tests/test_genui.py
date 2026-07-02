from pathlib import Path
from typing import TypeVar

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.core.config import Settings
from app.main import create_app
from app.providers.errors import ProviderResponseError
from app.providers.mock import MockProvider
from app.schemas.analytics import AnalyticsResult
from app.schemas.genui import GenUIComponent, GenUIResponse
from app.schemas.inference import StructuredGenerationResult
from app.services.genui import ground_analytics_genui

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)
COMPONENT_ADAPTER: TypeAdapter[GenUIComponent] = TypeAdapter(GenUIComponent)
SAMPLE_CSV = (
    Path(__file__).resolve().parents[2] / "sample-data" / "datasets" / "regional-revenue.csv"
)


class MalformedGenUIProvider(MockProvider):
    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredModel],
    ) -> StructuredGenerationResult[StructuredModel]:
        if response_model is GenUIResponse:
            self.call_history.append("generate_structured")
            raise ProviderResponseError("Malformed Gen-UI fixture.")
        return super().generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
        )


def _settings() -> Settings:
    return Settings(
        app_env="test",
        ai_provider="mock",
        dataset_max_upload_bytes=100_000,
        dataset_max_rows=100,
        dataset_max_columns=10,
        analytics_max_result_rows=20,
    )


def _application(provider: MockProvider | None = None) -> FastAPI:
    return create_app(_settings(), provider or MockProvider())


def _upload_dataset(client: TestClient) -> None:
    response = client.post(
        "/api/v1/datasets",
        files={"file": ("regional-revenue.csv", SAMPLE_CSV.read_bytes(), "text/csv")},
    )
    assert response.status_code == 201


def _valid_chart() -> dict[str, object]:
    return {
        "version": "1.0",
        "type": "bar_chart",
        "title": "Revenue by Region",
        "data": [
            {"region": "North", "revenue": 120},
            {"region": "South", "revenue": 95},
        ],
        "config": {"xKey": "region", "yKey": "revenue"},
    }


def test_valid_chart_payload_matches_versioned_protocol() -> None:
    component = COMPONENT_ADAPTER.validate_python(_valid_chart())

    assert component.type == "bar_chart"
    assert component.version == "1.0"
    assert component.model_dump(mode="json") == _valid_chart()


@pytest.mark.parametrize("component_type", ["dashboard", "custom_widget", "react_component"])
def test_invalid_and_unknown_component_types_are_rejected(component_type: str) -> None:
    with pytest.raises(ValidationError):
        COMPONENT_ADAPTER.validate_python({**_valid_chart(), "type": component_type})


def test_missing_required_fields_and_malformed_data_are_rejected() -> None:
    missing_config = _valid_chart()
    del missing_config["config"]
    malformed_data = {
        **_valid_chart(),
        "data": [{"region": "North", "revenue": "not-a-number"}],
    }

    with pytest.raises(ValidationError):
        COMPONENT_ADAPTER.validate_python(missing_config)
    with pytest.raises(ValidationError):
        COMPONENT_ADAPTER.validate_python(malformed_data)


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "<div onclick='run()'>unsafe</div>",
    ],
)
def test_html_script_and_event_handler_attempts_are_rejected(unsafe_text: str) -> None:
    with pytest.raises(ValidationError):
        COMPONENT_ADAPTER.validate_python({"version": "1.0", "type": "text", "text": unsafe_text})


def test_unknown_fields_and_invalid_chart_keys_are_rejected() -> None:
    unknown_field = {**_valid_chart(), "component": "ArbitraryReact"}
    missing_key = {
        **_valid_chart(),
        "config": {"xKey": "missing", "yKey": "revenue"},
    }
    duplicate_key = {
        **_valid_chart(),
        "config": {"xKey": "region", "yKey": "region"},
    }
    unsafe_key = {
        **_valid_chart(),
        "config": {"xKey": "region", "yKey": "revenue;alert(1)"},
    }

    for payload in (unknown_field, missing_key, duplicate_key, unsafe_key):
        with pytest.raises(ValidationError):
            COMPONENT_ADAPTER.validate_python(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"version": "1.0", "type": "text", "text": "Safe answer."},
        {"version": "1.0", "type": "metric", "label": "Revenue", "value": 120},
        {
            "version": "1.0",
            "type": "line_chart",
            "title": "Trend",
            "data": [{"month": "Jan", "value": 1}, {"month": "Feb", "value": 2}],
            "config": {"xKey": "month", "yKey": "value"},
        },
        {
            "version": "1.0",
            "type": "pie_chart",
            "title": "Share",
            "data": [{"region": "North", "value": 1}],
            "config": {"labelKey": "region", "valueKey": "value"},
        },
        {
            "version": "1.0",
            "type": "table",
            "title": "Rows",
            "columns": [{"key": "region", "label": "Region"}],
            "data": [{"region": "North"}],
        },
        {
            "version": "1.0",
            "type": "citation_list",
            "citations": [
                {
                    "citation_id": "citation_1",
                    "label": "Policy",
                    "locator": "policy.pdf, page 2",
                    "source_type": "document",
                }
            ],
        },
        {
            "version": "1.0",
            "type": "video_evidence",
            "items": [
                {
                    "video_id": "video_1",
                    "filename": "demo.mp4",
                    "segment_id": "segment_1",
                    "start_seconds": 2,
                    "end_seconds": 4,
                    "description": "A safe scene description.",
                }
            ],
        },
    ],
)
def test_every_allowlisted_component_has_a_strict_schema(payload: dict[str, object]) -> None:
    assert COMPONENT_ADAPTER.validate_python(payload).type == payload["type"]


def test_analytics_grounding_rejects_model_modified_values() -> None:
    result = AnalyticsResult(
        summary="Computed sum grouped by region.",
        columns=["region", "sum_revenue"],
        result_rows=[{"region": "North", "sum_revenue": 120}],
        statistics={"group_count": 1},
        recommended_visualization="bar_chart",
    )
    forged = GenUIResponse.model_validate(
        {
            "components": [
                {
                    "version": "1.0",
                    "type": "bar_chart",
                    "title": "Revenue",
                    "data": [{"region": "North", "sum_revenue": 999}],
                    "config": {"xKey": "region", "yKey": "sum_revenue"},
                }
            ]
        }
    )

    with pytest.raises(ValueError, match="did not match deterministic result rows"):
        ground_analytics_genui(forged, result)


def test_graph_returns_validated_grounded_genui_for_analytics() -> None:
    provider = MockProvider()
    app = _application(provider)

    with TestClient(app) as client:
        _upload_dataset(client)
        response = client.post(
            "/api/v1/chat/invoke",
            json={
                "message": "Compare revenue across regions.",
                "thread_id": "genui-grounded",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["final_response"].startswith("Computed sum grouped by region")
    assert payload["genui"] == [
        {
            "version": "1.0",
            "title": "Analytics result",
            "type": "bar_chart",
            "data": [
                {"region": "North", "sum_revenue": 200.75},
                {"region": "South", "sum_revenue": 245.75},
                {"region": "West", "sum_revenue": 180.5},
            ],
            "config": {"xKey": "region", "yKey": "sum_revenue"},
        }
    ]
    assert "genui=validated" in payload["trace"]
    assert provider.call_history == [
        "generate_structured",
        "generate_structured",
        "generate_structured",
    ]


def test_malformed_provider_genui_falls_back_to_safe_text() -> None:
    provider = MalformedGenUIProvider()
    app = _application(provider)

    with TestClient(app) as client:
        _upload_dataset(client)
        response = client.post(
            "/api/v1/chat/invoke",
            json={
                "message": "Compare revenue across regions.",
                "thread_id": "genui-fallback",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["final_response"].startswith("Computed sum grouped by region")
    assert payload["genui"] == []
    assert "genui=fallback_safe_text" in payload["trace"]
