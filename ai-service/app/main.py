from fastapi import FastAPI

from app.api.errors import register_provider_error_handlers
from app.api.router import api_router
from app.api.routes.debug import router as debug_router
from app.core.config import Settings, get_settings
from app.providers.base import LLMProvider
from app.providers.factory import create_llm_provider
from app.services.document_factory import create_document_rag_service
from app.services.document_rag import DocumentRAGService
from app.services.orchestrator import SynapseOrchestrator
from app.services.video_factory import create_video_rag_service
from app.services.video_rag import VideoRAGService


def create_app(
    settings: Settings | None = None,
    provider: LLMProvider | None = None,
    document_service: DocumentRAGService | None = None,
    video_service: VideoRAGService | None = None,
) -> FastAPI:
    """Build the HTTP application with explicit, testable runtime settings."""

    runtime = settings or get_settings()
    active_provider = provider or create_llm_provider(runtime)
    active_document_service = document_service or create_document_rag_service(
        runtime,
        active_provider,
    )
    active_video_service = video_service or create_video_rag_service(
        runtime,
        active_provider,
    )
    application = FastAPI(
        title="Synapse AI Service",
        description="Grounded document and timestamped video retrieval for Synapse.",
        version=runtime.app_version,
    )
    application.state.settings = runtime
    application.state.llm_provider = active_provider
    application.state.document_service = active_document_service
    application.state.video_service = active_video_service
    application.state.orchestrator = SynapseOrchestrator(
        provider=active_provider,
        document_retriever=active_document_service,
        document_context_top_k=runtime.final_context_k,
        video_retriever=active_video_service,
        video_context_top_k=runtime.video_search_top_k,
    )
    register_provider_error_handlers(application)
    application.include_router(api_router)
    if runtime.debug:
        application.include_router(debug_router)

    return application


app = create_app()
