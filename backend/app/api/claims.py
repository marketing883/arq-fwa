"""
Claims API — list, detail, and batch-processing pipeline for ArqAI FWA Detection.
"""

import math
import time
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from app.services.audit_service import AuditService
from app.schemas.schemas import (
    ClaimListResponse,
    ClaimSummary,
    ClaimDetail,
    RuleResultDetail,
    RiskScoreDetail,
    ProcessBatchRequest,
    ProcessBatchResponse,
)

router = APIRouter(prefix="/api/claims", tags=["claims"])


# ---------------------------------------------------------------------------
# GET /api/claims — paginated list with filters
# ---------------------------------------------------------------------------

@router.get("", response_model=ClaimListResponse)
async def list_claims(
    type: str | None = Query(None, pattern="^(medical|pharmacy)$"),
    status: str | None = Query(None),
    risk_level: str | None = Query(None, pattern="^(low|medium|high|critical)$"),
    workspace_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> ClaimListResponse:
    """Return a paginated, filterable list of claims with risk information."""

    # Resolve optional workspace_id to internal integer id
    ws_id = None
    if workspace_id:
        ws_result = await db.execute(select(Workspace).where(Workspace.workspace_id == workspace_id))
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws_id = ws.id

    offset = (page - 1) * size
    items: list[ClaimSummary] = []
    total = 0

    # Determine which claim types to query
    query_medical = type is None or type == "medical"
    query_pharmacy = type is None or type == "pharmacy"

    # ── Medical claims ──────────────────────────────────────────────────
    if query_medical:
        med_query = (
            select(
                MedicalClaim.id,
                MedicalClaim.claim_id,
                MedicalClaim.member_id,
                MedicalClaim.provider_id,
                MedicalClaim.service_date,
                MedicalClaim.amount_billed,
                MedicalClaim.amount_paid,
                MedicalClaim.status,
                MedicalClaim.batch_id,
                MedicalClaim.created_at,
                RiskScore.total_score.label("risk_score"),
                RiskScore.risk_level.label("risk_level"),
                RiskScore.rules_triggered.label("rules_triggered"),
            )
            .outerjoin(RiskScore, RiskScore.claim_id == MedicalClaim.claim_id)
        )

        if ws_id is not None:
            med_query = med_query.where(MedicalClaim.workspace_id == ws_id)
        if status:
            med_query = med_query.where(MedicalClaim.status == status)
        if risk_level:
            med_query = med_query.where(RiskScore.risk_level == risk_level)

        # Count for medical
        med_count_q = select(func.count()).select_from(
            med_query.subquery()
        )
        med_count = (await db.execute(med_count_q)).scalar() or 0
        total += med_count

    # ── Pharmacy claims ─────────────────────────────────────────────────
    if query_pharmacy:
        rx_query = (
            select(
                PharmacyClaim.id,
                PharmacyClaim.claim_id,
                PharmacyClaim.member_id,
                PharmacyClaim.pharmacy_id,
                PharmacyClaim.fill_date,
                PharmacyClaim.amount_billed,
                PharmacyClaim.amount_paid,
                PharmacyClaim.status,
                PharmacyClaim.batch_id,
                PharmacyClaim.created_at,
                RiskScore.total_score.label("risk_score"),
                RiskScore.risk_level.label("risk_level"),
                RiskScore.rules_triggered.label("rules_triggered"),
            )
            .outerjoin(RiskScore, RiskScore.claim_id == PharmacyClaim.claim_id)
        )

        if ws_id is not None:
            rx_query = rx_query.where(PharmacyClaim.workspace_id == ws_id)
        if status:
            rx_query = rx_query.where(PharmacyClaim.status == status)
        if risk_level:
            rx_query = rx_query.where(RiskScore.risk_level == risk_level)

        rx_count_q = select(func.count()).select_from(
            rx_query.subquery()
        )
        rx_count = (await db.execute(rx_count_q)).scalar() or 0
        total += rx_count

    # ── Fetch paginated rows ────────────────────────────────────────────
    # When querying both types we interleave by created_at descending.
    # We pull rows from both result sets and merge.

    if query_medical and (not query_pharmacy or type == "medical"):
        # Medical only
        med_query = med_query.order_by(MedicalClaim.created_at.desc()).offset(offset).limit(size)
        rows = (await db.execute(med_query)).all()
        for r in rows:
            items.append(ClaimSummary(
                id=r.id,
                claim_id=r.claim_id,
                claim_type="medical",
                member_id=r.member_id,
                provider_id=r.provider_id,
                service_date=r.service_date,
                amount_billed=float(r.amount_billed),
                amount_paid=float(r.amount_paid) if r.amount_paid else None,
                status=r.status,
                risk_score=float(r.risk_score) if r.risk_score is not None else None,
                risk_level=r.risk_level,
                rules_triggered=r.rules_triggered or 0,
                batch_id=r.batch_id,
                created_at=r.created_at,
            ))

    elif query_pharmacy and not query_medical:
        # Pharmacy only
        rx_query = rx_query.order_by(PharmacyClaim.created_at.desc()).offset(offset).limit(size)
        rows = (await db.execute(rx_query)).all()
        for r in rows:
            items.append(ClaimSummary(
                id=r.id,
                claim_id=r.claim_id,
                claim_type="pharmacy",
                member_id=r.member_id,
                pharmacy_id=r.pharmacy_id,
                fill_date=r.fill_date,
                amount_billed=float(r.amount_billed),
                amount_paid=float(r.amount_paid) if r.amount_paid else None,
                status=r.status,
                risk_score=float(r.risk_score) if r.risk_score is not None else None,
                risk_level=r.risk_level,
                rules_triggered=r.rules_triggered or 0,
                batch_id=r.batch_id,
                created_at=r.created_at,
            ))

    else:
        # Both types — fetch half-page from each, merge, sort, trim to page size
        half = size
        med_query = med_query.order_by(MedicalClaim.created_at.desc()).offset(offset).limit(half)
        rx_query = rx_query.order_by(PharmacyClaim.created_at.desc()).offset(offset).limit(half)

        med_rows = (await db.execute(med_query)).all()
        rx_rows = (await db.execute(rx_query)).all()

        for r in med_rows:
            items.append(ClaimSummary(
                id=r.id,
                claim_id=r.claim_id,
                claim_type="medical",
                member_id=r.member_id,
                provider_id=r.provider_id,
                service_date=r.service_date,
                amount_billed=float(r.amount_billed),
                amount_paid=float(r.amount_paid) if r.amount_paid else None,
                status=r.status,
                risk_score=float(r.risk_score) if r.risk_score is not None else None,
                risk_level=r.risk_level,
                rules_triggered=r.rules_triggered or 0,
                batch_id=r.batch_id,
                created_at=r.created_at,
            ))

        for r in rx_rows:
            items.append(ClaimSummary(
                id=r.id,
                claim_id=r.claim_id,
                claim_type="pharmacy",
                member_id=r.member_id,
                pharmacy_id=r.pharmacy_id,
                fill_date=r.fill_date,
                amount_billed=float(r.amount_billed),
                amount_paid=float(r.amount_paid) if r.amount_paid else None,
                status=r.status,
                risk_score=float(r.risk_score) if r.risk_score is not None else None,
                risk_level=r.risk_level,
                rules_triggered=r.rules_triggered or 0,
                batch_id=r.batch_id,
                created_at=r.created_at,
            ))

        # Sort merged list by created_at descending and trim
        items.sort(key=lambda c: c.created_at or datetime.min, reverse=True)
        items = items[:size]

    pages = math.ceil(total / size) if total > 0 else 1

    return ClaimListResponse(
        total=total,
        page=page,
        size=size,
        pages=pages,
        items=items,
    )


# ---------------------------------------------------------------------------
# GET /api/claims/{claim_id} — full detail
# ---------------------------------------------------------------------------

@router.get("/{claim_id}", response_model=ClaimDetail)
async def get_claim_detail(
    claim_id: str,
    db: AsyncSession = Depends(get_db),
) -> ClaimDetail:
    """Return complete claim detail including rule results and risk score."""

    # Try medical first (eager-load relationships to avoid async lazy-loading)
    med_q = await db.execute(
        select(MedicalClaim)
        .where(MedicalClaim.claim_id == claim_id)
        .options(
            selectinload(MedicalClaim.provider),
            selectinload(MedicalClaim.member),
        )
    )
    med_claim = med_q.scalar_one_or_none()

    rx_claim = None
    if med_claim is None:
        rx_q = await db.execute(
            select(PharmacyClaim)
            .where(PharmacyClaim.claim_id == claim_id)
            .options(
                selectinload(PharmacyClaim.prescriber),
                selectinload(PharmacyClaim.member),
            )
        )
        rx_claim = rx_q.scalar_one_or_none()

    if med_claim is None and rx_claim is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    # Fetch rule results
    rr_q = await db.execute(
        select(RuleResult).where(RuleResult.claim_id == claim_id)
    )
    rule_results_rows = list(rr_q.scalars())

    rule_results = [
        RuleResultDetail(
            rule_id=rr.rule_id,
            triggered=rr.triggered,
            severity=float(rr.severity) if rr.severity is not None else None,
            confidence=float(rr.confidence) if rr.confidence is not None else None,
            evidence=rr.evidence or {},
            details=rr.details,
        )
        for rr in rule_results_rows
    ]

    # Fetch risk score
    rs_q = await db.execute(
        select(RiskScore).where(RiskScore.claim_id == claim_id)
    )
    rs = rs_q.scalar_one_or_none()

    risk_score_detail = None
    if rs:
        risk_score_detail = RiskScoreDetail(
            total_score=float(rs.total_score),
            risk_level=rs.risk_level,
            rules_triggered=rs.rules_triggered,
            rule_contributions=rs.rule_contributions or {},
            confidence_factor=float(rs.confidence_factor),
        )

    # Build response based on claim type
    if med_claim is not None:
        # Resolve provider name/npi if possible
        provider_name = None
        provider_npi = None
        if med_claim.provider:
            provider_name = med_claim.provider.name
            provider_npi = med_claim.provider.npi

        # Resolve member_member_id if possible
        member_member_id = None
        if med_claim.member:
            member_member_id = med_claim.member.member_id

        return ClaimDetail(
            id=med_claim.id,
            claim_id=med_claim.claim_id,
            claim_type="medical",
            member_id=med_claim.member_id,
            amount_billed=float(med_claim.amount_billed),
            amount_allowed=float(med_claim.amount_allowed) if med_claim.amount_allowed else None,
            amount_paid=float(med_claim.amount_paid) if med_claim.amount_paid else None,
            status=med_claim.status,
            batch_id=med_claim.batch_id,
            provider_id=med_claim.provider_id,
            service_date=med_claim.service_date,
            cpt_code=med_claim.cpt_code,
            cpt_modifier=med_claim.cpt_modifier,
            diagnosis_code_primary=med_claim.diagnosis_code_primary,
            place_of_service=med_claim.place_of_service,
            provider_name=provider_name,
            provider_npi=provider_npi,
            member_member_id=member_member_id,
            rule_results=rule_results,
            risk_score=risk_score_detail,
            created_at=med_claim.created_at,
        )
    else:
        # Pharmacy claim
        # Resolve provider (prescriber) name/npi
        provider_name = None
        provider_npi = None
        if rx_claim.prescriber:
            provider_name = rx_claim.prescriber.name
            provider_npi = rx_claim.prescriber.npi

        member_member_id = None
        if rx_claim.member:
            member_member_id = rx_claim.member.member_id

        return ClaimDetail(
            id=rx_claim.id,
            claim_id=rx_claim.claim_id,
            claim_type="pharmacy",
            member_id=rx_claim.member_id,
            amount_billed=float(rx_claim.amount_billed),
            amount_allowed=float(rx_claim.amount_allowed) if rx_claim.amount_allowed else None,
            amount_paid=float(rx_claim.amount_paid) if rx_claim.amount_paid else None,
            status=rx_claim.status,
            batch_id=rx_claim.batch_id,
            pharmacy_id=rx_claim.pharmacy_id,
            prescriber_id=rx_claim.prescriber_id,
            fill_date=rx_claim.fill_date,
            ndc_code=rx_claim.ndc_code,
            drug_name=rx_claim.drug_name,
            days_supply=rx_claim.days_supply,
            is_controlled=rx_claim.is_controlled,
            provider_name=provider_name,
            provider_npi=provider_npi,
            member_member_id=member_member_id,
            rule_results=rule_results,
            risk_score=risk_score_detail,
            created_at=rx_claim.created_at,
        )


# ---------------------------------------------------------------------------
# GET /api/claims/{claim_id}/rule-trace — step-by-step rule evaluation trace
# ---------------------------------------------------------------------------

@router.get("/{claim_id}/rule-trace")
async def get_rule_trace(claim_id: str, db: AsyncSession = Depends(get_db)):
    """Return step-by-step rule evaluation trace with human-readable explanations."""
    from app.services.rule_trace import RuleTraceService
    service = RuleTraceService(db)
    result = await service.get_trace(claim_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No rule results found for claim {claim_id}")
    return result


# ---------------------------------------------------------------------------
# GET /api/claims/{claim_id}/confidence — pattern confidence scores
# ---------------------------------------------------------------------------

@router.get("/{claim_id}/confidence")
async def get_pattern_confidence(claim_id: str, db: AsyncSession = Depends(get_db)):
    """Return pattern confidence scores based on historical case outcomes."""
    from app.services.pattern_confidence import PatternConfidenceService
    service = PatternConfidenceService(db)
    result = await service.compute_for_claim(claim_id)
    return result


# ---------------------------------------------------------------------------
# POST /api/claims/process-batch — full pipeline
# ---------------------------------------------------------------------------

@router.post("/process-batch", response_model=ProcessBatchResponse)
async def process_batch(
    body: ProcessBatchRequest,
    db: AsyncSession = Depends(get_db),
) -> ProcessBatchResponse:
    """
    Run the full FWA detection pipeline on a batch of claims:
    1. Load claims (by batch_id or latest unprocessed, up to limit)
    2. Enrich claims with reference/context data
    3. Evaluate all enabled rules
    4. Calculate risk scores
    5. Persist results
    6. Auto-create investigation cases for high/critical risk
    7. Log audit trail entries
    """

    t_start = time.time()

    # ── 1. Load claims ──────────────────────────────────────────────────
    med_claims: list[MedicalClaim] = []
    rx_claims: list[PharmacyClaim] = []

    process_medical = body.claim_type is None or body.claim_type == "medical"
    process_pharmacy = body.claim_type is None or body.claim_type == "pharmacy"

    if process_medical:
        med_q = select(MedicalClaim)
        if body.batch_id:
            med_q = med_q.where(MedicalClaim.batch_id == body.batch_id)
        else:
            # Claims not yet scored (no entry in risk_scores)
            scored_ids = select(RiskScore.claim_id).where(RiskScore.claim_type == "medical")
            med_q = med_q.where(MedicalClaim.claim_id.not_in(scored_ids))
        med_q = med_q.order_by(MedicalClaim.created_at.asc()).limit(body.limit)
        result = await db.execute(med_q)
        med_claims = list(result.scalars())

    if process_pharmacy:
        rx_q = select(PharmacyClaim)
        if body.batch_id:
            rx_q = rx_q.where(PharmacyClaim.batch_id == body.batch_id)
        else:
            scored_ids = select(RiskScore.claim_id).where(RiskScore.claim_type == "pharmacy")
            rx_q = rx_q.where(PharmacyClaim.claim_id.not_in(scored_ids))
        rx_q = rx_q.order_by(PharmacyClaim.created_at.asc()).limit(body.limit)
        result = await db.execute(rx_q)
        rx_claims = list(result.scalars())

    total_claims = len(med_claims) + len(rx_claims)
    if total_claims == 0:
        raise HTTPException(status_code=404, detail="No claims found to process")

    # Determine batch_id for tracking
    batch_id = body.batch_id or f"BATCH-{uuid4().hex[:12].upper()}"

    # ── 2. Enrich ───────────────────────────────────────────────────────
    enrichment = EnrichmentService(db)
    enriched_medical = await enrichment.enrich_medical_batch(med_claims) if med_claims else []
    enriched_pharmacy = await enrichment.enrich_pharmacy_batch(rx_claims) if rx_claims else []

    # ── 3. Rule engine ──────────────────────────────────────────────────
    rule_engine = RuleEngine(db)
    await rule_engine.load_rules()
    await rule_engine.load_configs()

    med_results = await rule_engine.evaluate_batch(enriched_medical, batch_id) if enriched_medical else {}
    rx_results = await rule_engine.evaluate_batch(enriched_pharmacy, batch_id) if enriched_pharmacy else {}

    # Save rule results
    rules_saved = 0
    rules_saved += await rule_engine.save_results(med_results)
    rules_saved += await rule_engine.save_results(rx_results)

    # ── 4. Score ────────────────────────────────────────────────────────
    scoring = ScoringEngine(db)
    med_scores = await scoring.score_batch(med_results, "medical", batch_id) if med_results else []
    rx_scores = await scoring.score_batch(rx_results, "pharmacy", batch_id) if rx_results else []

    all_scores = med_scores + rx_scores
    scores_saved = await scoring.save_scores(all_scores)

    # ── 5. Update claim statuses ────────────────────────────────────────
    for claim in med_claims:
        claim.status = "processed"
        claim.batch_id = batch_id
    for claim in rx_claims:
        claim.status = "processed"
        claim.batch_id = batch_id

    await db.flush()

    # ── 6. Auto-create investigation cases for high/critical ────────────
    from app.services.case_manager import CaseManager
    case_manager = CaseManager(db)
    new_cases = await case_manager.create_cases_from_scores(
        all_scores, generate_evidence=True
    )
    cases_created = len(new_cases)

    # ── 7. Audit: batch processing event ────────────────────────────────
    audit = AuditService(db)
    await audit.log_event(
        event_type="batch_processed",
        actor="system",
        action=f"Processed batch {batch_id}: {total_claims} claims, {cases_created} cases created",
        resource_type="batch",
        resource_id=batch_id,
        details={
            "batch_id": batch_id,
            "claims_processed": total_claims,
            "rules_evaluated": rules_saved,
            "scores_generated": scores_saved,
            "cases_created": cases_created,
        },
    )

    t_end = time.time()

    return ProcessBatchResponse(
        batch_id=batch_id,
        claims_processed=total_claims,
        rules_evaluated=rules_saved,
        scores_generated=scores_saved,
        cases_created=cases_created,
        processing_time_seconds=round(t_end - t_start, 3),
    )
