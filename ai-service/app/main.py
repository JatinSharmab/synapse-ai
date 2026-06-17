from fastapi import FastAPI

from app.config import Settings, get_settings
from app.models import HealthResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the HTTP application with explicit, testable runtime settings."""

    runtime = settings or get_settings()
    application = FastAPI(
        title="Synapse AI Service",
        description="Phase 1 service foundation; AI capabilities are not implemented.",
        version=runtime.app_version,
    )

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(
            version=runtime.app_version,
            environment=runtime.app_env,
        )

    return application


app = create_app()

