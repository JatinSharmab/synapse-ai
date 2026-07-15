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
from app.prompts.genui import GENUI_SYSTEM_PROMPT, build_genui_user_prompt
from app.prompts.router import ROUTER_SYSTEM_PROMPT, build_router_user_prompt
from app.prompts.synthesis import SYNTHESIS_SYSTEM_PROMPT, build_synthesis_user_prompt
from app.providers.base import LLMProvider
from app.providers.errors import ProviderError
from app.schemas.genui import GenUIResponse
from app.schemas.inference import RouterClassification
from app.services.analytics_errors import AnalyticsError
from app.services.analytics_service import AnalyticsTool
from app.services.document_rag import DocumentRetriever
from app.services.genui import ground_analytics_genui
from app.services.guardrails import GroundingGuard, InputGuard, OutputGuard
from app.services.video_rag import VideoRetriever
from app.tools.placeholders import run_placeholder_tool

INPUT_GUARD = InputGuard()
GROUNDING_GUARD = GroundingGuard()
OUTPUT_GUARD = OutputGuard()


def input_guard(state: SynapseState) -> SynapseStateUpdate:
    outcome = INPUT_GUARD.evaluate(state["user_query"])
    if outcome.passed:
        return {
            "input_guard_passed": True,
            "trace": ["guardrail.input=pass"],
        }

    result = GuardrailResult(
        decision=GuardrailDecision.BLOCK,
        groundedness_score=0,
        citation_coverage=0,
        prompt_injection_detected=outcome.prompt_injection_detected,
        schema_valid=True,
        reasons=outcome.reasons,
        rewrite_required=False,
    )
    return {
        "input_guard_passed": False,
        "guardrail_result": result,
        "final_response": "The request was blocked by deterministic input safety checks.",
        "citations": [],
        "genui": [],
        "trace": ["guardrail.input=block", "sentinel=block"],
    }


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
        "analytics_result": execution.result,
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
        update: SynapseStateUpdate = {
            "draft_response": tool_result.summary,
            "trace": [synthesis_event, "synthesizer.mode=deterministic_analytics"],
        }
        analytics_result = state["analytics_result"]
        if analytics_result is None or tool_result.status != ToolStatus.COMPLETED:
            return update
        try:
            proposal = provider.generate_structured(
                system_prompt=GENUI_SYSTEM_PROMPT,
                user_prompt=build_genui_user_prompt(analytics_result),
                response_model=GenUIResponse,
            )
            components = ground_analytics_genui(proposal.value, analytics_result)
        except (AnalyticsError, ProviderError, ValueError):
            update["genui"] = []
            update["trace"] = [*update["trace"], "genui=fallback_safe_text"]
            return update
        update["genui"] = components
        update["inference_metadata"] = [proposal.metadata]
        update["trace"] = [*update["trace"], "genui=validated"]
        return update
    result = provider.generate(
        system_prompt=SYNTHESIS_SYSTEM_PROMPT,
        user_prompt=build_synthesis_user_prompt(
            user_query=state["user_query"],
            route=route,
            tool_result=tool_result,
            retrieved_context=state["retrieved_context"],
            citations=state["citations"],
            rewrite_count=state["rewrite_count"],
            guardrail_reasons=(
                state["guardrail_result"].reasons if state["guardrail_result"] is not None else ()
            ),
        ),
    )

    synthesis_event = "synthesizer=rewrite" if state["rewrite_count"] > 0 else "synthesizer=draft"
    return {
        "draft_response": result.text,
        "inference_metadata": [result.metadata],
        "trace": [synthesis_event, f"provider.synthesizer={result.metadata.provider}"],
    }


def sentinel(state: SynapseState, provider: LLMProvider | None = None) -> SynapseStateUpdate:
    draft = (state["draft_response"] or "").strip()
    input_outcome = INPUT_GUARD.evaluate(state["user_query"])
    grounding_outcome = GROUNDING_GUARD.evaluate(state, provider)
    output_outcome = OUTPUT_GUARD.evaluate(state)
    reasons = tuple(
        dict.fromkeys(
            [
                *input_outcome.reasons,
                *grounding_outcome.reasons,
                *output_outcome.reasons,
            ]
        )
    )
    block_required = (
        not input_outcome.passed
        or grounding_outcome.block_required
        or output_outcome.block_required
    )
    rewrite_required = grounding_outcome.rewrite_required or output_outcome.rewrite_required
    grounding_status = (
        "block"
        if grounding_outcome.block_required
        else "rewrite"
        if grounding_outcome.rewrite_required
        else "pass"
    )
    output_status = (
        "block"
        if output_outcome.block_required
        else "rewrite"
        if output_outcome.rewrite_required
        else "fallback"
        if not output_outcome.schema_valid
        else "pass"
    )
    stage_trace = [
        f"guardrail.grounding={grounding_status}",
        f"guardrail.output={output_status}",
    ]
    if grounding_outcome.semantic_judgement_used:
        stage_trace.insert(1, "guardrail.grounding.semantic=used")

    if block_required:
        result = GuardrailResult(
            decision=GuardrailDecision.BLOCK,
            groundedness_score=grounding_outcome.groundedness_score,
            citation_coverage=grounding_outcome.citation_coverage,
            prompt_injection_detected=input_outcome.prompt_injection_detected,
            schema_valid=output_outcome.schema_valid,
            reasons=reasons or ("GUARDRAIL_BLOCKED",),
            rewrite_required=False,
        )
        update: SynapseStateUpdate = {
            "guardrail_result": result,
            "final_response": "The response was blocked by deterministic safety checks.",
            "citations": [],
            "genui": [],
            "trace": [*stage_trace, "sentinel=block"],
        }
        if grounding_outcome.inference_metadata:
            update["inference_metadata"] = list(grounding_outcome.inference_metadata)
        return update

    if rewrite_required:
        if state["rewrite_count"] == 0:
            result = GuardrailResult(
                decision=GuardrailDecision.REWRITE,
                groundedness_score=grounding_outcome.groundedness_score,
                citation_coverage=grounding_outcome.citation_coverage,
                prompt_injection_detected=False,
                schema_valid=output_outcome.schema_valid,
                reasons=reasons or ("GUARDRAIL_REWRITE_REQUIRED",),
                rewrite_required=True,
            )
            update = {
                "genui": list(output_outcome.genui),
                "guardrail_result": result,
                "rewrite_count": 1,
                "trace": [*stage_trace, "sentinel=rewrite"],
            }
            if grounding_outcome.inference_metadata:
                update["inference_metadata"] = list(grounding_outcome.inference_metadata)
            return update

        bounded_reasons = tuple(dict.fromkeys([*reasons, "REWRITE_LIMIT_REACHED"]))
        result = GuardrailResult(
            decision=GuardrailDecision.BLOCK,
            groundedness_score=grounding_outcome.groundedness_score,
            citation_coverage=grounding_outcome.citation_coverage,
            prompt_injection_detected=False,
            schema_valid=output_outcome.schema_valid,
            reasons=bounded_reasons,
            rewrite_required=True,
        )
        update = {
            "guardrail_result": result,
            "final_response": "Synapse could not produce a safe response within the rewrite limit.",
            "citations": [],
            "genui": [],
            "trace": [*stage_trace, "sentinel=block"],
        }
        if grounding_outcome.inference_metadata:
            update["inference_metadata"] = list(grounding_outcome.inference_metadata)
        return update

    result = GuardrailResult(
        decision=GuardrailDecision.APPROVE,
        groundedness_score=grounding_outcome.groundedness_score,
        citation_coverage=grounding_outcome.citation_coverage,
        prompt_injection_detected=False,
        schema_valid=output_outcome.schema_valid,
        reasons=reasons or ("GUARDRAILS_PASSED",),
        rewrite_required=False,
    )
    trace = stage_trace
    if not output_outcome.schema_valid:
        trace = [*trace, "sentinel.genui=fallback_safe_text"]
    update = {
        "genui": list(output_outcome.genui),
        "guardrail_result": result,
        "final_response": draft,
        "trace": [*trace, "sentinel=approve"],
    }
    if grounding_outcome.inference_metadata:
        update["inference_metadata"] = list(grounding_outcome.inference_metadata)
    return update
