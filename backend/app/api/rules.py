"""
Rules API — ArqAI FWA Detection

CRUD + stats for fraud-detection rule configuration.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.models import Rule, RuleResult
from app.services.audit_service import AuditService
from app.auth.permissions import Permission
from app.auth.context import RequestContext
from app.schemas.schemas import (
    RuleSummary,
    RuleListResponse,
    RuleConfigUpdate,
    RuleStats,
)

router = APIRouter(prefix="/api/rules", tags=["rules"])


# ── GET /api/rules — list all rules with current config ─────────────────────

@router.get("", response_model=RuleListResponse)
async def list_rules(
    ctx: RequestContext = Depends(require(Permission.RULES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Return every rule with its current configuration."""
    result = await db.execute(
        select(Rule).order_by(Rule.claim_type, Rule.rule_id)
    )
    rules = list(result.scalars().all())

    items = [
        RuleSummary(
            rule_id=r.rule_id,
            category=r.category,
            fraud_type=r.fraud_type,
            claim_type=r.claim_type,
            description=r.description,
            detection_logic=r.detection_logic,
            weight=float(r.weight),
            enabled=r.enabled,
            thresholds=r.thresholds or {},
        )
        for r in rules
    ]
    return RuleListResponse(rules=items, total=len(items))


# ── GET /api/rules/{rule_id} — single rule detail ───────────────────────────

@router.get("/{rule_id}", response_model=RuleSummary)
async def get_rule(
    rule_id: str,
    ctx: RequestContext = Depends(require(Permission.RULES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Return a single rule with its thresholds and configuration."""
    result = await db.execute(
        select(Rule).where(Rule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    return RuleSummary(
        rule_id=rule.rule_id,
        category=rule.category,
        fraud_type=rule.fraud_type,
        claim_type=rule.claim_type,
        description=rule.description,
        detection_logic=rule.detection_logic,
        weight=float(rule.weight),
        enabled=rule.enabled,
        thresholds=rule.thresholds or {},
    )


# ── PUT /api/rules/{rule_id}/config — update rule configuration ─────────────

@router.put("/{rule_id}/config", response_model=RuleSummary)
async def update_rule_config(
    rule_id: str,
    body: RuleConfigUpdate,
    ctx: RequestContext = Depends(require(Permission.RULES_CONFIGURE)),
    db: AsyncSession = Depends(get_db),
):
    """
    Update rule thresholds, weight, and/or enabled flag.
    Only provided fields are changed. All changes are audit-logged.
    """
    result = await db.execute(
        select(Rule).where(Rule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    # Track what actually changed for the audit log
    changes: dict = {}

    if body.weight is not None:
        if not (0.0 <= body.weight <= 10.0):
            raise HTTPException(
                status_code=422,
                detail="weight must be between 0.0 and 10.0",
            )
        changes["weight"] = {"old": float(rule.weight), "new": body.weight}
        rule.weight = body.weight

    if body.enabled is not None:
        changes["enabled"] = {"old": rule.enabled, "new": body.enabled}
        rule.enabled = body.enabled

    if body.thresholds is not None:
        changes["thresholds"] = {"old": rule.thresholds, "new": body.thresholds}
        rule.thresholds = body.thresholds

    if not changes:
        raise HTTPException(
            status_code=422,
            detail="No valid fields provided for update",
        )

    # Bump version and record modifier
    rule.version += 1
    rule.last_modified_by = ctx.actor

    # Audit trail
    audit = AuditService(db)
    await audit.log_rule_config_changed(
        rule_id=rule_id,
        changes=changes,
        admin=ctx.actor,
    )

    await db.flush()

    return RuleSummary(
        rule_id=rule.rule_id,
        category=rule.category,
        fraud_type=rule.fraud_type,
        claim_type=rule.claim_type,
        description=rule.description,
        detection_logic=rule.detection_logic,
        weight=float(rule.weight),
        enabled=rule.enabled,
        thresholds=rule.thresholds or {},
    )


# ── GET /api/rules/{rule_id}/stats — rule performance statistics ─────────────

@router.get("/{rule_id}/stats", response_model=RuleStats)
async def get_rule_stats(
    rule_id: str,
    ctx: RequestContext = Depends(require(Permission.RULES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregate performance statistics for a single rule.

    Returns trigger count, average severity among triggered evaluations,
    average confidence, total claims evaluated, and trigger rate.
    """
    # Verify the rule exists
    rule_result = await db.execute(
        select(Rule).where(Rule.rule_id == rule_id)
    )
    rule = rule_result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    # Total evaluations for this rule
    total_result = await db.execute(
        select(func.count()).select_from(RuleResult).where(
            RuleResult.rule_id == rule_id
        )
    )
    total_evaluated = total_result.scalar() or 0

    # Triggered evaluations: count, avg severity, avg confidence
    triggered_result = await db.execute(
        select(
            func.count().label("trigger_count"),
            func.coalesce(func.avg(RuleResult.severity), 0).label("avg_severity"),
            func.coalesce(func.avg(RuleResult.confidence), 0).label("avg_confidence"),
        )
        .select_from(RuleResult)
        .where(
            RuleResult.rule_id == rule_id,
            RuleResult.triggered.is_(True),
        )
    )
    row = triggered_result.one()
    trigger_count = row.trigger_count or 0
    avg_severity = float(row.avg_severity)
    avg_confidence = float(row.avg_confidence)

    trigger_rate = (trigger_count / total_evaluated * 100.0) if total_evaluated > 0 else 0.0

    return RuleStats(
        rule_id=rule.rule_id,
        category=rule.category,
        times_triggered=trigger_count,
        avg_severity=round(avg_severity, 2),
        avg_confidence=round(avg_confidence, 2),
        total_claims_evaluated=total_evaluated,
        trigger_rate=round(trigger_rate, 2),
    )
