import json

from app.models.datasets import DatasetRecord

ANALYTICS_SYSTEM_PROMPT = """Map the request to exactly one allowed analytics operation schema.
Select only supplied dataset and column identifiers. Never produce Python, SQL, expressions,
formulas, shell commands, or calculations. The application will validate and execute the plan.
Use aggregation for multiple metrics, group_by for one grouped metric, and top_n only for a numeric
ranking. Return only the requested structured plan without private reasoning.
"""


def build_analytics_user_prompt(
    query: str,
    datasets: list[DatasetRecord],
    max_result_rows: int,
) -> str:
    payload = {
        "query": query,
        "max_result_rows": max_result_rows,
        "datasets": [
            {
                "dataset_id": dataset.dataset_id,
                "filename": dataset.filename,
                "columns": [
                    {"name": column.name, "type": column.data_type.value}
                    for column in dataset.columns
                ],
            }
            for dataset in datasets
        ],
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
