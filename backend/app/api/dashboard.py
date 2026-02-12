"""
Dashboard API — aggregated analytics for the ArqAI FWA Detection overview.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, case, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
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

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
async def get_overview(
    workspace_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> DashboardOverview:
    """Return high-level dashboard statistics."""

    # Resolve optional workspace_id to internal integer id
    ws_id = None
    if workspace_id:
        ws_result = await db.execute(select(Workspace).where(Workspace.workspace_id == workspace_id))
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws_id = ws.id

    # Total claims across both tables
    med_count_stmt = select(func.count()).select_from(MedicalClaim)
    rx_count_stmt = select(func.count()).select_from(PharmacyClaim)
    if ws_id is not None:
        med_count_stmt = med_count_stmt.where(MedicalClaim.workspace_id == ws_id)
        rx_count_stmt = rx_count_stmt.where(PharmacyClaim.workspace_id == ws_id)
    medical_count_q = await db.execute(med_count_stmt)
    pharmacy_count_q = await db.execute(rx_count_stmt)
    total_claims = (medical_count_q.scalar() or 0) + (pharmacy_count_q.scalar() or 0)

    # Total flagged = risk_scores where risk_level is NOT 'low'
    flagged_stmt = select(func.count()).select_from(RiskScore).where(
        RiskScore.risk_level != "low"
    )
    if ws_id is not None:
        flagged_stmt = flagged_stmt.where(RiskScore.workspace_id == ws_id)
    flagged_q = await db.execute(flagged_stmt)
    total_flagged = flagged_q.scalar() or 0

    # Total fraud amount = sum of amount_billed from medical claims that have
    # high/critical risk scores, plus the same from pharmacy claims.
    risk_subq = select(RiskScore.claim_id).where(
        RiskScore.risk_level.in_(["high", "critical"])
    )
    if ws_id is not None:
        risk_subq = risk_subq.where(RiskScore.workspace_id == ws_id)

    med_fraud_stmt = select(func.coalesce(func.sum(MedicalClaim.amount_billed), 0)).where(
        MedicalClaim.claim_id.in_(risk_subq)
    )
    rx_fraud_stmt = select(func.coalesce(func.sum(PharmacyClaim.amount_billed), 0)).where(
        PharmacyClaim.claim_id.in_(risk_subq)
    )
    if ws_id is not None:
        med_fraud_stmt = med_fraud_stmt.where(MedicalClaim.workspace_id == ws_id)
        rx_fraud_stmt = rx_fraud_stmt.where(PharmacyClaim.workspace_id == ws_id)

    medical_fraud_q = await db.execute(med_fraud_stmt)
    pharmacy_fraud_q = await db.execute(rx_fraud_stmt)
    total_fraud_amount = float(medical_fraud_q.scalar() or 0) + float(
        pharmacy_fraud_q.scalar() or 0
    )

    # Active cases = investigation_cases with status in ('open', 'under_review')
    active_stmt = select(func.count()).select_from(InvestigationCase).where(
        InvestigationCase.status.in_(["open", "under_review"])
    )
    if ws_id is not None:
        active_stmt = active_stmt.where(InvestigationCase.workspace_id == ws_id)
    active_q = await db.execute(active_stmt)
    active_cases = active_q.scalar() or 0

    # Risk distribution from risk_scores table
    dist_stmt = select(
        RiskScore.risk_level,
        func.count().label("cnt"),
    )
    if ws_id is not None:
        dist_stmt = dist_stmt.where(RiskScore.workspace_id == ws_id)
    dist_stmt = dist_stmt.group_by(RiskScore.risk_level)
    dist_q = await db.execute(dist_stmt)
    dist_rows = dist_q.all()
    dist_map = {row[0]: row[1] for row in dist_rows}
    risk_distribution = RiskDistribution(
        low=dist_map.get("low", 0),
        medium=dist_map.get("medium", 0),
        high=dist_map.get("high", 0),
        critical=dist_map.get("critical", 0),
    )

    # Recovery rate — placeholder
    recovery_rate = 0.0

    return DashboardOverview(
        total_claims=total_claims,
        total_flagged=total_flagged,
        total_fraud_amount=total_fraud_amount,
        active_cases=active_cases,
        recovery_rate=recovery_rate,
        risk_distribution=risk_distribution,
    )


@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    period: str = Query("30d", pattern="^(30d|90d|1y)$"),
    workspace_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> TrendsResponse:
    """Return daily trend data for claims processed/flagged over the given period."""

    # Resolve optional workspace_id to internal integer id
    ws_id = None
    if workspace_id:
        ws_result = await db.execute(select(Workspace).where(Workspace.workspace_id == workspace_id))
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws_id = ws.id

    # Determine lookback window
    period_map = {"30d": 30, "90d": 90, "1y": 365}
    days = period_map[period]
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Group risk_scores by scored_at date.
    # Each risk_score row represents one processed claim.
    # "Flagged" = risk_level != 'low'.
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
    trends_q = await db.execute(trends_stmt)
    rows = trends_q.all()

    # For fraud_amount per day, we need to join to claims.
    # Build a lookup of claim_id -> amount_billed for high/critical scores in the window.
    high_crit_conditions = [
        RiskScore.scored_at >= cutoff,
        RiskScore.risk_level.in_(["high", "critical"]),
    ]
    if ws_id is not None:
        high_crit_conditions.append(RiskScore.workspace_id == ws_id)
    high_crit_q = await db.execute(
        select(RiskScore.claim_id, RiskScore.claim_type).where(
            and_(*high_crit_conditions)
        )
    )
    high_crit_claims = high_crit_q.all()

    # Build mapping: claim_id -> amount_billed
    amount_map: dict[str, float] = {}
    if high_crit_claims:
        med_ids = [r[0] for r in high_crit_claims if r[1] == "medical"]
        rx_ids = [r[0] for r in high_crit_claims if r[1] == "pharmacy"]

        if med_ids:
            med_q = await db.execute(
                select(MedicalClaim.claim_id, MedicalClaim.amount_billed).where(
                    MedicalClaim.claim_id.in_(med_ids)
                )
            )
            for row in med_q.all():
                amount_map[row[0]] = float(row[1])

        if rx_ids:
            rx_q = await db.execute(
                select(PharmacyClaim.claim_id, PharmacyClaim.amount_billed).where(
                    PharmacyClaim.claim_id.in_(rx_ids)
                )
            )
            for row in rx_q.all():
                amount_map[row[0]] = float(row[1])

    # Build a date -> fraud_amount lookup via risk_scores
    date_fraud: dict[str, float] = {}
    if high_crit_claims:
        fraud_date_conditions = [
            RiskScore.scored_at >= cutoff,
            RiskScore.risk_level.in_(["high", "critical"]),
        ]
        if ws_id is not None:
            fraud_date_conditions.append(RiskScore.workspace_id == ws_id)
        fraud_date_q = await db.execute(
            select(
                cast(RiskScore.scored_at, Date).label("score_date"),
                RiskScore.claim_id,
            ).where(
                and_(*fraud_date_conditions)
            )
        )
        for row in fraud_date_q.all():
            d = str(row[0])
            date_fraud[d] = date_fraud.get(d, 0.0) + amount_map.get(row[1], 0.0)

    data = [
        TrendDataPoint(
            date=str(row[0]),
            claims_processed=row[1],
            claims_flagged=row[2] or 0,
            fraud_amount=date_fraud.get(str(row[0]), 0.0),
        )
        for row in rows
    ]

    return TrendsResponse(period=period, data=data)


@router.get("/top-providers", response_model=TopProvidersResponse)
async def get_top_providers(
    limit: int = Query(10, ge=1, le=100),
    workspace_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> TopProvidersResponse:
    """Return providers ranked by average risk score (descending)."""

    # Resolve optional workspace_id to internal integer id
    ws_id = None
    if workspace_id:
        ws_result = await db.execute(select(Workspace).where(Workspace.workspace_id == workspace_id))
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws_id = ws.id

    # Join providers -> medical_claims -> risk_scores.
    # Aggregate per provider: avg score, count of flagged claims, total amount_billed.
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

    result = await db.execute(query)
    rows = result.all()

    providers = [
        TopProviderItem(
            provider_id=row.provider_id,
            npi=row.npi,
            name=row.name,
            specialty=row.specialty,
            risk_score=round(float(row.avg_risk_score or 0), 2),
            flagged_claims=int(row.flagged_claims or 0),
            total_amount=round(float(row.total_amount or 0), 2),
        )
        for row in rows
    ]

    return TopProvidersResponse(providers=providers)


@router.get("/rule-effectiveness", response_model=RuleEffectivenessResponse)
async def get_rule_effectiveness(
    workspace_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> RuleEffectivenessResponse:
    """Return effectiveness stats for each rule: trigger count, avg severity, fraud amount."""

    # Resolve optional workspace_id to internal integer id
    ws_id = None
    if workspace_id:
        ws_result = await db.execute(select(Workspace).where(Workspace.workspace_id == workspace_id))
        ws = ws_result.scalar_one_or_none()
        if ws:
            ws_id = ws.id

    # Aggregate rule_results (only triggered) grouped by rule_id, joined to rules for category.
    # For total_fraud_amount, sum amount_billed of claims where this rule triggered and
    # the overall risk_level is high/critical.
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

    result = await db.execute(query)
    rows = result.all()

    rules_list = []
    for row in rows:
        # For each rule, sum fraud amounts of high/critical claims where this rule triggered.
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
                func.coalesce(
                    func.sum(MedicalClaim.amount_billed), 0
                )
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
                func.coalesce(
                    func.sum(PharmacyClaim.amount_billed), 0
                )
            ).where(and_(*rx_fraud_conditions))
        )
        total_fraud = float(fraud_q.scalar() or 0) + float(fraud_rx_q.scalar() or 0)

        rules_list.append(
            RuleEffectivenessItem(
                rule_id=row.rule_id,
                category=row.category,
                fraud_type=row.fraud_type,
                times_triggered=row.times_triggered,
                avg_severity=round(float(row.avg_severity or 0), 2),
                total_fraud_amount=round(total_fraud, 2),
            )
        )

    return RuleEffectivenessResponse(rules=rules_list)
