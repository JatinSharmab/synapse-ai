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


def build_synapse_graph() -> CompiledStateGraph[SynapseState, None, SynapseState, SynapseState]:
    builder = StateGraph(SynapseState)

    builder.add_node("router", router)
    builder.add_node(Route.DOCUMENT_SEARCH.value, document_search)
    builder.add_node(Route.VIDEO_SEARCH.value, video_search)
    builder.add_node(Route.DATA_ANALYTICS.value, data_analytics)
    builder.add_node(Route.DIRECT_ANSWER.value, direct_answer)
    builder.add_node("synthesizer", synthesizer)
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
