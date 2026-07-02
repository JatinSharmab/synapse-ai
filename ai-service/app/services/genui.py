import json

from app.schemas.analytics import AnalyticsResult
from app.schemas.genui import (
    BarChartComponent,
    GenUIComponent,
    GenUIResponse,
    MetricComponent,
    TableComponent,
)
from app.services.analytics_errors import AnalyticsOperationError


def ground_analytics_genui(
    response: GenUIResponse,
    result: AnalyticsResult,
) -> list[GenUIComponent]:
    """Fail closed unless the proposal exactly preserves deterministic result data."""

    if len(response.components) != 1:
        raise ValueError("Analytics Gen-UI must contain exactly one component")
    component = response.components[0]
    expected_rows = result.model_dump(mode="json")["result_rows"]

    if result.recommended_visualization == "bar_chart":
        if not isinstance(component, BarChartComponent):
            raise ValueError("Analytics Gen-UI component type did not match the recommendation")
        if component.data != expected_rows:
            raise ValueError("Analytics chart data did not match deterministic result rows")
        if (
            component.config.xKey not in result.columns
            or component.config.yKey not in result.columns
        ):
            raise ValueError("Analytics chart keys did not match deterministic result columns")
    elif result.recommended_visualization == "table":
        if not isinstance(component, TableComponent):
            raise ValueError("Analytics Gen-UI component type did not match the recommendation")
        if component.data != expected_rows:
            raise ValueError("Analytics table data did not match deterministic result rows")
        if [column.key for column in component.columns] != result.columns:
            raise ValueError("Analytics table columns did not match deterministic result columns")
    elif result.recommended_visualization == "metric":
        if not isinstance(component, MetricComponent):
            raise ValueError("Analytics Gen-UI component type did not match the recommendation")
        if len(result.columns) != 1 or len(expected_rows) != 1:
            raise ValueError("Metric visualization requires one deterministic value")
        column = result.columns[0]
        if component.label != column or component.value != expected_rows[0][column]:
            raise ValueError("Analytics metric did not match the deterministic result")
    else:
        raise ValueError("The analytics visualization recommendation is unsupported")
    return [component]


def genui_for_mock(user_prompt: str) -> GenUIResponse:
    """Create a deterministic offline proposal through the same strict response schema."""

    try:
        payload = json.loads(user_prompt)
        result = AnalyticsResult.model_validate(payload["analytics_result"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise AnalyticsOperationError("Mock Gen-UI planning input is invalid.") from error

    common = {"version": "1.0", "title": "Analytics result"}
    if result.recommended_visualization == "bar_chart":
        if len(result.columns) < 2:
            raise AnalyticsOperationError("A bar chart requires at least two result columns.")
        component: dict[str, object] = {
            **common,
            "type": "bar_chart",
            "data": result.result_rows,
            "config": {"xKey": result.columns[0], "yKey": result.columns[1]},
        }
    elif result.recommended_visualization == "table":
        component = {
            **common,
            "type": "table",
            "columns": [
                {"key": column, "label": column.replace("_", " ").title()}
                for column in result.columns
            ],
            "data": result.result_rows,
        }
    else:
        if len(result.columns) != 1 or len(result.result_rows) != 1:
            raise AnalyticsOperationError("A metric requires one deterministic result value.")
        column = result.columns[0]
        component = {
            **common,
            "type": "metric",
            "label": column,
            "value": result.result_rows[0][column],
        }
    return GenUIResponse.model_validate({"components": [component]})
