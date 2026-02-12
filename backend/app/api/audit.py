"""
Audit API Router — query audit trail and verify hash-chain integrity.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.auth.permissions import Permission
from app.auth.context import RequestContext
from app.services.audit_service import AuditService
from app.schemas.schemas import AuditListResponse, AuditEntry, IntegrityCheckResponse

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=AuditListResponse)
async def list_audit_entries(
    event_type: str | None = Query(None, description="Filter by event type"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    resource_id: str | None = Query(None, description="Filter by resource ID"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=200, description="Page size"),
    ctx: RequestContext = Depends(require(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> AuditListResponse:
    """Return a paginated list of audit log entries with optional filters."""
    service = AuditService(db)
    offset = (page - 1) * size

    entries = await service.get_entries(
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        limit=size,
        offset=offset,
    )

    total = await service.get_entry_count(event_type=event_type)
    pages = (total + size - 1) // size if total > 0 else 1

    items = [
        AuditEntry(
            id=entry.id,
            event_id=entry.event_id,
            event_type=entry.event_type,
            actor=entry.actor,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            details=entry.details,
            previous_hash=entry.previous_hash,
            current_hash=entry.current_hash,
            created_at=entry.created_at,
        )
        for entry in entries
    ]

    return AuditListResponse(
        total=total,
        page=page,
        size=size,
        pages=pages,
        items=items,
    )


@router.get("/integrity", response_model=IntegrityCheckResponse)
async def check_integrity(
    ctx: RequestContext = Depends(require(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
) -> IntegrityCheckResponse:
    """Verify the hash-chain integrity of the entire audit trail."""
    service = AuditService(db)
    result = await service.verify_chain_integrity()
    return IntegrityCheckResponse(**result)
