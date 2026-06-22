from app.models.domain import (
    ErrorRecord,
    GuardrailDecision,
    GuardrailResult,
    Route,
    ToolResult,
)
from app.models.state import SynapseState, SynapseStateUpdate
from app.prompts.router import ROUTER_SYSTEM_PROMPT, build_router_user_prompt
from app.prompts.synthesis import SYNTHESIS_SYSTEM_PROMPT, build_synthesis_user_prompt
from app.providers.base import LLMProvider
from app.schemas.inference import RouterClassification
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


def synthesizer(state: SynapseState, provider: LLMProvider) -> SynapseStateUpdate:
    route = state["route"]
    tool_result = _selected_tool_result(state)
    result = provider.generate(
        system_prompt=SYNTHESIS_SYSTEM_PROMPT,
        user_prompt=build_synthesis_user_prompt(
            user_query=state["user_query"],
            route=route,
            tool_result=tool_result,
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
