from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the HTTP application with explicit, testable runtime settings."""

    runtime = settings or get_settings()
    application = FastAPI(
        title="Synapse AI Service",
        description="Deterministic LangGraph orchestration core for Synapse.",
        version=runtime.app_version,
    )
    application.state.settings = runtime
    application.include_router(api_router)

    return application


app = create_app()
