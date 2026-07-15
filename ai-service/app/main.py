from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_provider_error_handlers
from app.api.router import api_router
from app.api.routes.debug import router as debug_router
from app.core.config import Settings, get_settings
from app.core.http_security import RequestSecurityMiddleware
from app.evaluation.repository import (
    EvaluationSummaryRepository,
    create_evaluation_repository,
)
from app.providers.base import LLMProvider
from app.providers.factory import create_llm_provider
from app.repositories.metadata import (
    DatasetMetadataAdapter,
    DocumentMetadataAdapter,
    VideoMetadataAdapter,
)
from app.services.analytics_factory import create_analytics_service
from app.services.analytics_service import AnalyticsService
from app.services.document_factory import create_document_rag_service
from app.services.document_rag import DocumentRAGService
from app.services.orchestrator import SynapseOrchestrator
from app.services.persistence_factory import PersistenceBundle, create_persistence_bundle
from app.services.readiness import RetrievalReadiness
from app.services.uploads import UploadCoordinator
from app.services.video_factory import create_video_rag_service
from app.services.video_rag import VideoRAGService
from app.vectorstores.adapters import DocumentVectorStoreAdapter, VideoVectorStoreAdapter


def create_app(
    settings: Settings | None = None,
    provider: LLMProvider | None = None,
    document_service: DocumentRAGService | None = None,
    video_service: VideoRAGService | None = None,
    analytics_service: AnalyticsService | None = None,
    persistence: PersistenceBundle | None = None,
    evaluation_repository: EvaluationSummaryRepository | None = None,
) -> FastAPI:
    """Build the HTTP application with explicit, testable runtime settings."""

    runtime = settings or get_settings()
    active_provider = provider or create_llm_provider(runtime)
    active_persistence = persistence or create_persistence_bundle(runtime)
    active_evaluation_repository = evaluation_repository or create_evaluation_repository(runtime)
    active_document_service = document_service or create_document_rag_service(
        runtime,
        active_provider,
        repository=DocumentMetadataAdapter(active_persistence.metadata),
        vector_store=DocumentVectorStoreAdapter(active_persistence.vectors),
    )
    active_video_service = video_service or create_video_rag_service(
        runtime,
        active_provider,
        repository=VideoMetadataAdapter(active_persistence.metadata),
        vector_store=VideoVectorStoreAdapter(active_persistence.vectors),
    )
    active_analytics_service = analytics_service or create_analytics_service(
        runtime,
        active_provider,
        repository=DatasetMetadataAdapter(active_persistence.metadata),
    )
    readiness = RetrievalReadiness(active_document_service, active_video_service)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        readiness.start()
        yield
        readiness.wait(timeout=1)

    application = FastAPI(
        title="Synapse AI Service",
        description="Grounded document/video retrieval and constrained CSV analytics for Synapse.",
        version=runtime.app_version,
        lifespan=lifespan,
        docs_url=None if runtime.app_env == "production" else "/docs",
        redoc_url=None if runtime.app_env == "production" else "/redoc",
        openapi_url=None if runtime.app_env == "production" else "/openapi.json",
    )
    application.add_middleware(
        RequestSecurityMiddleware,
        environment=runtime.app_env,
        logging_enabled=runtime.app_env != "test",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime.ai_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Correlation-ID", "X-Request-ID"],
        expose_headers=["X-Correlation-ID", "X-Request-ID"],
    )
    application.state.settings = runtime
    application.state.llm_provider = active_provider
    application.state.document_service = active_document_service
    application.state.video_service = active_video_service
    application.state.analytics_service = active_analytics_service
    application.state.persistence = active_persistence
    application.state.readiness = readiness
    application.state.evaluation_repository = active_evaluation_repository
    application.state.upload_coordinator = UploadCoordinator(
        settings=runtime,
        metadata=active_persistence.metadata,
        objects=active_persistence.objects,
        documents=active_document_service,
        videos=active_video_service,
    )
    application.state.orchestrator = SynapseOrchestrator(
        provider=active_provider,
        document_retriever=active_document_service,
        document_context_top_k=runtime.final_context_k,
        video_retriever=active_video_service,
        video_context_top_k=runtime.video_search_top_k,
        analytics=active_analytics_service,
    )
    register_provider_error_handlers(application)
    application.include_router(api_router)
    if runtime.debug:
        application.include_router(debug_router)

    return application


app = create_app()
