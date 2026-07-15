import ast
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.providers.mock import MockProvider
from app.schemas.analytics import AnalyticsExecuteRequest

SAMPLE_CSV = (
    Path(__file__).resolve().parents[2] / "sample-data" / "datasets" / "regional-revenue.csv"
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


def _upload(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/api/v1/datasets",
        files={"file": ("regional-revenue.csv", SAMPLE_CSV.read_bytes(), "text/csv")},
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def _execute(
    client: TestClient,
    dataset_id: object,
    operation: dict[str, object],
) -> dict[str, object]:
    response = client.post(
        "/api/v1/analytics/execute",
        json={"dataset_id": dataset_id, "operation": operation},
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json())


def test_csv_upload_infers_typed_schema_and_lists_dataset() -> None:
    app = _application()

    with TestClient(app) as client:
        uploaded = _upload(client)
        listed = client.get("/api/v1/datasets")

    assert uploaded["filename"] == "regional-revenue.csv"
    assert uploaded["row_count"] == 6
    assert len(cast(str, uploaded["checksum"])) == 64
    assert uploaded["columns"] == [
        {"name": "region", "data_type": "string", "nullable": False},
        {"name": "product", "data_type": "string", "nullable": False},
        {"name": "revenue", "data_type": "number", "nullable": False},
        {"name": "units", "data_type": "number", "nullable": False},
        {"name": "active", "data_type": "boolean", "nullable": False},
    ]
    assert listed.status_code == 200
    assert listed.json()["datasets"] == [uploaded]


@pytest.mark.parametrize(
    ("operation", "column", "expected"),
    [
        ({"operation": "count"}, "count", 6),
        ({"operation": "sum", "column": "revenue"}, "sum", 627),
        ({"operation": "mean", "column": "revenue"}, "mean", 104.5),
        ({"operation": "min", "column": "revenue"}, "min", 70.5),
        ({"operation": "max", "column": "revenue"}, "max", 150),
    ],
)
def test_scalar_operations_are_calculated_deterministically(
    operation: dict[str, object],
    column: str,
    expected: int | float,
) -> None:
    app = _application()

    with TestClient(app) as client:
        uploaded = _upload(client)
        result = _execute(client, uploaded["dataset_id"], operation)

    assert result["result_rows"] == [{column: expected}]
    assert result["statistics"] == {column: expected}
    assert result["recommended_visualization"] == "metric"


def test_describe_returns_deterministic_column_statistics() -> None:
    app = _application()

    with TestClient(app) as client:
        uploaded = _upload(client)
        result = _execute(
            client,
            uploaded["dataset_id"],
            {"operation": "describe", "columns": ["region", "revenue"]},
        )

    rows = cast(list[dict[str, object]], result["result_rows"])
    assert rows[0] == {
        "column": "region",
        "type": "string",
        "non_null_count": 6,
        "unique_count": 3,
    }
    assert rows[1]["min"] == 70.5
    assert rows[1]["max"] == 150
    assert rows[1]["mean"] == 104.5


def test_group_by_preserves_group_fields_and_computes_source_values() -> None:
    app = _application()

    with TestClient(app) as client:
        uploaded = _upload(client)
        result = _execute(
            client,
            uploaded["dataset_id"],
            {
                "operation": "group_by",
                "grouping_fields": ["region"],
                "aggregation": "sum",
                "aggregation_field": "revenue",
                "limit": 10,
            },
        )

    assert result["result_rows"] == [
        {"region": "North", "sum_revenue": 200.75},
        {"region": "South", "sum_revenue": 245.75},
        {"region": "West", "sum_revenue": 180.5},
    ]
    assert result["statistics"] == {"group_count": 3, "returned_rows": 3}
    assert result["recommended_visualization"] == "bar_chart"


def test_sort_and_top_n_are_bounded_and_deterministic() -> None:
    app = _application()

    with TestClient(app) as client:
        uploaded = _upload(client)
        sorted_result = _execute(
            client,
            uploaded["dataset_id"],
            {
                "operation": "sort",
                "sort_fields": [{"column": "revenue", "direction": "asc"}],
                "limit": 2,
            },
        )
        top_result = _execute(
            client,
            uploaded["dataset_id"],
            {"operation": "top_n", "column": "revenue", "n": 2},
        )

    sorted_rows = cast(list[dict[str, object]], sorted_result["result_rows"])
    top_rows = cast(list[dict[str, object]], top_result["result_rows"])
    assert [row["revenue"] for row in sorted_rows] == [70.5, 80.25]
    assert [row["revenue"] for row in top_rows] == [150, 120.5]


def test_multi_aggregation_uses_only_validated_fixed_functions() -> None:
    app = _application()

    with TestClient(app) as client:
        uploaded = _upload(client)
        result = _execute(
            client,
            uploaded["dataset_id"],
            {
                "operation": "aggregation",
                "grouping_fields": ["region"],
                "aggregations": [
                    {"function": "sum", "field": "revenue", "alias": "total_revenue"},
                    {"function": "mean", "field": "units", "alias": "average_units"},
                    {"function": "count", "field": None, "alias": "row_count"},
                ],
                "limit": 10,
            },
        )

    assert result["result_rows"] == [
        {
            "region": "North",
            "total_revenue": 200.75,
            "average_units": 9,
            "row_count": 2,
        },
        {
            "region": "South",
            "total_revenue": 245.75,
            "average_units": 10.5,
            "row_count": 2,
        },
        {
            "region": "West",
            "total_revenue": 180.5,
            "average_units": 9,
            "row_count": 2,
        },
    ]


def test_unknown_non_numeric_and_excessive_operations_are_rejected() -> None:
    app = _application()

    with TestClient(app) as client:
        uploaded = _upload(client)
        unknown = client.post(
            "/api/v1/analytics/execute",
            json={
                "dataset_id": uploaded["dataset_id"],
                "operation": {"operation": "sum", "column": "profit"},
            },
        )
        non_numeric = client.post(
            "/api/v1/analytics/execute",
            json={
                "dataset_id": uploaded["dataset_id"],
                "operation": {"operation": "mean", "column": "region"},
            },
        )
        excessive = client.post(
            "/api/v1/analytics/execute",
            json={
                "dataset_id": uploaded["dataset_id"],
                "operation": {
                    "operation": "sort",
                    "sort_fields": [{"column": "revenue", "direction": "desc"}],
                    "limit": 21,
                },
            },
        )

    for response in (unknown, non_numeric, excessive):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_ANALYTICS_OPERATION"


def test_code_like_and_invalid_aggregation_plans_fail_schema_validation() -> None:
    app = _application()

    with TestClient(app) as client:
        uploaded = _upload(client)
        code_operation = client.post(
            "/api/v1/analytics/execute",
            json={
                "dataset_id": uploaded["dataset_id"],
                "operation": {"operation": "python", "code": "print('unsafe')"},
            },
        )
        missing_field = client.post(
            "/api/v1/analytics/execute",
            json={
                "dataset_id": uploaded["dataset_id"],
                "operation": {
                    "operation": "group_by",
                    "grouping_fields": ["region"],
                    "aggregation": "sum",
                },
            },
        )

    schema = str(AnalyticsExecuteRequest.model_json_schema()).casefold()
    assert code_operation.status_code == 422
    assert missing_field.status_code == 422
    assert "python" not in schema
    assert "code" not in schema
    assert "expression" not in schema


def test_analytics_implementation_has_no_dynamic_code_execution_calls() -> None:
    services = Path(__file__).resolve().parents[1] / "app" / "services"
    modules = [
        services / "analytics_executor.py",
        services / "analytics_planning.py",
        services / "analytics_service.py",
    ]
    banned_calls = {"compile", "eval", "exec"}

    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert called_names.isdisjoint(banned_calls)


def test_malformed_csvs_are_rejected_without_partial_dataset() -> None:
    app = _application()

    with TestClient(app) as client:
        duplicate_header = client.post(
            "/api/v1/datasets",
            files={"file": ("duplicate.csv", b"region,region\nNorth,South\n", "text/csv")},
        )
        wrong_width = client.post(
            "/api/v1/datasets",
            files={"file": ("width.csv", b"region,revenue\nNorth\n", "text/csv")},
        )
        wrong_type = client.post(
            "/api/v1/datasets",
            files={"file": ("data.txt", b"region,revenue\nNorth,1\n", "text/plain")},
        )
        listed = client.get("/api/v1/datasets")

    assert duplicate_header.status_code == 422
    assert wrong_width.status_code == 422
    assert wrong_type.status_code == 415
    assert listed.json() == {"datasets": []}


def test_graph_uses_structured_plan_and_deterministic_numeric_summary() -> None:
    provider = MockProvider()
    app = _application(provider)

    with TestClient(app) as client:
        _upload(client)
        response = client.post(
            "/api/v1/chat/invoke",
            json={
                "message": "Compare revenue across regions.",
                "thread_id": "analytics-grounding",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "data_analytics"
    assert payload["final_response"] == (
        "Computed sum grouped by region: region=North, sum_revenue=200.75; "
        "region=South, sum_revenue=245.75; region=West, sum_revenue=180.5."
    )
    assert "analytics.status=completed" in payload["trace"]
    assert "synthesizer.mode=deterministic_analytics" in payload["trace"]
    assert provider.call_history == [
        "generate_structured",
        "generate_structured",
        "generate_structured",
    ]
    assert payload["genui"][0]["type"] == "bar_chart"


def test_dataset_delete_removes_it_from_execution() -> None:
    app = _application()

    with TestClient(app) as client:
        uploaded = _upload(client)
        dataset_id = cast(str, uploaded["dataset_id"])
        deleted = client.delete(f"/api/v1/datasets/{dataset_id}")
        executed = client.post(
            "/api/v1/analytics/execute",
            json={"dataset_id": dataset_id, "operation": {"operation": "count"}},
        )

    assert deleted.status_code == 204
    assert executed.status_code == 404
    assert executed.json()["error"]["code"] == "DATASET_NOT_FOUND"
