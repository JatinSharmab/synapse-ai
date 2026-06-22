from app.models.domain import Route, ToolResult, ToolStatus

NOT_IMPLEMENTED_SUMMARIES: dict[Route, str] = {
    Route.DOCUMENT_SEARCH: "Document retrieval is not implemented in Phase 3.",
    Route.VIDEO_SEARCH: "Video retrieval is not implemented in Phase 3.",
    Route.DATA_ANALYTICS: "Dataset execution is not implemented in Phase 3.",
}


def run_placeholder_tool(route: Route, user_query: str) -> ToolResult:
    del user_query  # The placeholder intentionally performs no query execution.

    if route == Route.DIRECT_ANSWER:
        return ToolResult(
            tool=route,
            status=ToolStatus.COMPLETED,
            summary="The direct-answer path is ready for provider-backed synthesis.",
        )

    return ToolResult(
        tool=route,
        status=ToolStatus.NOT_IMPLEMENTED,
        summary=NOT_IMPLEMENTED_SUMMARIES[route],
    )
