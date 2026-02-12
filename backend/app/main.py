import logging
import time
import traceback
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine

# Configure logging so errors are visible in Docker logs
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
from app.api.dashboard import router as dashboard_router
from app.api.claims import router as claims_router
from app.api.rules import router as rules_router
from app.api.cases import router as cases_router
from app.api.scoring import router as scoring_router
from app.api.audit import router as audit_router
from app.api.agents import router as agents_router
from app.api.pipeline import router as pipeline_router
from app.api.workspaces import router as workspaces_router
from app.api.providers import router as providers_router
from app.api.metrics import router as metrics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection
    async with engine.begin() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="ArqAI FWA Detection & Prevention",
    description="Fraud, Waste, and Abuse detection for Insurance/TPA",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS (tightened) ─────────────────────────────────────────────────────────
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

# ── Security headers middleware ──────────────────────────────────────────────
from app.middleware.security_headers import SecurityHeadersMiddleware  # noqa: E402

app.add_middleware(SecurityHeadersMiddleware)

# ── Rate limiting middleware ─────────────────────────────────────────────────
from app.middleware.rate_limit import RateLimitMiddleware  # noqa: E402

app.add_middleware(RateLimitMiddleware)

# ── Request context middleware (request ID + timing) ─────────────────────────
from app.middleware.request_context import RequestContextMiddleware  # noqa: E402

app.add_middleware(RequestContextMiddleware)

# ── Prometheus metrics middleware ────────────────────────────────────────────
from app.middleware.metrics import PrometheusMiddleware  # noqa: E402

app.add_middleware(PrometheusMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return detailed error info in development mode so 500s are debuggable."""
    tb = traceback.format_exc()
    logging.getLogger("app").error(
        "Unhandled %s on %s %s: %s\n%s",
        type(exc).__name__, request.method, request.url.path, exc, tb,
    )
    detail = f"{type(exc).__name__}: {exc}"
    if settings.environment == "development":
        return JSONResponse(
            status_code=500,
            content={"detail": detail, "traceback": tb.splitlines()[-5:]},
        )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


# Register API routers
app.include_router(dashboard_router)
app.include_router(claims_router)
app.include_router(rules_router)
app.include_router(cases_router)
app.include_router(scoring_router)
app.include_router(audit_router)
app.include_router(agents_router)
app.include_router(pipeline_router)
app.include_router(workspaces_router)
app.include_router(providers_router)
app.include_router(metrics_router)


# ── Health check (expanded) ──────────────────────────────────────────────────

_health_cache: dict = {}
_health_cache_ts: float = 0.0
HEALTH_CACHE_TTL = 10.0  # seconds


@app.get("/api/health")
async def health_check():
    global _health_cache, _health_cache_ts

    now = time.time()
    if _health_cache and (now - _health_cache_ts) < HEALTH_CACHE_TTL:
        return _health_cache

    components: dict = {}

    # Database
    try:
        async with engine.begin() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        components["database"] = {"status": "connected"}
    except Exception as exc:
        components["database"] = {"status": "disconnected", "error": str(exc)}

    # Redis
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        await r.aclose()
        components["redis"] = {"status": "connected"}
    except Exception as exc:
        components["redis"] = {"status": "disconnected", "error": str(exc)}

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{settings.ollama_url}/api/show",
                json={"name": settings.llm_model},
            )
            if resp.status_code == 200:
                components["ollama"] = {"status": "ready", "model": settings.llm_model}
            else:
                components["ollama"] = {"status": "loading", "model": settings.llm_model}
    except Exception:
        components["ollama"] = {"status": "unavailable"}

    # Overall status
    db_ok = components["database"]["status"] == "connected"
    redis_ok = components["redis"]["status"] == "connected"

    if db_ok and redis_ok:
        overall = "healthy"
    elif not db_ok:
        overall = "unhealthy"
    else:
        overall = "degraded"

    result = {
        "status": overall,
        "environment": settings.environment,
        "components": components,
    }

    _health_cache = result
    _health_cache_ts = now
    return result
