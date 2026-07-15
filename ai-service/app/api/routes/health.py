from typing import cast

from fastapi import APIRouter, Request, Response, status

from app.core.config import Settings
from app.schemas.health import HealthResponse
from app.services.readiness import ReadinessSnapshot, RetrievalReadiness

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    return HealthResponse(
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("/ready", response_model=ReadinessSnapshot)
def ready(request: Request, response: Response) -> ReadinessSnapshot:
    readiness = cast(RetrievalReadiness, request.app.state.readiness)
    snapshot = readiness.snapshot()
    if snapshot.status != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return snapshot
