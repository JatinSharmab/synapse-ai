from typing import Annotated, cast

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status

from app.core.config import Settings
from app.models.documents import DocumentRecord
from app.schemas.documents import DocumentListResponse
from app.services.document_errors import DocumentTooLargeError, DocumentValidationError
from app.services.document_rag import DocumentRAGService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _service(request: Request) -> DocumentRAGService:
    return cast(DocumentRAGService, request.app.state.document_service)


@router.post("", response_model=DocumentRecord, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: Annotated[UploadFile, File(description="A bounded local-development PDF upload")],
) -> DocumentRecord:
    settings = cast(Settings, request.app.state.settings)
    if settings.app_env == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct PDF upload is disabled in production.",
        )
    filename = file.filename or ""
    try:
        data = await file.read(settings.document_max_upload_bytes + 1)
    finally:
        await file.close()
    if len(data) > settings.document_max_upload_bytes:
        raise DocumentTooLargeError("The uploaded PDF exceeds the configured size limit.")
    if not data:
        raise DocumentValidationError("The uploaded PDF is empty.")
    return _service(request).ingest_pdf(
        filename=filename,
        content_type=file.content_type,
        data=data,
    )


@router.get("", response_model=DocumentListResponse)
def list_documents(request: Request) -> DocumentListResponse:
    return DocumentListResponse(documents=_service(request).list_documents())


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, request: Request) -> Response:
    _service(request).delete_document(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
