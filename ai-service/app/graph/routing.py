from typing import Literal

from app.models.domain import GuardrailDecision, Route
from app.models.state import SynapseState

SentinelRoute = Literal["rewrite", "end"]


def route_after_router(state: SynapseState) -> Route:
    route = state["route"]
    if route is None:
        raise ValueError("Router completed without selecting a route.")
    return route


def route_after_sentinel(state: SynapseState) -> SentinelRoute:
    result = state["guardrail_result"]
    if result is None:
        raise ValueError("Sentinel completed without a guardrail result.")

    if result.decision == GuardrailDecision.REWRITE and state["rewrite_count"] <= 1:
        return "rewrite"
    return "end"
