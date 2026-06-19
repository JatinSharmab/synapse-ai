from fastapi import APIRouter

from app.schemas.chat import ChatInvokeRequest, ChatStateSummary
from app.services.orchestrator import SynapseOrchestrator

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])
orchestrator = SynapseOrchestrator()


@router.post("/invoke", response_model=ChatStateSummary)
def invoke_chat(request: ChatInvokeRequest) -> ChatStateSummary:
    return orchestrator.invoke(message=request.message, thread_id=request.thread_id)
