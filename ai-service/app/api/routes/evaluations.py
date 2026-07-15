from typing import cast

from fastapi import APIRouter, Query, Request

from app.evaluation.models import RecentEvaluationSummaries
from app.evaluation.repository import EvaluationSummaryRepository

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.get("/summaries", response_model=RecentEvaluationSummaries)
def get_recent_evaluation_summaries(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100),
) -> RecentEvaluationSummaries:
    repository = cast(
        EvaluationSummaryRepository, request.app.state.evaluation_repository
    )
    configured_limit = request.app.state.settings.evaluation_recent_limit
    summaries = repository.recent(min(limit, configured_limit))
    return RecentEvaluationSummaries(summaries=tuple(summaries))
