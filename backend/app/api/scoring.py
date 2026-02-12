"""
Scoring API Router — manage risk-level thresholds.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.auth.permissions import Permission
from app.auth.context import RequestContext
from app.services.scoring_engine import ScoringEngine, DEFAULT_RISK_THRESHOLDS
from app.services.audit_service import AuditService
from app.schemas.schemas import ScoringThresholds

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.get("/thresholds", response_model=ScoringThresholds)
async def get_thresholds(
    ctx: RequestContext = Depends(require(Permission.SCORING_READ)),
) -> ScoringThresholds:
    """Return the current risk-level thresholds."""
    return ScoringThresholds(**DEFAULT_RISK_THRESHOLDS)


@router.put("/thresholds", response_model=ScoringThresholds)
async def update_thresholds(
    body: ScoringThresholds,
    db: AsyncSession = Depends(get_db),
    ctx: RequestContext = Depends(require(Permission.RULES_CONFIGURE)),
) -> ScoringThresholds:
    """
    Update risk-level thresholds.

    Validates that low_max < medium_max < high_max and all values are
    within the 0-100 range. In a production system the new values would
    be persisted; for now they are validated, audit-logged, and returned.
    """
    # Validate ordering
    if not (0 <= body.low_max < body.medium_max < body.high_max <= 100):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=422,
            detail="Thresholds must satisfy 0 <= low_max < medium_max < high_max <= 100",
        )

    # Capture previous values for the audit trail
    previous = DEFAULT_RISK_THRESHOLDS.copy()

    # Update the in-memory defaults (non-persistent)
    DEFAULT_RISK_THRESHOLDS["low_max"] = body.low_max
    DEFAULT_RISK_THRESHOLDS["medium_max"] = body.medium_max
    DEFAULT_RISK_THRESHOLDS["high_max"] = body.high_max

    # Audit log the change
    audit = AuditService(db)
    await audit.log_event(
        event_type="threshold_updated",
        actor=ctx.actor,
        action="Risk scoring thresholds updated",
        resource_type="scoring_thresholds",
        resource_id=None,
        details={
            "previous": previous,
            "updated": {
                "low_max": body.low_max,
                "medium_max": body.medium_max,
                "high_max": body.high_max,
            },
        },
    )

    return body
