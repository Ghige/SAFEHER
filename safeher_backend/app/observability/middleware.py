"""Stage 11 request access / failure middleware."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.observability import metrics

logger = logging.getLogger("safeher.access")


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Record duration_ms, status, and failed-request counters.
    Does not log bodies, Authorization, phones, or coordinates.
    """

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        request_id = getattr(request.state, "request_id", None)
        path = request.url.path
        method = request.method
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000.0, 2)
            metrics.incr("http_requests_total")
            metrics.observe_ms("http_request", duration_ms)
            metrics.incr(f"http_status_{status_code}")
            if status_code >= 400:
                metrics.incr("http_failed_requests_total")
                if status_code >= 500:
                    metrics.incr("http_5xx_total")
                elif status_code == 429:
                    metrics.incr("http_429_total")
                else:
                    metrics.incr("http_4xx_total")

            # Skip noisy health probes at DEBUG; always log failures
            is_health = path.rstrip("/").endswith("/ping") or path.rstrip("/").endswith(
                "/ping/ready"
            )
            if status_code >= 400 or not is_health:
                extra = {
                    "request_id": request_id,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
                msg = f"{method} {path} status={status_code} duration_ms={duration_ms}"
                if status_code >= 500:
                    logger.error(msg, extra=extra)
                elif status_code >= 400:
                    logger.warning(msg, extra=extra)
                else:
                    logger.info(msg, extra=extra)
