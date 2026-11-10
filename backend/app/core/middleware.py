"""HTTP correlation ID and structured observability middleware for PAYFLOW AI (Prompt 40).

Guarantees:
- Every request carries a persistent or generated correlation ID.
- Injects X-Correlation-ID and X-Request-ID response headers.
- Emits structured access logs with method, path, status, and duration (ms).
- Records operational API error metrics categorized safely.
- Never logs Authorization headers, credentials, or customer PII.
"""

import time
import uuid
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import logger
from app.core.metrics import metrics_collector


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware attaching correlation/request IDs and collecting structured metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Extract existing correlation ID or generate fresh UUID4
        correlation_id = (
            request.headers.get("X-Correlation-ID")
            or request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )
        request.state.correlation_id = correlation_id

        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            # Log unhandled exception with correlation ID
            logger.error(
                "Unhandled error in %s %s [cid=%s duration=%sms]: %s",
                request.method,
                request.url.path,
                correlation_id,
                duration_ms,
                type(exc).__name__,
            )
            metrics_collector.record_request(request.method, request.url.path, 500)
            raise exc

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # 2. Attach correlation headers to response
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = correlation_id

        # 3. Record operational metrics
        metrics_collector.record_request(request.method, request.url.path, response.status_code)

        # 4. Structured log for non-health endpoints to avoid log flooding
        if not request.url.path.startswith("/health"):
            log_level = logger.info if response.status_code < 400 else logger.warning
            log_level(
                "%s %s -> %s [cid=%s duration=%sms]",
                request.method,
                request.url.path,
                response.status_code,
                correlation_id,
                duration_ms,
            )

        return response

