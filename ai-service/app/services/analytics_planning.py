import json
import re

from app.schemas.analytics import AnalyticsPlan
from app.services.analytics_errors import AnalyticsOperationError


def plan_for_mock(user_prompt: str) -> AnalyticsPlan:
    """Deterministic offline stand-in for schema-constrained model planning."""

    try:
        payload = json.loads(user_prompt)
    except json.JSONDecodeError as error:
        raise AnalyticsOperationError("Analytics planning input is invalid.") from error
    query = str(payload.get("query", "")).casefold()
    max_result_rows = payload.get("max_result_rows", 100)
    if not isinstance(max_result_rows, int) or not 1 <= max_result_rows <= 1_000:
        raise AnalyticsOperationError("Analytics planning row limit is invalid.")
    raw_datasets = payload.get("datasets")
    if not isinstance(raw_datasets, list) or not raw_datasets:
        raise AnalyticsOperationError("No dataset is available for analytics planning.")

    selected = _select_dataset(query, raw_datasets)
    dataset_id = str(selected["dataset_id"])
    raw_columns = selected.get("columns")
    if not isinstance(raw_columns, list):
        raise AnalyticsOperationError("The selected dataset has no valid column schema.")
    columns = [
        str(item["name"]) for item in raw_columns if isinstance(item, dict) and "name" in item
    ]
    numeric = [
        str(item["name"])
        for item in raw_columns
        if isinstance(item, dict) and item.get("type") == "number"
    ]

    if "describe" in query or "summary" in query:
        operation: dict[str, object] = {"operation": "describe"}
    elif "top" in query:
        operation = {
            "operation": "top_n",
            "column": _mentioned_column(query, numeric),
            "n": min(_requested_top_n(query), max_result_rows),
        }
    elif "sort" in query or "order" in query:
        operation = {
            "operation": "sort",
            "sort_fields": [
                {
                    "column": _mentioned_column(query, columns),
                    "direction": "asc" if "ascending" in query else "desc",
                }
            ],
            "limit": max_result_rows,
        }
    elif "group" in query or "across" in query or " by " in f" {query} ":
        value_column = _mentioned_column(query, numeric)
        grouping_candidates = [item for item in columns if item != value_column]
        grouping = _mentioned_column(query, grouping_candidates)
        operation = {
            "operation": "group_by",
            "grouping_fields": [grouping],
            "aggregation": _aggregate_function(query, default="sum"),
            "aggregation_field": value_column,
            "limit": max_result_rows,
        }
    elif "count" in query:
        mentioned = [item for item in columns if _column_is_mentioned(query, item)]
        operation = {"operation": "count", "column": mentioned[0] if mentioned else None}
    else:
        function = _aggregate_function(query, default="sum")
        operation = {
            "operation": function,
            "column": _mentioned_column(query, numeric),
        }
    return AnalyticsPlan.model_validate({"dataset_id": dataset_id, "operation": operation})


def _select_dataset(query: str, datasets: list[object]) -> dict[str, object]:
    valid = [item for item in datasets if isinstance(item, dict)]
    for dataset in valid:
        filename = str(dataset.get("filename", ""))
        if filename and filename.casefold() in query:
            return dataset
    if not valid:
        raise AnalyticsOperationError("No valid dataset schema is available.")
    return valid[0]


def _mentioned_column(query: str, columns: list[str]) -> str:
    for column in columns:
        if _column_is_mentioned(query, column):
            return column
    if not columns:
        raise AnalyticsOperationError("No compatible dataset column is available.")
    return columns[0]


def _column_is_mentioned(query: str, column: str) -> bool:
    normalized = column.casefold().replace("_", " ")
    singular = normalized[:-1] if normalized.endswith("s") else normalized
    return normalized in query or singular in query


def _aggregate_function(query: str, *, default: str) -> str:
    if "average" in query or "mean" in query:
        return "mean"
    for function in ("min", "max", "sum"):
        if re.search(rf"\b{function}\b", query):
            return function
    return default


def _requested_top_n(query: str) -> int:
    match = re.search(r"\btop\s+(\d{1,3})\b", query)
    return min(int(match.group(1)), 100) if match else 10
