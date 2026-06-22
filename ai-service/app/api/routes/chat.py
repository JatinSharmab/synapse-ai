from typing import cast

from fastapi import APIRouter, Request

from app.schemas.chat import ChatInvokeRequest, ChatStateSummary
from app.services.orchestrator import SynapseOrchestrator

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/invoke", response_model=ChatStateSummary)
def invoke_chat(payload: ChatInvokeRequest, request: Request) -> ChatStateSummary:
    orchestrator = cast(SynapseOrchestrator, request.app.state.orchestrator)
    return orchestrator.invoke(message=payload.message, thread_id=payload.thread_id)
