from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.providers.errors import ProviderError, ProviderRateLimitError, ProviderTransientError


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
