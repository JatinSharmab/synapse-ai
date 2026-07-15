from typing import cast

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.uploads import PresignUploadRequest, PresignUploadResponse
from app.services.uploads import UploadCoordinator, UploadIntentError
from app.storage.base import ObjectStorageError

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


@router.post("/presign", response_model=PresignUploadResponse)
def presign_upload(payload: PresignUploadRequest, request: Request) -> PresignUploadResponse:
    coordinator = cast(UploadCoordinator, request.app.state.upload_coordinator)
    try:
        return coordinator.presign(payload)
    except UploadIntentError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    except ObjectStorageError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
