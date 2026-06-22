import re

from app.models.domain import Intent, Route
from app.schemas.inference import RouterClassification

ANALYTICS_TERMS = frozenset(
    {
        "aggregate",
        "average",
        "calculate",
        "compare",
        "count",
        "csv",
        "data",
        "dataset",
        "group by",
        "mean",
        "revenue",
        "sales",
        "sum",
        "table",
        "top",
    }
)
VIDEO_TERMS = frozenset(
    {"clip", "frame", "minute", "scene", "timestamp", "transcript", "video", "watch"}
)
DOCUMENT_TERMS = frozenset(
    {"contract", "document", "file", "page", "pdf", "policy", "report", "section"}
)


def _contains_any(query: str, terms: frozenset[str]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", query) is not None for term in terms)


def classify_for_mock(user_query: str) -> RouterClassification:
    """Provide deterministic, offline structured output for MockProvider."""

    query = user_query.casefold()
    if _contains_any(query, ANALYTICS_TERMS):
        return RouterClassification(
            intent=Intent.ANALYTICS,
            route=Route.DATA_ANALYTICS,
            confidence=1,
            rationale_code="analytics_signal",
        )
    if _contains_any(query, VIDEO_TERMS):
        return RouterClassification(
            intent=Intent.VIDEO,
            route=Route.VIDEO_SEARCH,
            confidence=1,
            rationale_code="video_signal",
        )
    if _contains_any(query, DOCUMENT_TERMS):
        return RouterClassification(
            intent=Intent.DOCUMENT,
            route=Route.DOCUMENT_SEARCH,
            confidence=1,
            rationale_code="document_signal",
        )
    return RouterClassification(
        intent=Intent.DIRECT,
        route=Route.DIRECT_ANSWER,
        confidence=1,
        rationale_code="direct_fallback",
    )
