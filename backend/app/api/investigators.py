"""
Investigators API — manage investigators, assignment rules, and workload.
"""

from uuid import uuid4

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.auth.permissions import Permission
from app.auth.context import RequestContext
from app.models.investigator import Investigator
from app.models.assignment_rule import AssignmentRule
from app.services.assignment_service import AssignmentService

router = APIRouter(prefix="/api/investigators", tags=["investigators"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class InvestigatorCreate(BaseModel):
    name: str = Field(..., max_length=100)
    email: str | None = Field(None, max_length=200)
    specialty: str = Field("both", pattern="^(medical|pharmacy|both)$")
    seniority: str = Field("standard", pattern="^(junior|standard|senior)$")
    max_caseload: int = Field(20, ge=1, le=200)
    workspace_id: int | None = None


class InvestigatorUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=200)
    specialty: str | None = Field(None, pattern="^(medical|pharmacy|both)$")
    seniority: str | None = Field(None, pattern="^(junior|standard|senior)$")
    max_caseload: int | None = Field(None, ge=1, le=200)
    is_available: bool | None = None


class InvestigatorResponse(BaseModel):
    investigator_id: str
    name: str
    email: str | None
    specialty: str
    seniority: str
    max_caseload: int
    is_available: bool
    workspace_id: int | None
    created_at: str | None


class AssignmentRuleCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=500)
    priority: int = Field(100, ge=1)
    conditions: dict = Field(default_factory=dict)
    strategy: str = Field("round_robin", pattern="^(round_robin|workload_balanced|skill_matched)$")
    target_filter: dict = Field(default_factory=dict)
    is_enabled: bool = True
    workspace_id: int | None = None


class AssignmentRuleUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=500)
    priority: int | None = Field(None, ge=1)
    conditions: dict | None = None
    strategy: str | None = Field(None, pattern="^(round_robin|workload_balanced|skill_matched)$")
    target_filter: dict | None = None
    is_enabled: bool | None = None


class AssignmentRuleResponse(BaseModel):
    rule_id: str
    name: str
    description: str | None
    priority: int
    conditions: dict
    strategy: str
    target_filter: dict
    is_enabled: bool
    workspace_id: int | None
    created_at: str | None


# ── Investigator endpoints ───────────────────────────────────────────────────


@router.get("")
async def list_investigators(
    workspace_id: int | None = Query(None),
    ctx: RequestContext = Depends(require(Permission.CASES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """List investigators with workload stats."""
    svc = AssignmentService(db)
    summary = await svc.get_workload_summary(workspace_id)
    return {"investigators": summary, "total": len(summary)}


@router.post("", status_code=201)
async def create_investigator(
    body: InvestigatorCreate,
    ctx: RequestContext = Depends(require(Permission.ADMIN_USERS)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new investigator."""
    inv = Investigator(
        investigator_id=f"INV-{uuid4().hex[:8].upper()}",
        name=body.name,
        email=body.email,
        specialty=body.specialty,
        seniority=body.seniority,
        max_caseload=body.max_caseload,
        workspace_id=body.workspace_id,
    )
    db.add(inv)
    await db.flush()

    return InvestigatorResponse(
        investigator_id=inv.investigator_id,
        name=inv.name,
        email=inv.email,
        specialty=inv.specialty,
        seniority=inv.seniority,
        max_caseload=inv.max_caseload,
        is_available=inv.is_available,
        workspace_id=inv.workspace_id,
        created_at=str(inv.created_at) if inv.created_at else None,
    )


@router.get("/workload")
async def get_workload(
    workspace_id: int | None = Query(None),
    ctx: RequestContext = Depends(require(Permission.CASES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Workload summary for dashboard."""
    svc = AssignmentService(db)
    summary = await svc.get_workload_summary(workspace_id)
    return {"workload": summary}


@router.get("/{investigator_id}")
async def get_investigator(
    investigator_id: str,
    ctx: RequestContext = Depends(require(Permission.CASES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Get investigator detail with caseload."""
    result = await db.execute(
        select(Investigator).where(
            Investigator.investigator_id == investigator_id
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigator not found")

    svc = AssignmentService(db)
    caseload = await svc._get_active_caseload(inv)

    return {
        "investigator_id": inv.investigator_id,
        "name": inv.name,
        "email": inv.email,
        "specialty": inv.specialty,
        "seniority": inv.seniority,
        "max_caseload": inv.max_caseload,
        "is_available": inv.is_available,
        "workspace_id": inv.workspace_id,
        "active_cases": caseload,
        "utilization": round(caseload / inv.max_caseload * 100, 1)
        if inv.max_caseload > 0
        else 0,
        "created_at": str(inv.created_at) if inv.created_at else None,
    }


@router.put("/{investigator_id}")
async def update_investigator(
    investigator_id: str,
    body: InvestigatorUpdate,
    ctx: RequestContext = Depends(require(Permission.ADMIN_USERS)),
    db: AsyncSession = Depends(get_db),
):
    """Update investigator."""
    result = await db.execute(
        select(Investigator).where(
            Investigator.investigator_id == investigator_id
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigator not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(inv, field, value)

    await db.flush()

    return InvestigatorResponse(
        investigator_id=inv.investigator_id,
        name=inv.name,
        email=inv.email,
        specialty=inv.specialty,
        seniority=inv.seniority,
        max_caseload=inv.max_caseload,
        is_available=inv.is_available,
        workspace_id=inv.workspace_id,
        created_at=str(inv.created_at) if inv.created_at else None,
    )


@router.delete("/{investigator_id}", status_code=204)
async def delete_investigator(
    investigator_id: str,
    ctx: RequestContext = Depends(require(Permission.ADMIN_USERS)),
    db: AsyncSession = Depends(get_db),
):
    """Remove an investigator."""
    result = await db.execute(
        select(Investigator).where(
            Investigator.investigator_id == investigator_id
        )
    )
    inv = result.scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=404, detail="Investigator not found")

    await db.delete(inv)
    await db.flush()


# ── Assignment Rule endpoints ────────────────────────────────────────────────


@router.get("/rules/list")
async def list_assignment_rules(
    workspace_id: int | None = Query(None),
    ctx: RequestContext = Depends(require(Permission.CASES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """List assignment rules ordered by priority."""
    conditions = []
    if workspace_id is not None:
        conditions.append(AssignmentRule.workspace_id == workspace_id)

    where_clause = and_(*conditions) if conditions else True
    result = await db.execute(
        select(AssignmentRule)
        .where(where_clause)
        .order_by(AssignmentRule.priority.asc())
    )
    rules = list(result.scalars())

    return {
        "rules": [
            AssignmentRuleResponse(
                rule_id=r.rule_id,
                name=r.name,
                description=r.description,
                priority=r.priority,
                conditions=r.conditions or {},
                strategy=r.strategy,
                target_filter=r.target_filter or {},
                is_enabled=r.is_enabled,
                workspace_id=r.workspace_id,
                created_at=str(r.created_at) if r.created_at else None,
            )
            for r in rules
        ],
        "total": len(rules),
    }


@router.post("/rules", status_code=201)
async def create_assignment_rule(
    body: AssignmentRuleCreate,
    ctx: RequestContext = Depends(require(Permission.ADMIN_SYSTEM)),
    db: AsyncSession = Depends(get_db),
):
    """Create an assignment rule."""
    rule = AssignmentRule(
        rule_id=f"ARULE-{uuid4().hex[:8].upper()}",
        name=body.name,
        description=body.description,
        priority=body.priority,
        conditions=body.conditions,
        strategy=body.strategy,
        target_filter=body.target_filter,
        is_enabled=body.is_enabled,
        workspace_id=body.workspace_id,
    )
    db.add(rule)
    await db.flush()

    return AssignmentRuleResponse(
        rule_id=rule.rule_id,
        name=rule.name,
        description=rule.description,
        priority=rule.priority,
        conditions=rule.conditions or {},
        strategy=rule.strategy,
        target_filter=rule.target_filter or {},
        is_enabled=rule.is_enabled,
        workspace_id=rule.workspace_id,
        created_at=str(rule.created_at) if rule.created_at else None,
    )


@router.put("/rules/{rule_id}")
async def update_assignment_rule(
    rule_id: str,
    body: AssignmentRuleUpdate,
    ctx: RequestContext = Depends(require(Permission.ADMIN_SYSTEM)),
    db: AsyncSession = Depends(get_db),
):
    """Update an assignment rule."""
    result = await db.execute(
        select(AssignmentRule).where(AssignmentRule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Assignment rule not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    await db.flush()

    return AssignmentRuleResponse(
        rule_id=rule.rule_id,
        name=rule.name,
        description=rule.description,
        priority=rule.priority,
        conditions=rule.conditions or {},
        strategy=rule.strategy,
        target_filter=rule.target_filter or {},
        is_enabled=rule.is_enabled,
        workspace_id=rule.workspace_id,
        created_at=str(rule.created_at) if rule.created_at else None,
    )


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_assignment_rule(
    rule_id: str,
    ctx: RequestContext = Depends(require(Permission.ADMIN_SYSTEM)),
    db: AsyncSession = Depends(get_db),
):
    """Delete an assignment rule."""
    result = await db.execute(
        select(AssignmentRule).where(AssignmentRule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Assignment rule not found")

    await db.delete(rule)
    await db.flush()
