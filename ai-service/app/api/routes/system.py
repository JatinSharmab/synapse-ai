from typing import cast

from fastapi import APIRouter, Request

from app.providers.base import LLMProvider
from app.schemas.inference import ProviderInfo

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/ai-provider", response_model=ProviderInfo)
def get_ai_provider(request: Request) -> ProviderInfo:
    provider = cast(LLMProvider, request.app.state.llm_provider)
    return provider.info()
