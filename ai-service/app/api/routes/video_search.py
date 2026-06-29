from typing import cast

from fastapi import APIRouter, Request

from app.core.config import Settings
from app.schemas.videos import VideoSearchRequest, VideoSearchResponse
from app.services.video_rag import VideoRAGService

router = APIRouter(prefix="/api/v1/search/videos", tags=["search"])


@router.post("", response_model=VideoSearchResponse)
def search_videos(payload: VideoSearchRequest, request: Request) -> VideoSearchResponse:
    settings = cast(Settings, request.app.state.settings)
    service = cast(VideoRAGService, request.app.state.video_service)
    execution = service.search(payload.query, top_k=payload.top_k or settings.video_search_top_k)
    return VideoSearchResponse(
        results=execution.results,
        inference_metadata=execution.inference_metadata,
    )
