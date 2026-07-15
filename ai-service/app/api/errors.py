import json
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.providers.errors import ProviderError, ProviderRateLimitError, ProviderTransientError
from app.services.analytics_errors import AnalyticsError
from app.services.document_errors import DocumentError
from app.services.video_errors import VideoDependencyError, VideoError

LOGGER = logging.getLogger("synapse.errors")


def register_provider_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        del error
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request did not match the required schema.",
                    "retryable": False,
                }
            },
        )

    @application.exception_handler(AnalyticsError)
    async def handle_analytics_error(
        request: Request,
        error: AnalyticsError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "retryable": False,
                }
            },
        )

    @application.exception_handler(ProviderError)
    async def handle_provider_error(
        request: Request,
        error: ProviderError,
    ) -> JSONResponse:
        del request
        if isinstance(error, ProviderRateLimitError):
            status_code = 429
        elif isinstance(error, ProviderTransientError):
            status_code = 503
        else:
            status_code = 502

        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "retryable": error.retryable,
                }
            },
        )

    @application.exception_handler(DocumentError)
    async def handle_document_error(
        request: Request,
        error: DocumentError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "retryable": False,
                }
            },
        )

    @application.exception_handler(VideoError)
    async def handle_video_error(
        request: Request,
        error: VideoError,
    ) -> JSONResponse:
        del request
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "retryable": isinstance(error, VideoDependencyError),
                }
            },
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unavailable")
        correlation_id = getattr(request.state, "correlation_id", "unavailable")
        LOGGER.error(
            json.dumps(
                {
                    "correlation_id": correlation_id,
                    "error_type": type(error).__name__,
                    "event": "http.request.failed",
                    "request_id": request_id,
                    "service": "synapse-ai-service",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "The request could not be completed.",
                    "retryable": False,
                }
            },
        )
