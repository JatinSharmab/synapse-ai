import re
from typing import cast
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.config import Settings
from app.schemas.chat import ChatInvokeRequest, ChatStateSummary
from app.services.orchestrator import SynapseOrchestrator
from app.services.streaming import SSEStreamService

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


@router.post("/invoke", response_model=ChatStateSummary)
def invoke_chat(payload: ChatInvokeRequest, request: Request) -> ChatStateSummary:
    orchestrator = cast(SynapseOrchestrator, request.app.state.orchestrator)
    return orchestrator.invoke(message=payload.message, thread_id=payload.thread_id)


@router.post("/stream")
async def stream_chat(payload: ChatInvokeRequest, request: Request) -> StreamingResponse:
    orchestrator = cast(SynapseOrchestrator, request.app.state.orchestrator)
    settings = cast(Settings, request.app.state.settings)
    request_id = _safe_request_id(request.headers.get("x-request-id"))
    correlation_id = _safe_request_id(request.headers.get("x-correlation-id"))
    stream_service = SSEStreamService(
        orchestrator,
        timeout_seconds=settings.sse_stream_timeout_seconds,
        heartbeat_seconds=settings.sse_heartbeat_seconds,
    )
    body = stream_service.stream(
        message=payload.message,
        thread_id=payload.thread_id,
        request_id=request_id,
        correlation_id=correlation_id,
        is_disconnected=request.is_disconnected,
    )
    return StreamingResponse(
        body,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Correlation-ID": correlation_id,
            "X-Request-ID": request_id,
        },
    )


def _safe_request_id(value: str | None) -> str:
    if value is not None and SAFE_ID_PATTERN.fullmatch(value):
        return value
    return str(uuid4())
