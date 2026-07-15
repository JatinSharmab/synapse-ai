import operator
from typing import Annotated

from typing_extensions import TypedDict

from app.models.domain import (
    Citation,
    ErrorRecord,
    GuardrailResult,
    Intent,
    RetrievedContext,
    Route,
    ToolResult,
)
from app.schemas.analytics import AnalyticsResult
from app.schemas.genui import GenUIComponent
from app.schemas.inference import InferenceMetadata


class SynapseState(TypedDict):
    request_id: str
    thread_id: str
    user_query: str
    input_guard_passed: bool
    intent: Intent | None
    route: Route | None
    retrieved_context: list[RetrievedContext]
    tool_results: Annotated[list[ToolResult], operator.add]
    draft_response: str | None
    final_response: str | None
    citations: list[Citation]
    genui: list[GenUIComponent]
    analytics_result: AnalyticsResult | None
    guardrail_result: GuardrailResult | None
    errors: Annotated[list[ErrorRecord], operator.add]
    inference_metadata: Annotated[list[InferenceMetadata], operator.add]
    trace: Annotated[list[str], operator.add]
    rewrite_count: int


class SynapseStateUpdate(TypedDict, total=False):
    input_guard_passed: bool
    intent: Intent | None
    route: Route | None
    retrieved_context: list[RetrievedContext]
    tool_results: list[ToolResult]
    draft_response: str | None
    final_response: str | None
    citations: list[Citation]
    genui: list[GenUIComponent]
    analytics_result: AnalyticsResult | None
    guardrail_result: GuardrailResult | None
    errors: list[ErrorRecord]
    inference_metadata: list[InferenceMetadata]
    trace: list[str]
    rewrite_count: int


def create_initial_state(*, request_id: str, thread_id: str, user_query: str) -> SynapseState:
    return {
        "request_id": request_id,
        "thread_id": thread_id,
        "user_query": user_query,
        "input_guard_passed": False,
        "intent": None,
        "route": None,
        "retrieved_context": [],
        "tool_results": [],
        "draft_response": None,
        "final_response": None,
        "citations": [],
        "genui": [],
        "analytics_result": None,
        "guardrail_result": None,
        "errors": [],
        "inference_metadata": [],
        "trace": [],
        "rewrite_count": 0,
    }
