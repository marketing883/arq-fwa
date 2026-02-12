import logging
import traceback
from contextlib import asynccontextmanager

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:80", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "environment": settings.environment}
