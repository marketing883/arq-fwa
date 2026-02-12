from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.api.dashboard import router as dashboard_router
from app.api.claims import router as claims_router
from app.api.rules import router as rules_router
from app.api.cases import router as cases_router
from app.api.scoring import router as scoring_router
from app.api.audit import router as audit_router


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

# Register API routers
app.include_router(dashboard_router)
app.include_router(claims_router)
app.include_router(rules_router)
app.include_router(cases_router)
app.include_router(scoring_router)
app.include_router(audit_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "environment": settings.environment}
