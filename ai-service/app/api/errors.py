from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.providers.errors import ProviderError, ProviderRateLimitError, ProviderTransientError
from app.services.document_errors import DocumentError
from app.services.video_errors import VideoDependencyError, VideoError


def register_provider_error_handlers(application: FastAPI) -> None:
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
