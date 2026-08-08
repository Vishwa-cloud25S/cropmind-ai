"""Request-ID middleware: every request gets/propagates an id, logged with latency."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_ctx

logger = logging.getLogger("cropmind.http")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s (%.1fms)", request.method, request.url.path, response.status_code, duration_ms
        )
        return response
