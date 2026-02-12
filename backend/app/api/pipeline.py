"""
Pipeline API — Full end-to-end FWA detection pipeline.

POST /api/pipeline/run-full
  Runs the complete pipeline: load → enrich → evaluate → score → create cases → audit
"""

import json
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models import (
    MedicalClaim,
    PharmacyClaim,
    RiskScore,
    RuleResult,
    InvestigationCase,
    Workspace,
)
from app.services.enrichment import EnrichmentService
from app.services.rule_engine import RuleEngine
from app.services.scoring_engine import ScoringEngine
from app.services.case_manager import CaseManager
from app.services.audit_service import AuditService
from pydantic import BaseModel, Field


class PipelineRunRequest(BaseModel):
    limit: int = Field(1000, ge=1, le=50000, description="Max claims per type to process")
    batch_id: str | None = Field(None, description="Process specific batch only")
    workspace_id: str | None = Field(None, description="Filter claims by workspace")


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


class PipelineStatusResponse(BaseModel):
    total_medical_claims: int
    total_pharmacy_claims: int
    scored_claims: int
    unscored_claims: int
    total_cases: int
    open_cases: int
    total_rule_results: int
    total_audit_entries: int


router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/run-full", response_model=PipelineRunResponse)
async def run_full_pipeline(
    body: PipelineRunRequest,
    db: AsyncSession = Depends(get_db),
) -> PipelineRunResponse:
    """
    Run the full FWA detection pipeline end-to-end:

    1. Load unscored claims (medical + pharmacy)
    2. Enrich with reference data and historical context
    3. Evaluate all 29 enabled rules
    4. Calculate risk scores
    5. Auto-create investigation cases for high/critical risk
    6. Generate evidence bundles for new cases
    7. Log all actions to audit trail
    """

    t_start = time.time()
    batch_id = body.batch_id or f"PIPE-{uuid4().hex[:12].upper()}"

    # Resolve optional workspace_id to internal integer id
    ws_id = None
    if body.workspace_id:
        ws_result = await db.execute(select(Workspace).where(Workspace.workspace_id == body.workspace_id))
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws_id = ws.id

    # ── 1. Load unscored claims ──────────────────────────────────────────
    scored_med_ids = select(RiskScore.claim_id).where(RiskScore.claim_type == "medical")
    scored_rx_ids = select(RiskScore.claim_id).where(RiskScore.claim_type == "pharmacy")

    med_q = (
        select(MedicalClaim)
        .where(MedicalClaim.claim_id.not_in(scored_med_ids))
    )
    if ws_id is not None:
        med_q = med_q.where(MedicalClaim.workspace_id == ws_id)
    med_q = med_q.order_by(MedicalClaim.created_at.asc()).limit(body.limit)

    rx_q = (
        select(PharmacyClaim)
        .where(PharmacyClaim.claim_id.not_in(scored_rx_ids))
    )
    if ws_id is not None:
        rx_q = rx_q.where(PharmacyClaim.workspace_id == ws_id)
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

    # ── 2. Enrich ────────────────────────────────────────────────────────
    enrichment = EnrichmentService(db)
    enriched_medical = await enrichment.enrich_medical_batch(med_claims) if med_claims else []
    enriched_pharmacy = await enrichment.enrich_pharmacy_batch(rx_claims) if rx_claims else []

    # ── 3. Rule engine ───────────────────────────────────────────────────
    rule_engine = RuleEngine(db)
    await rule_engine.load_rules()
    await rule_engine.load_configs()

    med_results = await rule_engine.evaluate_batch(enriched_medical, batch_id) if enriched_medical else {}
    rx_results = await rule_engine.evaluate_batch(enriched_pharmacy, batch_id) if enriched_pharmacy else {}

    rules_saved = 0
    rules_saved += await rule_engine.save_results(med_results)
    rules_saved += await rule_engine.save_results(rx_results)

    # ── 4. Score ─────────────────────────────────────────────────────────
    scoring = ScoringEngine(db)
    med_scores = await scoring.score_batch(med_results, "medical", batch_id) if med_results else []
    rx_scores = await scoring.score_batch(rx_results, "pharmacy", batch_id) if rx_results else []

    all_scores = med_scores + rx_scores
    scores_saved = await scoring.save_scores(all_scores)

    # ── 5. Update claim statuses ─────────────────────────────────────────
    for claim in med_claims:
        claim.status = "processed"
        claim.batch_id = batch_id
    for claim in rx_claims:
        claim.status = "processed"
        claim.batch_id = batch_id

    await db.flush()

    # ── 6. Auto-create cases with evidence bundles ───────────────────────
    case_manager = CaseManager(db)
    new_cases = await case_manager.create_cases_from_scores(
        all_scores, generate_evidence=True
    )

    # Count risk levels
    high_count = sum(1 for s in all_scores if s.risk_level == "high")
    critical_count = sum(1 for s in all_scores if s.risk_level == "critical")

    # ── 7. Audit: pipeline run event ─────────────────────────────────────
    audit = AuditService(db)
    await audit.log_event(
        event_type="pipeline_run",
        actor="system",
        action=f"Full pipeline run {batch_id}: {total_claims} claims processed",
        resource_type="batch",
        resource_id=batch_id,
        details={
            "batch_id": batch_id,
            "medical_claims": len(med_claims),
            "pharmacy_claims": len(rx_claims),
            "rules_evaluated": rules_saved,
            "scores_generated": scores_saved,
            "cases_created": len(new_cases),
            "high_risk": high_count,
            "critical_risk": critical_count,
        },
    )

    t_end = time.time()

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
        processing_time_seconds=round(t_end - t_start, 3),
    )


@router.get("/status", response_model=PipelineStatusResponse)
async def pipeline_status(db: AsyncSession = Depends(get_db)):
    """
    Get current pipeline status: counts of claims, scores, cases, and audit entries.
    Useful for monitoring and verifying pipeline runs.
    """
    # Claims
    med_count = (await db.execute(
        select(func.count()).select_from(MedicalClaim)
    )).scalar() or 0

    rx_count = (await db.execute(
        select(func.count()).select_from(PharmacyClaim)
    )).scalar() or 0

    scored_count = (await db.execute(
        select(func.count()).select_from(RiskScore)
    )).scalar() or 0

    # Cases
    total_cases = (await db.execute(
        select(func.count()).select_from(InvestigationCase)
    )).scalar() or 0

    open_cases = (await db.execute(
        select(func.count()).select_from(InvestigationCase).where(
            InvestigationCase.status.in_(["open", "under_review", "escalated"])
        )
    )).scalar() or 0

    # Rules
    total_rr = (await db.execute(
        select(func.count()).select_from(RuleResult)
    )).scalar() or 0

    # Audit
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
    db: AsyncSession = Depends(get_db),
):
    """
    Run the full pipeline with SSE progress streaming.
    Returns text/event-stream with progress updates.
    """

    async def generate():
        t_start = time.time()
        batch_id = body.batch_id or f"PIPE-{uuid4().hex[:12].upper()}"

        def send_event(event_type: str, data: dict) -> str:
            return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        # Phase 1: Load claims
        yield send_event("phase", {"phase": "loading", "label": "Loading claims", "progress": 0})

        scored_med_ids = select(RiskScore.claim_id).where(RiskScore.claim_type == "medical")
        scored_rx_ids = select(RiskScore.claim_id).where(RiskScore.claim_type == "pharmacy")

        med_q = (
            select(MedicalClaim)
            .where(MedicalClaim.claim_id.not_in(scored_med_ids))
            .order_by(MedicalClaim.created_at.asc())
            .limit(body.limit)
        )
        rx_q = (
            select(PharmacyClaim)
            .where(PharmacyClaim.claim_id.not_in(scored_rx_ids))
            .order_by(PharmacyClaim.created_at.asc())
            .limit(body.limit)
        )

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

        # Phase 2: Enrich
        yield send_event("phase", {"phase": "enrichment", "label": "Enriching claims with reference data", "progress": 0})
        enrichment = EnrichmentService(db)
        enriched_medical = await enrichment.enrich_medical_batch(med_claims) if med_claims else []
        yield send_event("progress", {"phase": "enrichment", "current": len(med_claims), "total": total_claims, "progress": 50, "detail": f"Enriched {len(med_claims)} medical claims"})
        enriched_pharmacy = await enrichment.enrich_pharmacy_batch(rx_claims) if rx_claims else []
        yield send_event("progress", {"phase": "enrichment", "current": total_claims, "total": total_claims, "progress": 100, "detail": f"Enriched all {total_claims} claims"})

        # Phase 3: Rule evaluation
        yield send_event("phase", {"phase": "rules", "label": "Evaluating 29 fraud detection rules", "progress": 0})
        rule_engine = RuleEngine(db)
        await rule_engine.load_rules()
        await rule_engine.load_configs()

        med_results = await rule_engine.evaluate_batch(enriched_medical, batch_id) if enriched_medical else {}
        med_triggered = sum(1 for results in med_results.values() for r in results if r.triggered)
        yield send_event("progress", {"phase": "rules", "current": len(med_claims), "total": total_claims, "progress": 50, "detail": f"Medical: {med_triggered} rules triggered across {len(med_claims)} claims"})

        rx_results = await rule_engine.evaluate_batch(enriched_pharmacy, batch_id) if enriched_pharmacy else {}
        rx_triggered = sum(1 for results in rx_results.values() for r in results if r.triggered)
        total_triggered = med_triggered + rx_triggered
        yield send_event("progress", {"phase": "rules", "current": total_claims, "total": total_claims, "progress": 100, "detail": f"Total: {total_triggered} rules triggered"})

        rules_saved = await rule_engine.save_results(med_results) + await rule_engine.save_results(rx_results)

        # Phase 4: Scoring
        yield send_event("phase", {"phase": "scoring", "label": "Calculating risk scores", "progress": 0})
        scoring = ScoringEngine(db)
        med_scores = await scoring.score_batch(med_results, "medical", batch_id) if med_results else []
        rx_scores = await scoring.score_batch(rx_results, "pharmacy", batch_id) if rx_results else []
        all_scores = med_scores + rx_scores
        scores_saved = await scoring.save_scores(all_scores)

        high_count = sum(1 for s in all_scores if s.risk_level == "high")
        critical_count = sum(1 for s in all_scores if s.risk_level == "critical")
        yield send_event("progress", {"phase": "scoring", "current": len(all_scores), "total": len(all_scores), "progress": 100, "detail": f"High: {high_count}, Critical: {critical_count}"})

        # Update claim statuses
        for claim in med_claims:
            claim.status = "processed"
            claim.batch_id = batch_id
        for claim in rx_claims:
            claim.status = "processed"
            claim.batch_id = batch_id
        await db.flush()

        # Phase 5: Case creation
        yield send_event("phase", {"phase": "cases", "label": "Creating investigation cases", "progress": 0})
        case_manager = CaseManager(db)
        new_cases = await case_manager.create_cases_from_scores(all_scores, generate_evidence=True)
        yield send_event("progress", {"phase": "cases", "current": len(new_cases), "total": len(new_cases), "progress": 100, "detail": f"Created {len(new_cases)} investigation cases"})

        # Audit
        audit = AuditService(db)
        await audit.log_event(
            event_type="pipeline_run",
            actor="system",
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
