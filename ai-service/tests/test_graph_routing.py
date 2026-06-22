import pytest

from app.agents.nodes import sentinel
from app.graph.routing import route_after_sentinel
from app.models.domain import GuardrailDecision, Route
from app.models.state import create_initial_state
from app.providers.mock import MockProvider
from app.services.orchestrator import SynapseOrchestrator


@pytest.mark.parametrize(
    ("query", "expected_route", "expected_tool_trace"),
    [
        (
            "Find the refund policy in my documents.",
            Route.DOCUMENT_SEARCH,
            "tool=document_search",
        ),
        (
            "What happened at 2 minutes in the uploaded video?",
            Route.VIDEO_SEARCH,
            "tool=video_search",
        ),
        (
            "Compare revenue across regions.",
            Route.DATA_ANALYTICS,
            "tool=data_analytics",
        ),
        (
            "Explain what RAG means.",
            Route.DIRECT_ANSWER,
            "tool=direct_answer",
        ),
    ],
)
def test_queries_route_to_expected_deterministic_node(
    query: str,
    expected_route: Route,
    expected_tool_trace: str,
) -> None:
    provider = MockProvider()
    summary = SynapseOrchestrator(provider=provider).invoke(
        message=query,
        thread_id="thread-routing",
    )

    assert summary.route == expected_route
    assert summary.trace[0] == f"router.selected={expected_route.value}"
    assert expected_tool_trace in summary.trace
    assert summary.trace[-1] == "sentinel=approve"
    assert provider.call_history == ["generate_structured", "generate"]
    assert [event.operation for event in summary.inference_metadata] == [
        "generate_structured",
        "generate",
    ]


def test_graph_terminates_with_a_complete_safe_summary() -> None:
    summary = SynapseOrchestrator(provider=MockProvider()).invoke(
        message="Summarize this policy document",
        thread_id="thread-termination",
    )

    assert summary.final_response
    assert summary.guardrail_result.decision == GuardrailDecision.APPROVE
    assert summary.rewrite_count == 0
    assert summary.errors == []


def test_sentinel_rewrite_is_bounded_to_one_graph_cycle() -> None:
    provider = MockProvider(
        generated_responses=[
            "Hello.",
            "Hello. The response was expanded once and now passes deterministic checks.",
        ]
    )
    summary = SynapseOrchestrator(provider=provider).invoke(
        message="hello",
        thread_id="thread-rewrite",
    )

    sentinel_events = [event for event in summary.trace if event.startswith("sentinel=")]
    assert sentinel_events == ["sentinel=rewrite", "sentinel=approve"]
    assert summary.rewrite_count == 1
    assert summary.guardrail_result.decision == GuardrailDecision.APPROVE
    assert summary.trace.count("synthesizer=rewrite") == 1
    assert provider.call_history == ["generate_structured", "generate", "generate"]


def test_second_invalid_draft_blocks_instead_of_rewriting_again() -> None:
    state = create_initial_state(
        request_id="request-bound",
        thread_id="thread-bound",
        user_query="hello",
    )
    state["draft_response"] = "short"
    state["rewrite_count"] = 1

    update = sentinel(state)
    guardrail_result = update["guardrail_result"]
    assert guardrail_result is not None
    state["guardrail_result"] = guardrail_result

    assert guardrail_result.decision == GuardrailDecision.BLOCK
    assert state["rewrite_count"] == 1
    assert route_after_sentinel(state) == "end"
