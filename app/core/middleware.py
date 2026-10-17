"""Request middleware: assigns a request ID and logs one line per request.

Written as a plain ASGI middleware (not BaseHTTPMiddleware) so the request ID
context variable is visible to every handler and exception handler downstream.
"""
import logging
import re
import time
import uuid

from app.core.constants import REQUEST_ID_HEADER
from app.core.request_context import request_id_context

logger = logging.getLogger("app.request")

SAFE_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
REQUEST_ID_HEADER_BYTES = REQUEST_ID_HEADER.lower().encode("latin-1")


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._resolve_request_id(scope)
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id
        context_token = request_id_context.set(request_id)
        started_at = time.perf_counter()
        response_status = {"code": 500}

        async def send_with_request_id(message):
            if message["type"] == "http.response.start":
                response_status["code"] = message["status"]
                response_headers = list(message.get("headers", []))
                response_headers.append((REQUEST_ID_HEADER_BYTES, request_id.encode("latin-1")))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.info(
                "%s %s -> %d in %d ms",
                scope.get("method", "-"),
                scope.get("path", "-"),
                response_status["code"],
                duration_ms,
            )
            request_id_context.reset(context_token)

    @staticmethod
    def _resolve_request_id(scope) -> str:
        """Reuse the caller's X-Request-ID if it is safe, otherwise create a new one."""
        for header_name, header_value in scope.get("headers", []):
            if header_name == REQUEST_ID_HEADER_BYTES:
                incoming_request_id = header_value.decode("latin-1")
                if SAFE_REQUEST_ID_PATTERN.match(incoming_request_id):
                    return incoming_request_id
        return uuid.uuid4().hex[:16]
