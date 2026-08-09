"""Request-ID middleware: every request gets/propagates an id, logged with latency.

Health probes are deliberately NOT access-logged — the compose healthcheck polls every
few seconds and would otherwise be the dominant "request" in every log forever.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_ctx

logger = logging.getLogger("cropmind.http")

_QUIET_PATHS = frozenset({"/health", "/health/ready"})


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            response.headers["X-Request-ID"] = request_id
            if request.url.path not in _QUIET_PATHS:
                # Log while the contextvar is still set — the formatter reads it at emit
                # time, and the finally-block reset made every access line show "-".
                logger.info(
                    "%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code, duration_ms
                )
            return response
        finally:
            request_id_ctx.reset(token)
