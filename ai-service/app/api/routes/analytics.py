from typing import cast

from fastapi import APIRouter, Request

from app.schemas.analytics import AnalyticsExecuteRequest, AnalyticsResult
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.post("/execute", response_model=AnalyticsResult)
def execute_analytics(payload: AnalyticsExecuteRequest, request: Request) -> AnalyticsResult:
    service = cast(AnalyticsService, request.app.state.analytics_service)
    return service.execute(payload.dataset_id, payload.operation)
