import json
import logging
import re
from time import monotonic
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
LOGGER = logging.getLogger("synapse.http")


class RequestSecurityMiddleware:
    """Adds safe request IDs, response hardening headers, and body-free JSON access logs."""

    def __init__(self, app: ASGIApp, *, environment: str, logging_enabled: bool) -> None:
        self._app = app
        self._production = environment == "production"
        self._logging_enabled = logging_enabled

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        request_id = _safe_identifier(headers.get(b"x-request-id"))
        correlation_id = _safe_identifier(headers.get(b"x-correlation-id"))
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        state["correlation_id"] = correlation_id
        started = monotonic()
        status_code = 500

        async def send_hardened(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                response_headers = MutableHeaders(scope=message)
                response_headers.setdefault("X-Request-ID", request_id)
                response_headers.setdefault("X-Correlation-ID", correlation_id)
                response_headers.setdefault("X-Content-Type-Options", "nosniff")
                response_headers.setdefault("X-Frame-Options", "DENY")
                response_headers.setdefault("Referrer-Policy", "no-referrer")
                response_headers.setdefault(
                    "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
                )
                response_headers.setdefault("Cache-Control", "no-store")
                if self._production:
                    response_headers.setdefault(
                        "Content-Security-Policy",
                        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
                    )
                    response_headers.setdefault(
                        "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
                    )
            await send(message)

        try:
            await self._app(scope, receive, send_hardened)
        finally:
            if self._logging_enabled:
                LOGGER.info(
                    json.dumps(
                        {
                            "correlation_id": correlation_id,
                            "duration_ms": round((monotonic() - started) * 1_000, 3),
                            "event": "http.request.completed",
                            "method": scope.get("method", ""),
                            "path": scope.get("path", ""),
                            "request_id": request_id,
                            "service": "synapse-ai-service",
                            "status": status_code,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                )


def _safe_identifier(raw_value: bytes | None) -> str:
    if raw_value is not None:
        try:
            value = raw_value.decode("ascii")
        except UnicodeDecodeError:
            value = ""
        if SAFE_ID_PATTERN.fullmatch(value):
            return value
    return str(uuid4())
