import re

from app.models.domain import (
    ErrorRecord,
    GuardrailDecision,
    GuardrailResult,
    Intent,
    Route,
    ToolResult,
)
from app.models.state import SynapseState, SynapseStateUpdate
from app.tools.placeholders import run_placeholder_tool

ANALYTICS_TERMS = frozenset(
    {
        "aggregate",
        "average",
        "calculate",
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
VIDEO_TERMS = frozenset({"clip", "frame", "scene", "timestamp", "transcript", "video", "watch"})
DOCUMENT_TERMS = frozenset(
    {"contract", "document", "file", "page", "pdf", "policy", "report", "section"}
)
BLOCKED_INPUT_PATTERNS = (
    "<script",
    "javascript:",
    "reveal system prompt",
    "show chain of thought",
)
MINIMUM_DRAFT_LENGTH = 20


def _contains_any(query: str, terms: frozenset[str]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", query) is not None for term in terms)


def router(state: SynapseState) -> SynapseStateUpdate:
    query = state["user_query"].casefold()

    if _contains_any(query, ANALYTICS_TERMS):
        intent = Intent.ANALYTICS
        route = Route.DATA_ANALYTICS
    elif _contains_any(query, VIDEO_TERMS):
        intent = Intent.VIDEO
        route = Route.VIDEO_SEARCH
    elif _contains_any(query, DOCUMENT_TERMS):
        intent = Intent.DOCUMENT
        route = Route.DOCUMENT_SEARCH
    else:
        intent = Intent.DIRECT
        route = Route.DIRECT_ANSWER

    return {
        "intent": intent,
        "route": route,
        "trace": [f"router.selected={route.value}"],
    }


def _tool_node(state: SynapseState, expected_route: Route) -> SynapseStateUpdate:
    if state["route"] != expected_route:
        return {
            "errors": [
                ErrorRecord(
                    code="ROUTE_MISMATCH",
                    message=f"Expected {expected_route.value} route.",
                )
            ],
            "trace": [f"tool.error={expected_route.value}"],
        }

    result = run_placeholder_tool(expected_route, state["user_query"])
    return {
        "tool_results": [result],
        "trace": [f"tool={expected_route.value}"],
    }


def document_search(state: SynapseState) -> SynapseStateUpdate:
    return _tool_node(state, Route.DOCUMENT_SEARCH)


def video_search(state: SynapseState) -> SynapseStateUpdate:
    return _tool_node(state, Route.VIDEO_SEARCH)


def data_analytics(state: SynapseState) -> SynapseStateUpdate:
    return _tool_node(state, Route.DATA_ANALYTICS)


def direct_answer(state: SynapseState) -> SynapseStateUpdate:
    return _tool_node(state, Route.DIRECT_ANSWER)


def _selected_tool_result(state: SynapseState) -> ToolResult | None:
    route = state["route"]
    return next(
        (result for result in reversed(state["tool_results"]) if result.tool == route),
        None,
    )


def synthesizer(state: SynapseState) -> SynapseStateUpdate:
    route = state["route"]
    result = _selected_tool_result(state)

    if route is None or result is None:
        draft = "Synapse could not produce a response because routing did not complete safely."
    elif route == Route.DIRECT_ANSWER and state["user_query"].casefold() in {"hello", "hi", "hey"}:
        if state["rewrite_count"] == 0:
            draft = "Hello."
        else:
            draft = (
                "Hello. Synapse completed the deterministic Phase 2 orchestration path; "
                "model-backed answering is not enabled."
            )
    elif route == Route.DIRECT_ANSWER:
        draft = (
            "Synapse classified this as a direct question. Phase 2 validates orchestration only, "
            "so model-backed answering is not enabled."
        )
    else:
        draft = f"{route.value} was selected correctly. {result.summary}"

    synthesis_event = "synthesizer=rewrite" if state["rewrite_count"] > 0 else "synthesizer=draft"
    return {
        "draft_response": draft,
        "trace": [synthesis_event],
    }


def sentinel(state: SynapseState) -> SynapseStateUpdate:
    query = state["user_query"].casefold()
    draft = (state["draft_response"] or "").strip()

    if any(pattern in query for pattern in BLOCKED_INPUT_PATTERNS):
        result = GuardrailResult(
            decision=GuardrailDecision.BLOCK,
            reason_code="UNSAFE_INPUT_PATTERN",
        )
        return {
            "guardrail_result": result,
            "final_response": "The request was blocked by deterministic safety checks.",
            "trace": ["sentinel=block"],
        }

    if len(draft) < MINIMUM_DRAFT_LENGTH:
        if state["rewrite_count"] == 0:
            result = GuardrailResult(
                decision=GuardrailDecision.REWRITE,
                reason_code="RESPONSE_TOO_SHORT",
            )
            return {
                "guardrail_result": result,
                "rewrite_count": 1,
                "trace": ["sentinel=rewrite"],
            }

        result = GuardrailResult(
            decision=GuardrailDecision.BLOCK,
            reason_code="REWRITE_LIMIT_REACHED",
        )
        return {
            "guardrail_result": result,
            "final_response": "Synapse could not produce a safe response within the rewrite limit.",
            "trace": ["sentinel=block"],
        }

    result = GuardrailResult(
        decision=GuardrailDecision.APPROVE,
        reason_code="DETERMINISTIC_CHECKS_PASSED",
    )
    return {
        "guardrail_result": result,
        "final_response": draft,
        "trace": ["sentinel=approve"],
    }
