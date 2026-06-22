from typing import cast
from uuid import uuid4

from langgraph.graph.state import CompiledStateGraph

from app.graph.workflow import build_synapse_graph
from app.models.state import SynapseState, create_initial_state
from app.providers.base import LLMProvider
from app.schemas.chat import ChatStateSummary

GRAPH_RECURSION_LIMIT = 12


class SynapseOrchestrator:
    def __init__(
        self,
        provider: LLMProvider,
        graph: CompiledStateGraph[SynapseState, None, SynapseState, SynapseState] | None = None,
    ) -> None:
        self._graph = graph or build_synapse_graph(provider)

    def invoke(self, *, message: str, thread_id: str) -> ChatStateSummary:
        initial_state = create_initial_state(
            request_id=str(uuid4()),
            thread_id=thread_id,
            user_query=message,
        )
        result = cast(
            SynapseState,
            self._graph.invoke(initial_state, {"recursion_limit": GRAPH_RECURSION_LIMIT}),
        )

        intent = result["intent"]
        route = result["route"]
        final_response = result["final_response"]
        guardrail_result = result["guardrail_result"]
        if intent is None or route is None or final_response is None or guardrail_result is None:
            raise RuntimeError("Graph terminated without a complete safe state summary.")

        return ChatStateSummary(
            request_id=result["request_id"],
            thread_id=result["thread_id"],
            intent=intent,
            route=route,
            final_response=final_response,
            citations=result["citations"],
            genui=result["genui"],
            guardrail_result=guardrail_result,
            errors=result["errors"],
            inference_metadata=result["inference_metadata"],
            trace=result["trace"],
            rewrite_count=result["rewrite_count"],
        )
