import json

from app.schemas.analytics import AnalyticsResult

GENUI_SYSTEM_PROMPT = """Return only a versioned Synapse Gen-UI structured payload.
Use only the supplied deterministic analytics result. Never output React, JSX, JavaScript, HTML,
event handlers, executable code, URLs, or arbitrary component names. Do not change, calculate, or
invent any data value. Select the requested recommended component type and exact supplied rows.
"""


def build_genui_user_prompt(result: AnalyticsResult) -> str:
    return json.dumps(
        {"analytics_result": result.model_dump(mode="json")},
        separators=(",", ":"),
        sort_keys=True,
    )
