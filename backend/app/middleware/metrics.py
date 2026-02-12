"""
Prometheus metrics middleware.

Collects HTTP request metrics (counter + histogram) and exposes application-level
gauges/counters for pipeline, agent, and case monitoring.
"""

import time

from prometheus_client import Counter, Histogram, Gauge
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# ── HTTP metrics ─────────────────────────────────────────────────────────────

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

# ── Pipeline metrics ─────────────────────────────────────────────────────────

pipeline_runs_total = Counter(
    "pipeline_runs_total",
    "Total pipeline runs",
    ["workspace", "status"],
)

pipeline_duration_seconds = Histogram(
    "pipeline_duration_seconds",
    "Pipeline run duration in seconds",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

pipeline_claims_processed = Counter(
    "pipeline_claims_processed",
    "Total claims processed by pipeline",
)

# ── Agent metrics ────────────────────────────────────────────────────────────

agent_chat_requests_total = Counter(
    "agent_chat_requests_total",
    "Total agent chat requests",
    ["model_used"],
)

agent_chat_duration_seconds = Histogram(
    "agent_chat_duration_seconds",
    "Agent chat response duration in seconds",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# ── Case metrics ─────────────────────────────────────────────────────────────

active_cases_by_risk_level = Gauge(
    "active_cases_by_risk_level",
    "Number of active investigation cases by risk level",
    ["risk_level"],
)


def _normalize_path(path: str) -> str:
    """Collapse path parameters to reduce cardinality.

    e.g. /api/cases/CASE-ABC123 → /api/cases/{id}
    """
    parts = path.strip("/").split("/")
    normalized = []
    for i, part in enumerate(parts):
        if i > 1 and (
            part.startswith("CASE-")
            or part.startswith("CLM-")
            or part.startswith("RULE-")
            or part.isdigit()
            or len(part) > 20
        ):
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint itself to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = _normalize_path(request.url.path)

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        http_requests_total.labels(
            method=method,
            path=path,
            status_code=response.status_code,
        ).inc()

        http_request_duration_seconds.labels(
            method=method,
            path=path,
        ).observe(duration)

        return response
