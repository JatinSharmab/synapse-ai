from typing import Annotated, cast

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status

from app.core.config import Settings
from app.models.datasets import DatasetRecord
from app.schemas.datasets import DatasetListResponse
from app.services.analytics_errors import DatasetTooLargeError, DatasetValidationError
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


def _service(request: Request) -> AnalyticsService:
    return cast(AnalyticsService, request.app.state.analytics_service)


@router.post("", response_model=DatasetRecord, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    request: Request,
    file: Annotated[UploadFile, File(description="A bounded local-development CSV upload")],
) -> DatasetRecord:
    settings = cast(Settings, request.app.state.settings)
    if settings.app_env == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct CSV upload is disabled in production.",
        )
    try:
        data = await file.read(settings.dataset_max_upload_bytes + 1)
    finally:
        await file.close()
    if len(data) > settings.dataset_max_upload_bytes:
        raise DatasetTooLargeError("The uploaded CSV exceeds the configured size limit.")
    if not data:
        raise DatasetValidationError("The uploaded CSV is empty.")
    return _service(request).ingest_csv(
        filename=file.filename or "",
        content_type=file.content_type,
        data=data,
    )


@router.get("", response_model=DatasetListResponse)
def list_datasets(request: Request) -> DatasetListResponse:
    return DatasetListResponse(datasets=_service(request).list_datasets())


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(dataset_id: str, request: Request) -> Response:
    _service(request).delete_dataset(dataset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
