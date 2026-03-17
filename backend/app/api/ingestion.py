"""
Ingestion API — manage data sources and ingestion runs.
"""

from uuid import uuid4

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.auth.permissions import Permission
from app.auth.context import RequestContext
from app.models.data_source import DataSource
from app.models.ingestion_run import IngestionRun
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class DataSourceCreate(BaseModel):
    name: str = Field(..., max_length=100)
    source_type: str = Field(
        ..., pattern="^(watched_folder|api_endpoint|database_query)$"
    )
    claim_type: str = Field(..., pattern="^(medical|pharmacy)$")
    connection_config: dict = Field(default_factory=dict)
    field_mapping: dict = Field(default_factory=dict)
    polling_interval_seconds: int = Field(3600, ge=60, le=86400)
    auto_run_pipeline: bool = True
    workspace_id: int | None = None


class DataSourceUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    connection_config: dict | None = None
    field_mapping: dict | None = None
    polling_interval_seconds: int | None = Field(None, ge=60, le=86400)
    is_enabled: bool | None = None
    auto_run_pipeline: bool | None = None


class DataSourceResponse(BaseModel):
    source_id: str
    name: str
    source_type: str
    claim_type: str
    connection_config: dict
    field_mapping: dict
    polling_interval_seconds: int
    is_enabled: bool
    auto_run_pipeline: bool
    workspace_id: int | None
    last_polled_at: str | None
    created_at: str | None


class IngestionRunResponse(BaseModel):
    run_id: str
    data_source_id: int
    status: str
    rows_found: int
    rows_ingested: int
    rows_skipped: int
    error_count: int
    errors: dict | None
    batch_id: str | None
    pipeline_job_id: str | None
    duration_seconds: float | None
    started_at: str | None
    completed_at: str | None


# ── Data Source endpoints ────────────────────────────────────────────────────


def _source_response(s: DataSource) -> DataSourceResponse:
    return DataSourceResponse(
        source_id=s.source_id,
        name=s.name,
        source_type=s.source_type,
        claim_type=s.claim_type,
        connection_config=s.connection_config or {},
        field_mapping=s.field_mapping or {},
        polling_interval_seconds=s.polling_interval_seconds,
        is_enabled=s.is_enabled,
        auto_run_pipeline=s.auto_run_pipeline,
        workspace_id=s.workspace_id,
        last_polled_at=str(s.last_polled_at) if s.last_polled_at else None,
        created_at=str(s.created_at) if s.created_at else None,
    )


@router.get("/sources")
async def list_sources(
    workspace_id: int | None = Query(None),
    ctx: RequestContext = Depends(require(Permission.WORKSPACE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """List all data sources."""
    conditions = []
    if workspace_id is not None:
        conditions.append(DataSource.workspace_id == workspace_id)

    where_clause = and_(*conditions) if conditions else True
    result = await db.execute(
        select(DataSource)
        .where(where_clause)
        .order_by(DataSource.created_at.desc())
    )
    sources = list(result.scalars())

    return {
        "sources": [_source_response(s) for s in sources],
        "total": len(sources),
    }


@router.post("/sources", status_code=201)
async def create_source(
    body: DataSourceCreate,
    ctx: RequestContext = Depends(require(Permission.WORKSPACE_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new data source."""
    source = DataSource(
        source_id=f"SRC-{uuid4().hex[:8].upper()}",
        name=body.name,
        source_type=body.source_type,
        claim_type=body.claim_type,
        connection_config=body.connection_config,
        field_mapping=body.field_mapping,
        polling_interval_seconds=body.polling_interval_seconds,
        auto_run_pipeline=body.auto_run_pipeline,
        workspace_id=body.workspace_id,
    )
    db.add(source)
    await db.flush()

    return _source_response(source)


@router.get("/sources/{source_id}")
async def get_source(
    source_id: str,
    ctx: RequestContext = Depends(require(Permission.WORKSPACE_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Get data source detail."""
    result = await db.execute(
        select(DataSource).where(DataSource.source_id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    return _source_response(source)


@router.put("/sources/{source_id}")
async def update_source(
    source_id: str,
    body: DataSourceUpdate,
    ctx: RequestContext = Depends(require(Permission.WORKSPACE_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Update data source config."""
    result = await db.execute(
        select(DataSource).where(DataSource.source_id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(source, field, value)

    await db.flush()
    return _source_response(source)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: str,
    ctx: RequestContext = Depends(require(Permission.WORKSPACE_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Delete a data source."""
    result = await db.execute(
        select(DataSource).where(DataSource.source_id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    await db.delete(source)
    await db.flush()


@router.post("/sources/{source_id}/test")
async def test_source_connection(
    source_id: str,
    ctx: RequestContext = Depends(require(Permission.WORKSPACE_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Test connection, return sample rows."""
    result = await db.execute(
        select(DataSource).where(DataSource.source_id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    svc = IngestionService(db)
    return await svc.test_connection(source)


@router.post("/sources/{source_id}/poll-now")
async def poll_source_now(
    source_id: str,
    ctx: RequestContext = Depends(require(Permission.PIPELINE_RUN)),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger an immediate poll."""
    result = await db.execute(
        select(DataSource).where(DataSource.source_id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    svc = IngestionService(db)
    run = await svc.poll_source(source)

    return IngestionRunResponse(
        run_id=run.run_id,
        data_source_id=run.data_source_id,
        status=run.status,
        rows_found=run.rows_found,
        rows_ingested=run.rows_ingested,
        rows_skipped=run.rows_skipped,
        error_count=run.error_count,
        errors=run.errors,
        batch_id=run.batch_id,
        pipeline_job_id=run.pipeline_job_id,
        duration_seconds=run.duration_seconds,
        started_at=str(run.started_at) if run.started_at else None,
        completed_at=str(run.completed_at) if run.completed_at else None,
    )


# ── Ingestion Run endpoints ─────────────────────────────────────────────────


@router.get("/runs")
async def list_runs(
    source_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    ctx: RequestContext = Depends(require(Permission.PIPELINE_STATUS)),
    db: AsyncSession = Depends(get_db),
):
    """List ingestion runs."""
    conditions = []
    if source_id:
        # Look up the data source by source_id string
        src_result = await db.execute(
            select(DataSource.id).where(DataSource.source_id == source_id)
        )
        src_pk = src_result.scalar_one_or_none()
        if src_pk:
            conditions.append(IngestionRun.data_source_id == src_pk)

    where_clause = and_(*conditions) if conditions else True
    result = await db.execute(
        select(IngestionRun)
        .where(where_clause)
        .order_by(IngestionRun.started_at.desc())
        .limit(limit)
    )
    runs = list(result.scalars())

    return {
        "runs": [
            IngestionRunResponse(
                run_id=r.run_id,
                data_source_id=r.data_source_id,
                status=r.status,
                rows_found=r.rows_found,
                rows_ingested=r.rows_ingested,
                rows_skipped=r.rows_skipped,
                error_count=r.error_count,
                errors=r.errors,
                batch_id=r.batch_id,
                pipeline_job_id=r.pipeline_job_id,
                duration_seconds=r.duration_seconds,
                started_at=str(r.started_at) if r.started_at else None,
                completed_at=str(r.completed_at) if r.completed_at else None,
            )
            for r in runs
        ],
        "total": len(runs),
    }


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    ctx: RequestContext = Depends(require(Permission.PIPELINE_STATUS)),
    db: AsyncSession = Depends(get_db),
):
    """Get detail of a specific ingestion run."""
    result = await db.execute(
        select(IngestionRun).where(IngestionRun.run_id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Ingestion run not found")

    return IngestionRunResponse(
        run_id=run.run_id,
        data_source_id=run.data_source_id,
        status=run.status,
        rows_found=run.rows_found,
        rows_ingested=run.rows_ingested,
        rows_skipped=run.rows_skipped,
        error_count=run.error_count,
        errors=run.errors,
        batch_id=run.batch_id,
        pipeline_job_id=run.pipeline_job_id,
        duration_seconds=run.duration_seconds,
        started_at=str(run.started_at) if run.started_at else None,
        completed_at=str(run.completed_at) if run.completed_at else None,
    )
