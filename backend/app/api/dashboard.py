"""
Dashboard API — aggregated analytics for the ArqAI FWA Detection overview.
"""

import logging
import traceback
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, case, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.auth.permissions import Permission
from app.auth.context import RequestContext
from app.config import settings
from app.models import (
    MedicalClaim,
    PharmacyClaim,
    RiskScore,
    RuleResult,
    Rule,
    InvestigationCase,
    Provider,
    Workspace,
)
from app.schemas.schemas import (
    DashboardOverview,
    RiskDistribution,
    TrendsResponse,
    TrendDataPoint,
    TopProvidersResponse,
    TopProviderItem,
    RuleEffectivenessResponse,
    RuleEffectivenessItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _resolve_ws(db: AsyncSession, workspace_id: str | None) -> int | None:
    """Resolve an optional workspace_id string to the internal integer PK."""
    if not workspace_id:
        return None
    ws_result = await db.execute(
        select(Workspace).where(Workspace.workspace_id == workspace_id)
    )
    ws = ws_result.scalar_one_or_none()
    return ws.id if ws else None


# ---------------------------------------------------------------------------
# GET /api/dashboard/overview
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=DashboardOverview)
async def get_overview(
    workspace_id: str | None = Query(None),
    ctx: RequestContext = Depends(require(Permission.DASHBOARD_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> DashboardOverview:
    """Return high-level dashboard statistics."""
    try:
        ws_id = await _resolve_ws(db, workspace_id)

        # Total claims across both tables
        med_count_stmt = select(func.count()).select_from(MedicalClaim)
        rx_count_stmt = select(func.count()).select_from(PharmacyClaim)
        if ws_id is not None:
            med_count_stmt = med_count_stmt.where(MedicalClaim.workspace_id == ws_id)
            rx_count_stmt = rx_count_stmt.where(PharmacyClaim.workspace_id == ws_id)
        medical_count = (await db.execute(med_count_stmt)).scalar() or 0
        pharmacy_count = (await db.execute(rx_count_stmt)).scalar() or 0
        total_claims = int(medical_count) + int(pharmacy_count)

        # Total flagged = risk_scores where risk_level is NOT 'low'
        flagged_stmt = select(func.count()).select_from(RiskScore).where(
            RiskScore.risk_level != "low"
        )
        if ws_id is not None:
            flagged_stmt = flagged_stmt.where(RiskScore.workspace_id == ws_id)
        total_flagged = int((await db.execute(flagged_stmt)).scalar() or 0)

        # Total fraud amount = sum of amount_billed for high/critical claims
        risk_subq = select(RiskScore.claim_id).where(
            RiskScore.risk_level.in_(["high", "critical"])
        )
        if ws_id is not None:
            risk_subq = risk_subq.where(RiskScore.workspace_id == ws_id)

        med_fraud_stmt = select(
            func.coalesce(func.sum(MedicalClaim.amount_billed), 0)
        ).where(MedicalClaim.claim_id.in_(risk_subq))
        rx_fraud_stmt = select(
            func.coalesce(func.sum(PharmacyClaim.amount_billed), 0)
        ).where(PharmacyClaim.claim_id.in_(risk_subq))
        if ws_id is not None:
            med_fraud_stmt = med_fraud_stmt.where(MedicalClaim.workspace_id == ws_id)
            rx_fraud_stmt = rx_fraud_stmt.where(PharmacyClaim.workspace_id == ws_id)

        med_fraud = float((await db.execute(med_fraud_stmt)).scalar() or 0)
        rx_fraud = float((await db.execute(rx_fraud_stmt)).scalar() or 0)
        total_fraud_amount = med_fraud + rx_fraud

        # Active cases
        active_stmt = select(func.count()).select_from(InvestigationCase).where(
            InvestigationCase.status.in_(["open", "under_review"])
        )
        if ws_id is not None:
            active_stmt = active_stmt.where(InvestigationCase.workspace_id == ws_id)
        active_cases = int((await db.execute(active_stmt)).scalar() or 0)

        # Risk distribution
        dist_stmt = select(
            RiskScore.risk_level,
            func.count().label("cnt"),
        )
        if ws_id is not None:
            dist_stmt = dist_stmt.where(RiskScore.workspace_id == ws_id)
        dist_stmt = dist_stmt.group_by(RiskScore.risk_level)
        dist_rows = (await db.execute(dist_stmt)).all()
        dist_map = {row[0]: int(row[1]) for row in dist_rows}
        risk_distribution = RiskDistribution(
            low=dist_map.get("low", 0),
            medium=dist_map.get("medium", 0),
            high=dist_map.get("high", 0),
            critical=dist_map.get("critical", 0),
        )

        return DashboardOverview(
            total_claims=total_claims,
            total_flagged=total_flagged,
            total_fraud_amount=total_fraud_amount,
            active_cases=active_cases,
            recovery_rate=0.0,
            risk_distribution=risk_distribution,
        )

    except Exception as exc:
        logger.error("Dashboard overview failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Dashboard overview error: {type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# GET /api/dashboard/trends
# ---------------------------------------------------------------------------

@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    period: str = Query("30d", pattern="^(30d|90d|1y)$"),
    workspace_id: str | None = Query(None),
    ctx: RequestContext = Depends(require(Permission.DASHBOARD_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> TrendsResponse:
    """Return daily trend data for claims processed/flagged over the given period."""
    try:
        ws_id = await _resolve_ws(db, workspace_id)

        period_map = {"30d": 30, "90d": 90, "1y": 365}
        days = period_map[period]
        cutoff = datetime.utcnow() - timedelta(days=days)

        score_date = cast(RiskScore.scored_at, Date).label("score_date")
        trends_stmt = (
            select(
                score_date,
                func.count().label("claims_processed"),
                func.sum(
                    case(
                        (RiskScore.risk_level != "low", 1),
                        else_=0,
                    )
                ).label("claims_flagged"),
            )
            .where(RiskScore.scored_at >= cutoff)
        )
        if ws_id is not None:
            trends_stmt = trends_stmt.where(RiskScore.workspace_id == ws_id)
        trends_stmt = trends_stmt.group_by(score_date).order_by(score_date)
        rows = (await db.execute(trends_stmt)).all()

        # Build fraud_amount per day lookup
        high_crit_conditions = [
            RiskScore.scored_at >= cutoff,
            RiskScore.risk_level.in_(["high", "critical"]),
        ]
        if ws_id is not None:
            high_crit_conditions.append(RiskScore.workspace_id == ws_id)
        high_crit_claims = (await db.execute(
            select(RiskScore.claim_id, RiskScore.claim_type).where(
                and_(*high_crit_conditions)
            )
        )).all()

        amount_map: dict[str, float] = {}
        if high_crit_claims:
            med_ids = [r[0] for r in high_crit_claims if r[1] == "medical"]
            rx_ids = [r[0] for r in high_crit_claims if r[1] == "pharmacy"]

            if med_ids:
                for row in (await db.execute(
                    select(MedicalClaim.claim_id, MedicalClaim.amount_billed).where(
                        MedicalClaim.claim_id.in_(med_ids)
                    )
                )).all():
                    amount_map[row[0]] = float(row[1])

            if rx_ids:
                for row in (await db.execute(
                    select(PharmacyClaim.claim_id, PharmacyClaim.amount_billed).where(
                        PharmacyClaim.claim_id.in_(rx_ids)
                    )
                )).all():
                    amount_map[row[0]] = float(row[1])

        date_fraud: dict[str, float] = {}
        if high_crit_claims:
            fraud_date_conditions = [
                RiskScore.scored_at >= cutoff,
                RiskScore.risk_level.in_(["high", "critical"]),
            ]
            if ws_id is not None:
                fraud_date_conditions.append(RiskScore.workspace_id == ws_id)
            for row in (await db.execute(
                select(
                    cast(RiskScore.scored_at, Date).label("score_date"),
                    RiskScore.claim_id,
                ).where(and_(*fraud_date_conditions))
            )).all():
                d = str(row[0])
                date_fraud[d] = date_fraud.get(d, 0.0) + amount_map.get(row[1], 0.0)

        data = [
            TrendDataPoint(
                date=str(row[0]),
                claims_processed=int(row[1]),
                claims_flagged=int(row[2] or 0),
                fraud_amount=date_fraud.get(str(row[0]), 0.0),
            )
            for row in rows
        ]

        return TrendsResponse(period=period, data=data)

    except Exception as exc:
        logger.error("Dashboard trends failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Dashboard trends error: {type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# GET /api/dashboard/top-providers
# ---------------------------------------------------------------------------

@router.get("/top-providers", response_model=TopProvidersResponse)
async def get_top_providers(
    limit: int = Query(10, ge=1, le=100),
    workspace_id: str | None = Query(None),
    ctx: RequestContext = Depends(require(Permission.DASHBOARD_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> TopProvidersResponse:
    """Return providers ranked by average risk score (descending)."""
    try:
        ws_id = await _resolve_ws(db, workspace_id)

        query = (
            select(
                Provider.id.label("provider_id"),
                Provider.npi,
                Provider.name,
                Provider.specialty,
                func.avg(RiskScore.total_score).label("avg_risk_score"),
                func.sum(
                    case(
                        (RiskScore.risk_level != "low", 1),
                        else_=0,
                    )
                ).label("flagged_claims"),
                func.sum(MedicalClaim.amount_billed).label("total_amount"),
            )
            .join(MedicalClaim, MedicalClaim.provider_id == Provider.id)
            .join(RiskScore, RiskScore.claim_id == MedicalClaim.claim_id)
        )
        if ws_id is not None:
            query = query.where(MedicalClaim.workspace_id == ws_id)
        query = (
            query
            .group_by(Provider.id, Provider.npi, Provider.name, Provider.specialty)
            .order_by(func.avg(RiskScore.total_score).desc())
            .limit(limit)
        )

        rows = (await db.execute(query)).all()

        providers = [
            TopProviderItem(
                provider_id=int(row.provider_id),
                npi=str(row.npi),
                name=str(row.name),
                specialty=str(row.specialty) if row.specialty else None,
                risk_score=round(float(row.avg_risk_score or 0), 2),
                flagged_claims=int(row.flagged_claims or 0),
                total_amount=round(float(row.total_amount or 0), 2),
            )
            for row in rows
        ]

        return TopProvidersResponse(providers=providers)

    except Exception as exc:
        logger.error("Dashboard top-providers failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Dashboard top-providers error: {type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# GET /api/dashboard/rule-effectiveness
# ---------------------------------------------------------------------------

@router.get("/rule-effectiveness", response_model=RuleEffectivenessResponse)
async def get_rule_effectiveness(
    workspace_id: str | None = Query(None),
    ctx: RequestContext = Depends(require(Permission.DASHBOARD_VIEW)),
    db: AsyncSession = Depends(get_db),
) -> RuleEffectivenessResponse:
    """Return effectiveness stats for each rule: trigger count, avg severity, fraud amount."""
    try:
        ws_id = await _resolve_ws(db, workspace_id)

        rule_conditions = [RuleResult.triggered == True]  # noqa: E712
        if ws_id is not None:
            rule_conditions.append(RuleResult.workspace_id == ws_id)
        query = (
            select(
                RuleResult.rule_id,
                Rule.category,
                Rule.fraud_type,
                func.count().label("times_triggered"),
                func.avg(RuleResult.severity).label("avg_severity"),
            )
            .join(Rule, Rule.rule_id == RuleResult.rule_id)
            .where(and_(*rule_conditions))
            .group_by(RuleResult.rule_id, Rule.category, Rule.fraud_type)
            .order_by(func.count().desc())
        )

        rows = (await db.execute(query)).all()

        rules_list = []
        for row in rows:
            risk_subq = select(RiskScore.claim_id).where(
                RiskScore.risk_level.in_(["high", "critical"])
            )
            if ws_id is not None:
                risk_subq = risk_subq.where(RiskScore.workspace_id == ws_id)

            med_fraud_conditions = [
                MedicalClaim.claim_id.in_(
                    select(RuleResult.claim_id).where(
                        and_(
                            RuleResult.rule_id == row.rule_id,
                            RuleResult.triggered == True,  # noqa: E712
                        )
                    )
                ),
                MedicalClaim.claim_id.in_(risk_subq),
            ]
            if ws_id is not None:
                med_fraud_conditions.append(MedicalClaim.workspace_id == ws_id)

            fraud_q = await db.execute(
                select(
                    func.coalesce(func.sum(MedicalClaim.amount_billed), 0)
                ).where(and_(*med_fraud_conditions))
            )

            rx_fraud_conditions = [
                PharmacyClaim.claim_id.in_(
                    select(RuleResult.claim_id).where(
                        and_(
                            RuleResult.rule_id == row.rule_id,
                            RuleResult.triggered == True,  # noqa: E712
                        )
                    )
                ),
                PharmacyClaim.claim_id.in_(risk_subq),
            ]
            if ws_id is not None:
                rx_fraud_conditions.append(PharmacyClaim.workspace_id == ws_id)

            fraud_rx_q = await db.execute(
                select(
                    func.coalesce(func.sum(PharmacyClaim.amount_billed), 0)
                ).where(and_(*rx_fraud_conditions))
            )
            total_fraud = float(fraud_q.scalar() or 0) + float(fraud_rx_q.scalar() or 0)

            rules_list.append(
                RuleEffectivenessItem(
                    rule_id=str(row.rule_id),
                    category=str(row.category),
                    fraud_type=str(row.fraud_type),
                    times_triggered=int(row.times_triggered),
                    avg_severity=round(float(row.avg_severity or 0), 2),
                    total_fraud_amount=round(total_fraud, 2),
                )
            )

        return RuleEffectivenessResponse(rules=rules_list)

    except Exception as exc:
        logger.error("Dashboard rule-effectiveness failed: %s\n%s", exc, traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Dashboard rule-effectiveness error: {type(exc).__name__}: {exc}",
        )
