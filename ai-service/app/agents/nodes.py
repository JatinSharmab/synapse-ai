from app.models.domain import (
    Citation,
    DocumentCitation,
    DocumentRetrievedContext,
    ErrorRecord,
    GuardrailDecision,
    GuardrailResult,
    RetrievedContext,
    Route,
    ToolResult,
    ToolStatus,
    VideoCitation,
    VideoRetrievedContext,
)
from app.models.state import SynapseState, SynapseStateUpdate
from app.prompts.router import ROUTER_SYSTEM_PROMPT, build_router_user_prompt
from app.prompts.synthesis import SYNTHESIS_SYSTEM_PROMPT, build_synthesis_user_prompt
from app.providers.base import LLMProvider
from app.schemas.inference import RouterClassification
from app.services.analytics_errors import AnalyticsError
from app.services.analytics_service import AnalyticsTool
from app.services.document_rag import DocumentRetriever
from app.services.video_rag import VideoRetriever
from app.tools.placeholders import run_placeholder_tool

BLOCKED_INPUT_PATTERNS = (
    "<script",
    "javascript:",
    "reveal system prompt",
    "show chain of thought",
)
MINIMUM_DRAFT_LENGTH = 20


def router(state: SynapseState, provider: LLMProvider) -> SynapseStateUpdate:
    result = provider.generate_structured(
        system_prompt=ROUTER_SYSTEM_PROMPT,
        user_prompt=build_router_user_prompt(state["user_query"]),
        response_model=RouterClassification,
    )
    classification = result.value

    return {
        "intent": classification.intent,
        "route": classification.route,
        "inference_metadata": [result.metadata],
        "trace": [
            f"router.selected={classification.route.value}",
            f"provider.router={result.metadata.provider}",
        ],
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


def document_search(
    state: SynapseState,
    retriever: DocumentRetriever,
    top_k: int,
) -> SynapseStateUpdate:
    if state["route"] != Route.DOCUMENT_SEARCH:
        return {
            "errors": [
                ErrorRecord(
                    code="ROUTE_MISMATCH",
                    message="Expected document_search route.",
                )
            ],
            "trace": ["tool.error=document_search"],
        }

    execution = retriever.search(state["user_query"], top_k=top_k)
    contexts: list[RetrievedContext] = [
        DocumentRetrievedContext(
            context_id=result.chunk_id,
            content=result.text,
            document_id=result.document_id,
            filename=result.filename,
            page=result.page,
            chunk_id=result.chunk_id,
            similarity_score=result.similarity_score,
        )
        for result in execution.results
    ]
    citations: list[Citation] = [
        DocumentCitation(
            citation_id=f"citation_{result.chunk_id}",
            document_id=result.document_id,
            filename=result.filename,
            page=result.page,
            chunk_id=result.chunk_id,
            locator=f"{result.filename}, page {result.page}",
        )
        for result in execution.results
    ]
    result_count = len(execution.results)
    update: SynapseStateUpdate = {
        "retrieved_context": contexts,
        "citations": citations,
        "tool_results": [
            ToolResult(
                tool=Route.DOCUMENT_SEARCH,
                status=ToolStatus.COMPLETED,
                summary=(
                    f"Retrieved {result_count} provenance-validated document chunks."
                    if result_count
                    else "No indexed document evidence matched the query."
                ),
            )
        ],
        "trace": ["tool=document_search", f"retrieval.count={result_count}"],
    }
    if execution.inference_metadata is not None:
        update["inference_metadata"] = [execution.inference_metadata]
    return update


def video_search(
    state: SynapseState,
    retriever: VideoRetriever,
    top_k: int,
) -> SynapseStateUpdate:
    if state["route"] != Route.VIDEO_SEARCH:
        return {
            "errors": [
                ErrorRecord(
                    code="ROUTE_MISMATCH",
                    message="Expected video_search route.",
                )
            ],
            "trace": ["tool.error=video_search"],
        }

    execution = retriever.search(state["user_query"], top_k=top_k)
    contexts: list[RetrievedContext] = [
        VideoRetrievedContext(
            context_id=result.segment_id,
            content=result.description,
            video_id=result.video_id,
            filename=result.filename,
            segment_id=result.segment_id,
            start_seconds=result.start_seconds,
            end_seconds=result.end_seconds,
            similarity_score=result.score,
        )
        for result in execution.results
    ]
    citations: list[Citation] = [
        VideoCitation(
            citation_id=f"citation_{result.segment_id}",
            video_id=result.video_id,
            filename=result.filename,
            segment_id=result.segment_id,
            start_seconds=result.start_seconds,
            end_seconds=result.end_seconds,
            locator=(f"{result.filename}, {result.start_seconds:.3f}s–{result.end_seconds:.3f}s"),
        )
        for result in execution.results
    ]
    result_count = len(execution.results)
    update: SynapseStateUpdate = {
        "retrieved_context": contexts,
        "citations": citations,
        "tool_results": [
            ToolResult(
                tool=Route.VIDEO_SEARCH,
                status=ToolStatus.COMPLETED,
                summary=(
                    f"Retrieved {result_count} timestamped video segments."
                    if result_count
                    else "No indexed video evidence matched the query."
                ),
            )
        ],
        "trace": ["tool=video_search", f"retrieval.count={result_count}"],
    }
    if execution.inference_metadata is not None:
        update["inference_metadata"] = [execution.inference_metadata]
    return update


def data_analytics(state: SynapseState, analytics: AnalyticsTool) -> SynapseStateUpdate:
    if state["route"] != Route.DATA_ANALYTICS:
        return {
            "errors": [
                ErrorRecord(
                    code="ROUTE_MISMATCH",
                    message="Expected data_analytics route.",
                )
            ],
            "trace": ["tool.error=data_analytics"],
        }
    try:
        execution = analytics.plan_and_execute(state["user_query"])
    except AnalyticsError as error:
        return {
            "tool_results": [
                ToolResult(
                    tool=Route.DATA_ANALYTICS,
                    status=ToolStatus.FAILED,
                    summary=f"Analytics could not run: {error}",
                )
            ],
            "errors": [ErrorRecord(code=error.code, message=str(error))],
            "trace": ["tool=data_analytics", "analytics.status=failed"],
        }
    update: SynapseStateUpdate = {
        "tool_results": [
            ToolResult(
                tool=Route.DATA_ANALYTICS,
                status=ToolStatus.COMPLETED,
                summary=execution.result.summary,
            )
        ],
        "trace": ["tool=data_analytics", "analytics.status=completed"],
    }
    if execution.inference_metadata is not None:
        update["inference_metadata"] = [execution.inference_metadata]
    return update


def direct_answer(state: SynapseState) -> SynapseStateUpdate:
    return _tool_node(state, Route.DIRECT_ANSWER)


def _selected_tool_result(state: SynapseState) -> ToolResult | None:
    route = state["route"]
    return next(
        (result for result in reversed(state["tool_results"]) if result.tool == route),
        None,
    )


def synthesizer(state: SynapseState, provider: LLMProvider) -> SynapseStateUpdate:
    route = state["route"]
    tool_result = _selected_tool_result(state)
    if route == Route.DATA_ANALYTICS and tool_result is not None:
        synthesis_event = (
            "synthesizer=rewrite" if state["rewrite_count"] > 0 else "synthesizer=draft"
        )
        return {
            "draft_response": tool_result.summary,
            "trace": [synthesis_event, "synthesizer.mode=deterministic_analytics"],
        }
    result = provider.generate(
        system_prompt=SYNTHESIS_SYSTEM_PROMPT,
        user_prompt=build_synthesis_user_prompt(
            user_query=state["user_query"],
            route=route,
            tool_result=tool_result,
            retrieved_context=state["retrieved_context"],
            citations=state["citations"],
            rewrite_count=state["rewrite_count"],
        ),
    )

    synthesis_event = "synthesizer=rewrite" if state["rewrite_count"] > 0 else "synthesizer=draft"
    return {
        "draft_response": result.text,
        "inference_metadata": [result.metadata],
        "trace": [synthesis_event, f"provider.synthesizer={result.metadata.provider}"],
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
