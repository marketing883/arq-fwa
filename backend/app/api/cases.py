"""
Cases API — ArqAI FWA Detection

Investigation case management: queue, detail, status transitions,
assignment, notes, and evidence bundles.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, require
from app.auth.permissions import Permission
from app.auth.context import RequestContext
from app.models import (
    InvestigationCase,
    CaseNote,
    CaseEvidence,
    MedicalClaim,
    PharmacyClaim,
    RiskScore,
    RuleResult,
    Workspace,
)
from app.services.audit_service import AuditService
from app.schemas.schemas import (
    CaseListResponse,
    CaseSummary,
    CaseDetail,
    CaseStatusUpdate,
    CaseAssign,
    CaseNoteCreate,
    CaseNoteSchema,
    CaseEvidenceSchema,
    RuleResultDetail,
    ClaimSummary,
)

router = APIRouter(prefix="/api/cases", tags=["cases"])

# Valid status transitions: current_status -> set of allowed next statuses
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"under_review", "escalated"},
    "under_review": {"resolved", "escalated", "open"},
    "escalated": {"under_review", "resolved"},
    "resolved": {"closed", "under_review"},
    "closed": set(),  # terminal state
}


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_case_or_404(
    case_id: str,
    db: AsyncSession,
    *,
    load_relations: bool = False,
) -> InvestigationCase:
    """Fetch a case by its public case_id, raising 404 if missing."""
    query = select(InvestigationCase).where(InvestigationCase.case_id == case_id)
    if load_relations:
        query = query.options(
            selectinload(InvestigationCase.notes),
            selectinload(InvestigationCase.evidence),
        )
    result = await db.execute(query)
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return case


async def _build_claim_summary(
    claim_id: str,
    claim_type: str,
    db: AsyncSession,
) -> ClaimSummary | None:
    """Load the claim record as a ClaimSummary, returning None if missing."""
    if claim_type == "medical":
        result = await db.execute(
            select(MedicalClaim).where(MedicalClaim.claim_id == claim_id)
        )
        claim = result.scalar_one_or_none()
        if not claim:
            return None
        return ClaimSummary(
            id=claim.id,
            claim_id=claim.claim_id,
            claim_type="medical",
            member_id=claim.member_id,
            provider_id=claim.provider_id,
            service_date=claim.service_date,
            amount_billed=float(claim.amount_billed),
            amount_paid=float(claim.amount_paid) if claim.amount_paid is not None else None,
            status=claim.status,
            batch_id=claim.batch_id,
            created_at=claim.created_at,
        )
    else:
        result = await db.execute(
            select(PharmacyClaim).where(PharmacyClaim.claim_id == claim_id)
        )
        claim = result.scalar_one_or_none()
        if not claim:
            return None
        return ClaimSummary(
            id=claim.id,
            claim_id=claim.claim_id,
            claim_type="pharmacy",
            member_id=claim.member_id,
            pharmacy_id=claim.pharmacy_id,
            fill_date=claim.fill_date,
            amount_billed=float(claim.amount_billed),
            amount_paid=float(claim.amount_paid) if claim.amount_paid is not None else None,
            status=claim.status,
            batch_id=claim.batch_id,
            created_at=claim.created_at,
        )


# ── GET /api/cases — investigation queue ─────────────────────────────────────

@router.get("", response_model=CaseListResponse)
async def list_cases(
    status: str | None = Query(None, pattern="^(open|under_review|escalated|resolved|closed)$"),
    priority: str | None = Query(None, pattern="^(P1|P2|P3|P4)$"),
    assigned_to: str | None = Query(None),
    workspace_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    ctx: RequestContext = Depends(require(Permission.CASES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    Paginated investigation queue with optional filters.
    Sorted by priority (P1 first), then by creation date descending.
    """
    # Resolve optional workspace_id to internal integer id
    ws_id = None
    if workspace_id:
        ws_result = await db.execute(select(Workspace).where(Workspace.workspace_id == workspace_id))
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws_id = ws.id

    # Base filter conditions
    conditions = []
    if ws_id is not None:
        conditions.append(InvestigationCase.workspace_id == ws_id)
    if status is not None:
        conditions.append(InvestigationCase.status == status)
    if priority is not None:
        conditions.append(InvestigationCase.priority == priority)
    if assigned_to is not None:
        conditions.append(InvestigationCase.assigned_to == assigned_to)

    where_clause = and_(*conditions) if conditions else True

    # Total count
    count_result = await db.execute(
        select(func.count())
        .select_from(InvestigationCase)
        .where(where_clause)
    )
    total = count_result.scalar() or 0

    # Paginated rows sorted by priority asc (P1 < P2 < …), created_at desc
    offset = (page - 1) * size
    rows_result = await db.execute(
        select(InvestigationCase)
        .where(where_clause)
        .order_by(InvestigationCase.priority.asc(), InvestigationCase.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    cases = list(rows_result.scalars().all())

    items = [
        CaseSummary(
            id=c.id,
            case_id=c.case_id,
            claim_id=c.claim_id,
            claim_type=c.claim_type,
            risk_level=c.risk_level,
            risk_score=float(c.risk_score),
            status=c.status,
            priority=c.priority,
            assigned_to=c.assigned_to,
            sla_deadline=c.sla_deadline,
            created_at=c.created_at,
        )
        for c in cases
    ]

    pages = (total + size - 1) // size if total > 0 else 0
    return CaseListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


# ── GET /api/cases/{case_id} — full case detail ─────────────────────────────

@router.get("/{case_id}", response_model=CaseDetail)
async def get_case(case_id: str, ctx: RequestContext = Depends(require(Permission.CASES_READ)), db: AsyncSession = Depends(get_db)):
    """
    Full case detail including claim data, rule results, score,
    evidence items, and investigation notes.
    """
    case = await _get_case_or_404(case_id, db, load_relations=True)

    # Load associated claim
    claim_summary = await _build_claim_summary(case.claim_id, case.claim_type, db)

    # Load risk score
    score_result = await db.execute(
        select(RiskScore).where(RiskScore.claim_id == case.claim_id)
    )
    risk_score = score_result.scalar_one_or_none()

    # Load rule results
    rr_result = await db.execute(
        select(RuleResult)
        .where(RuleResult.claim_id == case.claim_id)
        .order_by(RuleResult.rule_id)
    )
    rule_results = list(rr_result.scalars().all())

    # If a risk score exists, enrich the claim summary
    if claim_summary and risk_score:
        claim_summary.risk_score = float(risk_score.total_score)
        claim_summary.risk_level = risk_score.risk_level
        claim_summary.rules_triggered = risk_score.rules_triggered

    return CaseDetail(
        id=case.id,
        case_id=case.case_id,
        claim_id=case.claim_id,
        claim_type=case.claim_type,
        risk_level=case.risk_level,
        risk_score=float(case.risk_score),
        status=case.status,
        priority=case.priority,
        assigned_to=case.assigned_to,
        resolution_path=case.resolution_path,
        resolution_notes=case.resolution_notes,
        sla_deadline=case.sla_deadline,
        created_at=case.created_at,
        updated_at=case.closed_at,  # closest available timestamp
        notes=[
            CaseNoteSchema(
                id=n.id,
                content=n.content,
                author=n.author,
                created_at=n.created_at,
            )
            for n in case.notes
        ],
        evidence=[
            CaseEvidenceSchema(
                id=e.id,
                evidence_type=e.evidence_type,
                title=e.title,
                content=e.content or {},
                created_at=e.created_at,
            )
            for e in case.evidence
        ],
        claim=claim_summary,
        rule_results=[
            RuleResultDetail(
                rule_id=rr.rule_id,
                triggered=rr.triggered,
                severity=float(rr.severity) if rr.severity is not None else None,
                confidence=float(rr.confidence) if rr.confidence is not None else None,
                evidence=rr.evidence or {},
                details=rr.details,
            )
            for rr in rule_results
        ],
    )


# ── PUT /api/cases/{case_id}/status — transition case status ────────────────

@router.put("/{case_id}/status", response_model=CaseDetail)
async def update_case_status(
    case_id: str,
    body: CaseStatusUpdate,
    ctx: RequestContext = Depends(require(Permission.CASES_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """
    Update case status with validated transitions.

    Allowed transitions:
        open -> under_review
        under_review -> resolved | open
        resolved -> closed | under_review
        closed -> (terminal)
    """
    case = await _get_case_or_404(case_id, db)

    allowed = _VALID_TRANSITIONS.get(case.status, set())
    if body.status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status transition: {case.status} -> {body.status}. "
                   f"Allowed targets: {sorted(allowed) if allowed else 'none (terminal state)'}",
        )

    old_status = case.status
    case.status = body.status

    # Set resolution fields if transitioning to resolved or closed
    if body.resolution_path is not None:
        case.resolution_path = body.resolution_path
    if body.resolution_notes is not None:
        case.resolution_notes = body.resolution_notes

    # Record timestamp for resolved / closed
    now = datetime.utcnow()
    if body.status == "resolved":
        case.resolved_at = now
    elif body.status == "closed":
        case.closed_at = now

    # Audit trail
    audit = AuditService(db)
    await audit.log_case_updated(
        case_id=case.case_id,
        old_status=old_status,
        new_status=body.status,
        actor=ctx.actor,
    )

    await db.flush()

    # Return full detail
    return await get_case(case_id, ctx, db)


# ── PUT /api/cases/{case_id}/assign — assign investigator ────────────────────

@router.put("/{case_id}/assign", response_model=CaseDetail)
async def assign_case(
    case_id: str,
    body: CaseAssign,
    ctx: RequestContext = Depends(require(Permission.CASES_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Assign or reassign a case to an investigator."""
    case = await _get_case_or_404(case_id, db)

    old_assignee = case.assigned_to
    case.assigned_to = body.assigned_to

    # Audit trail
    audit = AuditService(db)
    await audit.log_event(
        event_type="case_assigned",
        actor=ctx.actor,
        action=f"Case {case.case_id} assigned to {body.assigned_to}",
        resource_type="case",
        resource_id=case.case_id,
        details={
            "old_assigned_to": old_assignee,
            "new_assigned_to": body.assigned_to,
        },
    )

    await db.flush()

    return await get_case(case_id, ctx, db)


# ── POST /api/cases/{case_id}/notes — add investigation note ────────────────

@router.post("/{case_id}/notes", response_model=CaseNoteSchema, status_code=201)
async def add_case_note(
    case_id: str,
    body: CaseNoteCreate,
    ctx: RequestContext = Depends(require(Permission.CASES_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    """Add an investigation note to a case."""
    case = await _get_case_or_404(case_id, db)

    note = CaseNote(
        case_id=case.id,  # FK points to investigation_cases.id
        content=body.content,
        author=body.author,
    )
    db.add(note)
    await db.flush()

    return CaseNoteSchema(
        id=note.id,
        content=note.content,
        author=note.author,
        created_at=note.created_at,
    )


# ── GET /api/cases/{case_id}/evidence — evidence bundle ─────────────────────

@router.get("/{case_id}/evidence", response_model=dict)
async def get_case_evidence(case_id: str, ctx: RequestContext = Depends(require(Permission.CASES_READ)), db: AsyncSession = Depends(get_db)):
    """
    Assemble a comprehensive evidence bundle for the case.

    The bundle includes:
      - claim_data: the original claim record
      - risk_score: composite risk score and breakdown
      - rule_results: every rule evaluation for the claim
      - evidence_items: any investigator-attached evidence
    """
    case = await _get_case_or_404(case_id, db, load_relations=True)

    # ── Claim data ───────────────────────────────────────────────────────
    claim_data: dict | None = None
    if case.claim_type == "medical":
        result = await db.execute(
            select(MedicalClaim).where(MedicalClaim.claim_id == case.claim_id)
        )
        claim = result.scalar_one_or_none()
        if claim:
            claim_data = {
                "claim_id": claim.claim_id,
                "claim_type": "medical",
                "member_id": claim.member_id,
                "provider_id": claim.provider_id,
                "service_date": str(claim.service_date),
                "cpt_code": claim.cpt_code,
                "cpt_modifier": claim.cpt_modifier,
                "diagnosis_code_primary": claim.diagnosis_code_primary,
                "place_of_service": claim.place_of_service,
                "amount_billed": float(claim.amount_billed),
                "amount_allowed": float(claim.amount_allowed) if claim.amount_allowed is not None else None,
                "amount_paid": float(claim.amount_paid) if claim.amount_paid is not None else None,
                "units": claim.units,
                "status": claim.status,
            }
    else:
        result = await db.execute(
            select(PharmacyClaim).where(PharmacyClaim.claim_id == case.claim_id)
        )
        claim = result.scalar_one_or_none()
        if claim:
            claim_data = {
                "claim_id": claim.claim_id,
                "claim_type": "pharmacy",
                "member_id": claim.member_id,
                "pharmacy_id": claim.pharmacy_id,
                "prescriber_id": claim.prescriber_id,
                "fill_date": str(claim.fill_date),
                "ndc_code": claim.ndc_code,
                "drug_name": claim.drug_name,
                "drug_class": claim.drug_class,
                "is_controlled": claim.is_controlled,
                "dea_schedule": claim.dea_schedule,
                "quantity_dispensed": float(claim.quantity_dispensed),
                "days_supply": claim.days_supply,
                "amount_billed": float(claim.amount_billed),
                "amount_allowed": float(claim.amount_allowed) if claim.amount_allowed is not None else None,
                "amount_paid": float(claim.amount_paid) if claim.amount_paid is not None else None,
                "status": claim.status,
            }

    # ── Risk score ───────────────────────────────────────────────────────
    score_result = await db.execute(
        select(RiskScore).where(RiskScore.claim_id == case.claim_id)
    )
    risk_score_row = score_result.scalar_one_or_none()
    risk_score_data: dict | None = None
    if risk_score_row:
        risk_score_data = {
            "total_score": float(risk_score_row.total_score),
            "risk_level": risk_score_row.risk_level,
            "rules_triggered": risk_score_row.rules_triggered,
            "rule_contributions": risk_score_row.rule_contributions or {},
            "confidence_factor": float(risk_score_row.confidence_factor),
            "scored_at": str(risk_score_row.scored_at),
        }

    # ── Rule results ─────────────────────────────────────────────────────
    rr_result = await db.execute(
        select(RuleResult)
        .where(RuleResult.claim_id == case.claim_id)
        .order_by(RuleResult.rule_id)
    )
    rule_results = [
        {
            "rule_id": rr.rule_id,
            "triggered": rr.triggered,
            "severity": float(rr.severity) if rr.severity is not None else None,
            "confidence": float(rr.confidence) if rr.confidence is not None else None,
            "evidence": rr.evidence or {},
            "details": rr.details,
            "evaluated_at": str(rr.evaluated_at),
        }
        for rr in rr_result.scalars().all()
    ]

    # ── Stored evidence items ────────────────────────────────────────────
    evidence_items = [
        {
            "id": e.id,
            "evidence_type": e.evidence_type,
            "title": e.title,
            "content": e.content or {},
            "created_at": str(e.created_at),
        }
        for e in case.evidence
    ]

    return {
        "case_id": case.case_id,
        "claim_id": case.claim_id,
        "claim_type": case.claim_type,
        "risk_level": case.risk_level,
        "claim_data": claim_data,
        "risk_score": risk_score_data,
        "rule_results": rule_results,
        "evidence_items": evidence_items,
    }
