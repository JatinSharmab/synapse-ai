from typing import Annotated, cast

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from app.core.config import Settings
from app.models.videos import VideoRecord
from app.schemas.uploads import StoredObjectRequest
from app.schemas.videos import VideoListResponse
from app.services.uploads import UploadCoordinator, UploadIntentError
from app.services.video_errors import VideoTooLargeError, VideoValidationError
from app.services.video_rag import VideoRAGService
from app.storage.base import ObjectStorageError

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


def _service(request: Request) -> VideoRAGService:
    return cast(VideoRAGService, request.app.state.video_service)


@router.post("", response_model=VideoRecord, status_code=status.HTTP_201_CREATED)
async def upload_video(
    request: Request,
    file: Annotated[UploadFile, File(description="A bounded local-development MP4 upload")],
) -> VideoRecord:
    settings = cast(Settings, request.app.state.settings)
    if settings.app_env == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct MP4 upload is disabled in production.",
        )
    max_bytes = settings.max_video_size_mb * 1024 * 1024
    try:
        data = await file.read(max_bytes + 1)
    finally:
        await file.close()
    if len(data) > max_bytes:
        raise VideoTooLargeError("The uploaded MP4 exceeds the configured size limit.")
    if not data:
        raise VideoValidationError("The uploaded MP4 is empty.")
    return _service(request).ingest_mp4(
        filename=file.filename or "",
        content_type=file.content_type,
        data=data,
    )


@router.post("/from-storage", response_model=VideoRecord, status_code=status.HTTP_201_CREATED)
def ingest_video_from_storage(payload: StoredObjectRequest, request: Request) -> VideoRecord:
    coordinator = cast(UploadCoordinator, request.app.state.upload_coordinator)
    try:
        return coordinator.ingest_video(payload.object_path)
    except UploadIntentError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except ObjectStorageError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error


@router.get("", response_model=VideoListResponse)
def list_videos(request: Request) -> VideoListResponse:
    return VideoListResponse(videos=_service(request).list_videos())
