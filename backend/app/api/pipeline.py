"""
Pipeline API — Full end-to-end FWA detection pipeline.

POST /api/pipeline/run-full
  Runs the complete pipeline: load → enrich → evaluate → score → create cases → audit
POST /api/pipeline/enqueue
  Enqueue pipeline as a background job (returns immediately)
GET /api/pipeline/jobs/{job_id}
  Check status of a background pipeline job
GET /api/pipeline/runs
  List past pipeline runs with stats
GET /api/pipeline/runs/{run_id}
  Detail for a specific pipeline run
"""

import json
import time
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.auth.permissions import Permission
from app.auth.context import RequestContext
from app.models import (
    MedicalClaim,
    PharmacyClaim,
    RiskScore,
    RuleResult,
    InvestigationCase,
    Workspace,
)
from app.models.pipeline_run import PipelineRun
from app.services.enrichment import EnrichmentService
from app.services.rule_engine import RuleEngine
from app.services.scoring_engine import ScoringEngine
from app.services.case_manager import CaseManager
from app.services.audit_service import AuditService
from app.services.data_quality import DataQualityService
from app.services.job_queue import enqueue_pipeline_job, get_job_status
from app.middleware.metrics import (
    pipeline_runs_total, pipeline_duration_seconds, pipeline_claims_processed,
)
from pydantic import BaseModel, Field


class PipelineRunRequest(BaseModel):
    limit: int = Field(1000, ge=1, le=50000, description="Max claims per type to process")
    batch_id: str | None = Field(None, description="Process specific batch only")
    workspace_id: str | None = Field(None, description="Filter claims by workspace")
    force_reprocess: bool = Field(False, description="Re-process already scored claims")


class PipelineRunResponse(BaseModel):
    batch_id: str
    medical_claims: int
    pharmacy_claims: int
    total_claims: int
    rules_evaluated: int
    scores_generated: int
    cases_created: int
    high_risk: int
    critical_risk: int
    processing_time_seconds: float
    quality_report: dict | None = None


class PipelineStatusResponse(BaseModel):
    total_medical_claims: int
    total_pharmacy_claims: int
    scored_claims: int
    unscored_claims: int
    total_cases: int
    open_cases: int
    total_rule_results: int
    total_audit_entries: int


class EnqueueRequest(BaseModel):
    limit: int = Field(1000, ge=1, le=50000)
    workspace_id: str | None = None
    batch_id: str | None = None
    force_reprocess: bool = False


class EnqueueResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    phase: str
    progress: int
    claims_processed: int
    errors: int
    started_at: str
    completed_at: str
    result: dict | None = None


class PipelineRunSummary(BaseModel):
    run_id: str
    workspace_id: int | None = None
    batch_id: str
    started_at: str | None = None
    completed_at: str | None = None
    status: str
    duration_seconds: float | None = None
    stats: dict | None = None


class PipelineRunDetail(PipelineRunSummary):
    config_snapshot: dict | None = None
    quality_report: dict | None = None


router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run-full", response_model=PipelineRunResponse)
async def run_full_pipeline(
    body: PipelineRunRequest,
    ctx: RequestContext = Depends(require(Permission.PIPELINE_RUN)),
    db: AsyncSession = Depends(get_db),
) -> PipelineRunResponse:
    """
    Run the full FWA detection pipeline end-to-end:

    1. Load unscored claims (medical + pharmacy)
    2. Data quality validation
    3. Enrich with reference data and historical context
    4. Evaluate all 29 enabled rules
    5. Calculate risk scores
    6. Auto-create investigation cases for high/critical risk
    7. Record pipeline run with stats
    8. Log all actions to audit trail
    """

    t_start = time.time()
    batch_id = body.batch_id or f"PIPE-{uuid4().hex[:12].upper()}"
    run_id = f"RUN-{uuid4().hex[:12].upper()}"

    # Resolve optional workspace_id to internal integer id
    ws_id = None
    if body.workspace_id:
        ws_result = await db.execute(select(Workspace).where(Workspace.workspace_id == body.workspace_id))
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws_id = ws.id

    # ── 1. Load unscored claims ──────────────────────────────────────────
    if body.force_reprocess:
        med_q = select(MedicalClaim)
        rx_q = select(PharmacyClaim)
    else:
        scored_med_ids = select(RiskScore.claim_id).where(RiskScore.claim_type == "medical")
        scored_rx_ids = select(RiskScore.claim_id).where(RiskScore.claim_type == "pharmacy")
        med_q = select(MedicalClaim).where(MedicalClaim.claim_id.not_in(scored_med_ids))
        rx_q = select(PharmacyClaim).where(PharmacyClaim.claim_id.not_in(scored_rx_ids))

    if ws_id is not None:
        med_q = med_q.where(MedicalClaim.workspace_id == ws_id)
        rx_q = rx_q.where(PharmacyClaim.workspace_id == ws_id)

    med_q = med_q.order_by(MedicalClaim.created_at.asc()).limit(body.limit)
    rx_q = rx_q.order_by(PharmacyClaim.created_at.asc()).limit(body.limit)

    med_result = await db.execute(med_q)
    rx_result = await db.execute(rx_q)

    med_claims = list(med_result.scalars())
    rx_claims = list(rx_result.scalars())

    total_claims = len(med_claims) + len(rx_claims)

    if total_claims == 0:
        return PipelineRunResponse(
            batch_id=batch_id,
            medical_claims=0,
            pharmacy_claims=0,
            total_claims=0,
            rules_evaluated=0,
            scores_generated=0,
            cases_created=0,
            high_risk=0,
            critical_risk=0,
            processing_time_seconds=round(time.time() - t_start, 3),
        )

    # ── 2. Data quality validation ───────────────────────────────────────
    dq = DataQualityService(db)
    med_quality = await dq.validate_medical_claims(med_claims)
    rx_quality = await dq.validate_pharmacy_claims(rx_claims)
    quality_report = {
        "medical": med_quality.to_dict(),
        "pharmacy": rx_quality.to_dict(),
    }

    # ── 3. Enrich ────────────────────────────────────────────────────────
    enrichment = EnrichmentService(db)
    enriched_medical = await enrichment.enrich_medical_batch(med_claims) if med_claims else []
    enriched_pharmacy = await enrichment.enrich_pharmacy_batch(rx_claims) if rx_claims else []

    # ── 4. Rule engine ───────────────────────────────────────────────────
    rule_engine = RuleEngine(db)
    await rule_engine.load_rules()
    await rule_engine.load_configs()

    med_results = await rule_engine.evaluate_batch(enriched_medical, batch_id) if enriched_medical else {}
    rx_results = await rule_engine.evaluate_batch(enriched_pharmacy, batch_id) if enriched_pharmacy else {}

    rules_saved = 0
    rules_saved += await rule_engine.save_results(med_results)
    rules_saved += await rule_engine.save_results(rx_results)

    # Stamp workspace_id on all rule results (inherit from claims)
    claim_ws_map: dict[str, int | None] = {}
    for c in med_claims:
        claim_ws_map[c.claim_id] = ws_id if ws_id is not None else c.workspace_id
    for c in rx_claims:
        claim_ws_map[c.claim_id] = ws_id if ws_id is not None else c.workspace_id
    for rr_list in list(med_results.values()) + list(rx_results.values()):
        for rr in rr_list:
            rr.workspace_id = claim_ws_map.get(rr.claim_id)

    # ── 5. Score ─────────────────────────────────────────────────────────
    scoring = ScoringEngine(db)
    med_scores = await scoring.score_batch(med_results, "medical", batch_id) if med_results else []
    rx_scores = await scoring.score_batch(rx_results, "pharmacy", batch_id) if rx_results else []

    all_scores = med_scores + rx_scores

    # Stamp workspace_id on all scores (inherit from claims)
    for score in all_scores:
        score.workspace_id = claim_ws_map.get(score.claim_id)

    scores_saved = await scoring.save_scores(all_scores)

    # ── 6. Update claim statuses ─────────────────────────────────────────
    for claim in med_claims:
        claim.status = "processed"
        claim.batch_id = batch_id
    for claim in rx_claims:
        claim.status = "processed"
        claim.batch_id = batch_id

    await db.flush()

    # ── 7. Auto-create cases with evidence bundles ───────────────────────
    case_manager = CaseManager(db)
    new_cases = await case_manager.create_cases_from_scores(
        all_scores, generate_evidence=True, workspace_id=ws_id,
        claim_ws_map=claim_ws_map,
    )

    # Count risk levels
    high_count = sum(1 for s in all_scores if s.risk_level == "high")
    critical_count = sum(1 for s in all_scores if s.risk_level == "critical")

    t_end = time.time()
    duration = round(t_end - t_start, 3)

    # ── 8. Record pipeline run ───────────────────────────────────────────
    pipeline_run = PipelineRun(
        run_id=run_id,
        workspace_id=ws_id,
        batch_id=batch_id,
        status="completed",
        completed_at=datetime.utcnow(),
        duration_seconds=duration,
        stats={
            "medical_claims": len(med_claims),
            "pharmacy_claims": len(rx_claims),
            "rules_evaluated": rules_saved,
            "scores_generated": scores_saved,
            "cases_created": len(new_cases),
            "high_risk": high_count,
            "critical_risk": critical_count,
        },
        quality_report=quality_report,
    )
    db.add(pipeline_run)

    # ── 9. Audit: pipeline run event ─────────────────────────────────────
    audit = AuditService(db)
    await audit.log_event(
        event_type="pipeline_run",
        actor=ctx.actor,
        action=f"Full pipeline run {batch_id}: {total_claims} claims processed",
        resource_type="batch",
        resource_id=batch_id,
        details={
            "batch_id": batch_id,
            "run_id": run_id,
            "medical_claims": len(med_claims),
            "pharmacy_claims": len(rx_claims),
            "rules_evaluated": rules_saved,
            "scores_generated": scores_saved,
            "cases_created": len(new_cases),
            "high_risk": high_count,
            "critical_risk": critical_count,
        },
    )

    # ── Prometheus metrics ───────────────────────────────────────────────
    pipeline_runs_total.labels(workspace=body.workspace_id or "default", status="completed").inc()
    pipeline_duration_seconds.observe(duration)
    pipeline_claims_processed.inc(total_claims)

    return PipelineRunResponse(
        batch_id=batch_id,
        medical_claims=len(med_claims),
        pharmacy_claims=len(rx_claims),
        total_claims=total_claims,
        rules_evaluated=rules_saved,
        scores_generated=scores_saved,
        cases_created=len(new_cases),
        high_risk=high_count,
        critical_risk=critical_count,
        processing_time_seconds=duration,
        quality_report=quality_report,
    )


# ── Async job queue endpoints ────────────────────────────────────────────────

@router.post("/enqueue", response_model=EnqueueResponse)
async def enqueue_pipeline(
    body: EnqueueRequest,
    ctx: RequestContext = Depends(require(Permission.PIPELINE_RUN)),
):
    """Enqueue a pipeline job for background processing. Returns immediately."""
    job_id = await enqueue_pipeline_job(
        workspace_id=body.workspace_id,
        limit=body.limit,
        batch_id=body.batch_id,
        force_reprocess=body.force_reprocess,
    )
    return EnqueueResponse(job_id=job_id, status="queued")


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_pipeline_job(
    job_id: str,
    ctx: RequestContext = Depends(require(Permission.PIPELINE_STATUS)),
):
    """Get the status of a background pipeline job."""
    data = await get_job_status(job_id)
    if data is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    result = None
    if data.get("result"):
        try:
            result = json.loads(data["result"])
        except (json.JSONDecodeError, TypeError):
            pass

    return JobStatusResponse(
        job_id=data.get("job_id", job_id),
        status=data.get("status", "unknown"),
        phase=data.get("phase", ""),
        progress=int(data.get("progress", 0)),
        claims_processed=int(data.get("claims_processed", 0)),
        errors=int(data.get("errors", 0)),
        started_at=data.get("started_at", ""),
        completed_at=data.get("completed_at", ""),
        result=result,
    )


# ── Pipeline run history endpoints ───────────────────────────────────────────

@router.get("/runs")
async def list_pipeline_runs(
    ctx: RequestContext = Depends(require(Permission.PIPELINE_STATUS)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List past pipeline runs with stats."""
    q = (
        select(PipelineRun)
        .order_by(PipelineRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(q)
    runs = list(result.scalars())

    total = (await db.execute(select(func.count()).select_from(PipelineRun))).scalar() or 0

    return {
        "total": total,
        "runs": [
            PipelineRunSummary(
                run_id=r.run_id,
                workspace_id=r.workspace_id,
                batch_id=r.batch_id,
                started_at=r.started_at.isoformat() if r.started_at else None,
                completed_at=r.completed_at.isoformat() if r.completed_at else None,
                status=r.status,
                duration_seconds=r.duration_seconds,
                stats=r.stats,
            ).model_dump()
            for r in runs
        ],
    }


@router.get("/runs/{run_id}")
async def get_pipeline_run(
    run_id: str,
    ctx: RequestContext = Depends(require(Permission.PIPELINE_STATUS)),
    db: AsyncSession = Depends(get_db),
):
    """Get detail for a specific pipeline run including config snapshot."""
    q = select(PipelineRun).where(PipelineRun.run_id == run_id)
    result = await db.execute(q)
    run = result.scalar_one_or_none()
    if not run:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")

    return PipelineRunDetail(
        run_id=run.run_id,
        workspace_id=run.workspace_id,
        batch_id=run.batch_id,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        status=run.status,
        duration_seconds=run.duration_seconds,
        stats=run.stats,
        config_snapshot=run.config_snapshot,
        quality_report=run.quality_report,
    ).model_dump()


@router.get("/status", response_model=PipelineStatusResponse)
async def pipeline_status(
    ctx: RequestContext = Depends(require(Permission.PIPELINE_STATUS)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current pipeline status: counts of claims, scores, cases, and audit entries.
    """
    med_count = (await db.execute(
        select(func.count()).select_from(MedicalClaim)
    )).scalar() or 0

    rx_count = (await db.execute(
        select(func.count()).select_from(PharmacyClaim)
    )).scalar() or 0

    scored_count = (await db.execute(
        select(func.count()).select_from(RiskScore)
    )).scalar() or 0

    total_cases = (await db.execute(
        select(func.count()).select_from(InvestigationCase)
    )).scalar() or 0

    open_cases = (await db.execute(
        select(func.count()).select_from(InvestigationCase).where(
            InvestigationCase.status.in_(["open", "under_review", "escalated"])
        )
    )).scalar() or 0

    total_rr = (await db.execute(
        select(func.count()).select_from(RuleResult)
    )).scalar() or 0

    from app.models import AuditLog
    total_audit = (await db.execute(
        select(func.count()).select_from(AuditLog)
    )).scalar() or 0

    return PipelineStatusResponse(
        total_medical_claims=med_count,
        total_pharmacy_claims=rx_count,
        scored_claims=scored_count,
        unscored_claims=(med_count + rx_count) - scored_count,
        total_cases=total_cases,
        open_cases=open_cases,
        total_rule_results=total_rr,
        total_audit_entries=total_audit,
    )


@router.post("/run-stream")
async def run_pipeline_stream(
    body: PipelineRunRequest,
    ctx: RequestContext = Depends(require(Permission.PIPELINE_RUN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Run the full pipeline with SSE progress streaming.
    Returns text/event-stream with progress updates.
    """

    async def generate():
        t_start = time.time()
        batch_id = body.batch_id or f"PIPE-{uuid4().hex[:12].upper()}"

        ws_id = None
        if body.workspace_id:
            ws_result = await db.execute(select(Workspace).where(Workspace.workspace_id == body.workspace_id))
            ws = ws_result.scalar_one_or_none()
            if ws:
                ws_id = ws.id

        def send_event(event_type: str, data: dict) -> str:
            return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        yield send_event("phase", {"phase": "loading", "label": "Loading claims", "progress": 0})

        if body.force_reprocess:
            med_q = select(MedicalClaim)
            rx_q = select(PharmacyClaim)
        else:
            scored_med_ids = select(RiskScore.claim_id).where(RiskScore.claim_type == "medical")
            scored_rx_ids = select(RiskScore.claim_id).where(RiskScore.claim_type == "pharmacy")
            med_q = select(MedicalClaim).where(MedicalClaim.claim_id.not_in(scored_med_ids))
            rx_q = select(PharmacyClaim).where(PharmacyClaim.claim_id.not_in(scored_rx_ids))

        if ws_id is not None:
            med_q = med_q.where(MedicalClaim.workspace_id == ws_id)
            rx_q = rx_q.where(PharmacyClaim.workspace_id == ws_id)

        med_q = med_q.order_by(MedicalClaim.created_at.asc()).limit(body.limit)
        rx_q = rx_q.order_by(PharmacyClaim.created_at.asc()).limit(body.limit)

        med_claims = list((await db.execute(med_q)).scalars())
        rx_claims = list((await db.execute(rx_q)).scalars())
        total_claims = len(med_claims) + len(rx_claims)

        yield send_event("progress", {
            "phase": "loading", "current": total_claims, "total": total_claims, "progress": 100,
            "detail": f"Found {len(med_claims)} medical + {len(rx_claims)} pharmacy claims"
        })

        if total_claims == 0:
            yield send_event("complete", {"total_claims": 0, "rules_evaluated": 0, "cases_created": 0, "elapsed_seconds": round(time.time() - t_start, 1)})
            return

        # Data quality
        yield send_event("phase", {"phase": "quality", "label": "Validating data quality", "progress": 0})
        dq = DataQualityService(db)
        med_quality = await dq.validate_medical_claims(med_claims)
        rx_quality = await dq.validate_pharmacy_claims(rx_claims)
        yield send_event("progress", {
            "phase": "quality", "current": total_claims, "total": total_claims, "progress": 100,
            "detail": f"Quality: {med_quality.passed + rx_quality.passed} passed, {med_quality.failed + rx_quality.failed} issues"
        })

        # Enrich
        yield send_event("phase", {"phase": "enrichment", "label": "Enriching claims with reference data", "progress": 0})
        enrichment = EnrichmentService(db)
        enriched_medical = await enrichment.enrich_medical_batch(med_claims) if med_claims else []
        yield send_event("progress", {"phase": "enrichment", "current": len(med_claims), "total": total_claims, "progress": 50, "detail": f"Enriched {len(med_claims)} medical claims"})
        enriched_pharmacy = await enrichment.enrich_pharmacy_batch(rx_claims) if rx_claims else []
        yield send_event("progress", {"phase": "enrichment", "current": total_claims, "total": total_claims, "progress": 100, "detail": f"Enriched all {total_claims} claims"})

        # Rules
        yield send_event("phase", {"phase": "rules", "label": "Evaluating 29 fraud detection rules", "progress": 0})
        rule_engine = RuleEngine(db)
        await rule_engine.load_rules()
        await rule_engine.load_configs()

        med_results = await rule_engine.evaluate_batch(enriched_medical, batch_id) if enriched_medical else {}
        med_triggered = sum(1 for results in med_results.values() for r in results if r.triggered)
        yield send_event("progress", {"phase": "rules", "current": len(med_claims), "total": total_claims, "progress": 50, "detail": f"Medical: {med_triggered} rules triggered"})

        rx_results = await rule_engine.evaluate_batch(enriched_pharmacy, batch_id) if enriched_pharmacy else {}
        rx_triggered = sum(1 for results in rx_results.values() for r in results if r.triggered)
        yield send_event("progress", {"phase": "rules", "current": total_claims, "total": total_claims, "progress": 100, "detail": f"Total: {med_triggered + rx_triggered} rules triggered"})

        rules_saved = await rule_engine.save_results(med_results) + await rule_engine.save_results(rx_results)

        claim_ws_map: dict[str, int | None] = {}
        for c in med_claims:
            claim_ws_map[c.claim_id] = ws_id if ws_id is not None else c.workspace_id
        for c in rx_claims:
            claim_ws_map[c.claim_id] = ws_id if ws_id is not None else c.workspace_id
        for rr_list in list(med_results.values()) + list(rx_results.values()):
            for rr in rr_list:
                rr.workspace_id = claim_ws_map.get(rr.claim_id)

        # Scoring
        yield send_event("phase", {"phase": "scoring", "label": "Calculating risk scores", "progress": 0})
        scoring = ScoringEngine(db)
        med_scores = await scoring.score_batch(med_results, "medical", batch_id) if med_results else []
        rx_scores = await scoring.score_batch(rx_results, "pharmacy", batch_id) if rx_results else []
        all_scores = med_scores + rx_scores
        for score in all_scores:
            score.workspace_id = claim_ws_map.get(score.claim_id)
        scores_saved = await scoring.save_scores(all_scores)

        high_count = sum(1 for s in all_scores if s.risk_level == "high")
        critical_count = sum(1 for s in all_scores if s.risk_level == "critical")
        yield send_event("progress", {"phase": "scoring", "current": len(all_scores), "total": len(all_scores), "progress": 100, "detail": f"High: {high_count}, Critical: {critical_count}"})

        for claim in med_claims + rx_claims:
            claim.status = "processed"
            claim.batch_id = batch_id
        await db.flush()

        # Cases
        yield send_event("phase", {"phase": "cases", "label": "Creating investigation cases", "progress": 0})
        case_manager = CaseManager(db)
        new_cases = await case_manager.create_cases_from_scores(all_scores, generate_evidence=True, workspace_id=ws_id, claim_ws_map=claim_ws_map)
        yield send_event("progress", {"phase": "cases", "current": len(new_cases), "total": len(new_cases), "progress": 100, "detail": f"Created {len(new_cases)} investigation cases"})

        audit = AuditService(db)
        await audit.log_event(
            event_type="pipeline_run",
            actor=ctx.actor,
            action=f"Streamed pipeline {batch_id}: {total_claims} claims",
            resource_type="batch",
            resource_id=batch_id,
            details={"batch_id": batch_id, "total_claims": total_claims, "rules_evaluated": rules_saved, "cases_created": len(new_cases)},
        )

        yield send_event("complete", {
            "batch_id": batch_id,
            "total_claims": total_claims,
            "medical_claims": len(med_claims),
            "pharmacy_claims": len(rx_claims),
            "rules_evaluated": rules_saved,
            "scores_generated": scores_saved,
            "cases_created": len(new_cases),
            "high_risk": high_count,
            "critical_risk": critical_count,
            "elapsed_seconds": round(time.time() - t_start, 1),
        })

    return StreamingResponse(generate(), media_type="text/event-stream")
