"""
Request context middleware.

Generates or propagates X-Request-ID headers and stores request context
(request_id, timing) in a ContextVar so all downstream code can access it.
"""

import time
import logging
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

# Context variable for the current request ID
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get the current request ID from context."""
    return _request_id_var.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate or propagate request ID
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        token = _request_id_var.set(request_id)

        start_time = time.time()
        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            _request_id_var.reset(token)

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "%s %s %s %.0fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={"duration_ms": duration_ms},
        )

        return response
