from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.nodes import (
    data_analytics,
    direct_answer,
    document_search,
    router,
    sentinel,
    synthesizer,
    video_search,
)
from app.graph.routing import route_after_router, route_after_sentinel
from app.models.domain import Route
from app.models.state import SynapseState
from app.providers.base import LLMProvider
from app.services.document_rag import DocumentRetriever
from app.services.video_rag import VideoRetriever


def build_synapse_graph(
    provider: LLMProvider,
    document_retriever: DocumentRetriever,
    document_context_top_k: int,
    video_retriever: VideoRetriever,
    video_context_top_k: int,
) -> CompiledStateGraph[SynapseState, None, SynapseState, SynapseState]:
    builder = StateGraph(SynapseState)

    builder.add_node("router", lambda state: router(state, provider))
    builder.add_node(
        Route.DOCUMENT_SEARCH.value,
        lambda state: document_search(
            state,
            document_retriever,
            document_context_top_k,
        ),
    )
    builder.add_node(
        Route.VIDEO_SEARCH.value,
        lambda state: video_search(state, video_retriever, video_context_top_k),
    )
    builder.add_node(Route.DATA_ANALYTICS.value, data_analytics)
    builder.add_node(Route.DIRECT_ANSWER.value, direct_answer)
    builder.add_node("synthesizer", lambda state: synthesizer(state, provider))
    builder.add_node("sentinel", sentinel)

    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        route_after_router,
        {
            Route.DOCUMENT_SEARCH: Route.DOCUMENT_SEARCH.value,
            Route.VIDEO_SEARCH: Route.VIDEO_SEARCH.value,
            Route.DATA_ANALYTICS: Route.DATA_ANALYTICS.value,
            Route.DIRECT_ANSWER: Route.DIRECT_ANSWER.value,
        },
    )

    for route in Route:
        builder.add_edge(route.value, "synthesizer")

    builder.add_edge("synthesizer", "sentinel")
    builder.add_conditional_edges(
        "sentinel",
        route_after_sentinel,
        {
            "rewrite": "synthesizer",
            "end": END,
        },
    )

    return builder.compile()
