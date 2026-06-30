from typing import cast

from fastapi import APIRouter, Request

from app.core.config import Settings
from app.schemas.documents import DocumentSearchRequest, DocumentSearchResponse
from app.services.document_rag import DocumentRAGService

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.post("/documents", response_model=DocumentSearchResponse)
def search_documents(payload: DocumentSearchRequest, request: Request) -> DocumentSearchResponse:
    settings = cast(Settings, request.app.state.settings)
    service = cast(DocumentRAGService, request.app.state.document_service)
    execution = service.search(
        payload.query,
        top_k=payload.top_k or settings.final_context_k,
        document_ids=payload.document_ids,
    )
    return DocumentSearchResponse(
        results=execution.results,
        inference_metadata=execution.inference_metadata,
    )
