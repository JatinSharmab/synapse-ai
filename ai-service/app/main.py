from fastapi import FastAPI

from app.api.errors import register_provider_error_handlers
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.providers.base import LLMProvider
from app.providers.factory import create_llm_provider
from app.services.orchestrator import SynapseOrchestrator


def create_app(
    settings: Settings | None = None,
    provider: LLMProvider | None = None,
) -> FastAPI:
    """Build the HTTP application with explicit, testable runtime settings."""

    runtime = settings or get_settings()
    active_provider = provider or create_llm_provider(runtime)
    application = FastAPI(
        title="Synapse AI Service",
        description="Provider-backed LangGraph orchestration core for Synapse.",
        version=runtime.app_version,
    )
    application.state.settings = runtime
    application.state.llm_provider = active_provider
    application.state.orchestrator = SynapseOrchestrator(provider=active_provider)
    register_provider_error_handlers(application)
    application.include_router(api_router)

    return application


app = create_app()
