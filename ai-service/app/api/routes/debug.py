from typing import cast

from fastapi import APIRouter, Request

from app.core.config import Settings
from app.schemas.documents import RetrievalDebugRequest, RetrievalDebugResponse
from app.services.document_rag import DocumentRAGService

router = APIRouter(prefix="/api/v1/debug", tags=["debug"])


@router.post("/retrieval/documents", response_model=RetrievalDebugResponse)
def debug_document_retrieval(
    payload: RetrievalDebugRequest,
    request: Request,
) -> RetrievalDebugResponse:
    settings = cast(Settings, request.app.state.settings)
    service = cast(DocumentRAGService, request.app.state.document_service)
    execution = service.search(
        payload.query,
        top_k=payload.top_k or settings.final_context_k,
        document_ids=payload.document_ids,
        mode=payload.mode,
        include_debug=True,
    )
    if execution.debug is None:
        raise RuntimeError("Retrieval debug state was not generated.")
    return RetrievalDebugResponse(
        **execution.debug.model_dump(),
        inference_metadata=execution.inference_metadata,
    )
