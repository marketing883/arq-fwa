"""
Workspaces API — CRUD, upload preview, and data ingestion.
"""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.workspace import Workspace
from app.models.claim import MedicalClaim, PharmacyClaim
from app.services.upload_service import UploadService

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


# ── Schemas ──

class WorkspaceCreate(BaseModel):
    name: str
    client_name: str | None = None
    description: str | None = None


class WorkspaceSummary(BaseModel):
    workspace_id: str
    name: str
    client_name: str | None
    description: str | None
    data_source: str
    status: str
    claim_count: int
    created_at: str | None


class WorkspaceListResponse(BaseModel):
    workspaces: list[WorkspaceSummary]
    total: int


class IngestRequest(BaseModel):
    mapping: dict[str, str]
    claim_type: str = "medical"


# ── Helpers ──

async def _get_workspace_or_404(workspace_id: str, db: AsyncSession) -> Workspace:
    result = await db.execute(
        select(Workspace).where(Workspace.workspace_id == workspace_id)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    return ws


# ── GET /api/workspaces ──

@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces(db: AsyncSession = Depends(get_db)):
    """List all workspaces."""
    result = await db.execute(
        select(Workspace)
        .where(Workspace.status == "active")
        .order_by(Workspace.created_at.asc())
    )
    workspaces = list(result.scalars())

    # Refresh claim counts from actual data
    items = []
    for ws in workspaces:
        med_count = (await db.execute(
            select(func.count()).select_from(MedicalClaim)
            .where(MedicalClaim.workspace_id == ws.id)
        )).scalar() or 0
        rx_count = (await db.execute(
            select(func.count()).select_from(PharmacyClaim)
            .where(PharmacyClaim.workspace_id == ws.id)
        )).scalar() or 0

        items.append(WorkspaceSummary(
            workspace_id=ws.workspace_id,
            name=ws.name,
            client_name=ws.client_name,
            description=ws.description,
            data_source=ws.data_source,
            status=ws.status,
            claim_count=med_count + rx_count,
            created_at=str(ws.created_at) if ws.created_at else None,
        ))

    return WorkspaceListResponse(workspaces=items, total=len(items))


# ── POST /api/workspaces ──

@router.post("", response_model=WorkspaceSummary, status_code=201)
async def create_workspace(body: WorkspaceCreate, db: AsyncSession = Depends(get_db)):
    """Create a new workspace."""
    ws = Workspace(
        workspace_id=f"ws-{uuid4().hex[:8]}",
        name=body.name,
        client_name=body.client_name,
        description=body.description,
        data_source="upload",
    )
    db.add(ws)
    await db.flush()

    return WorkspaceSummary(
        workspace_id=ws.workspace_id,
        name=ws.name,
        client_name=ws.client_name,
        description=ws.description,
        data_source=ws.data_source,
        status=ws.status,
        claim_count=0,
        created_at=str(ws.created_at) if ws.created_at else None,
    )


# ── GET /api/workspaces/{id} ──

@router.get("/{workspace_id}", response_model=WorkspaceSummary)
async def get_workspace(workspace_id: str, db: AsyncSession = Depends(get_db)):
    """Get workspace detail."""
    ws = await _get_workspace_or_404(workspace_id, db)

    med_count = (await db.execute(
        select(func.count()).select_from(MedicalClaim)
        .where(MedicalClaim.workspace_id == ws.id)
    )).scalar() or 0
    rx_count = (await db.execute(
        select(func.count()).select_from(PharmacyClaim)
        .where(PharmacyClaim.workspace_id == ws.id)
    )).scalar() or 0

    return WorkspaceSummary(
        workspace_id=ws.workspace_id,
        name=ws.name,
        client_name=ws.client_name,
        description=ws.description,
        data_source=ws.data_source,
        status=ws.status,
        claim_count=med_count + rx_count,
        created_at=str(ws.created_at) if ws.created_at else None,
    )


# ── DELETE /api/workspaces/{id} ──

@router.delete("/{workspace_id}", status_code=204)
async def archive_workspace(workspace_id: str, db: AsyncSession = Depends(get_db)):
    """Archive a workspace (soft delete)."""
    ws = await _get_workspace_or_404(workspace_id, db)
    if ws.workspace_id == "ws-default":
        raise HTTPException(status_code=400, detail="Cannot archive the default workspace")
    ws.status = "archived"
    await db.flush()


# ── POST /api/workspaces/{id}/upload/preview ──

@router.post("/{workspace_id}/upload/preview")
async def upload_preview(
    workspace_id: str,
    file: UploadFile = File(...),
    claim_type: str = Form("medical"),
    db: AsyncSession = Depends(get_db),
):
    """Upload a CSV file and get a column-mapping preview."""
    await _get_workspace_or_404(workspace_id, db)

    content = await file.read()
    service = UploadService(db)
    preview = await service.preview_csv(content, claim_type)
    return preview.to_dict()


# ── POST /api/workspaces/{id}/upload/ingest ──

@router.post("/{workspace_id}/upload/ingest")
async def upload_ingest(
    workspace_id: str,
    file: UploadFile = File(...),
    claim_type: str = Form("medical"),
    mapping: str = Form(...),  # JSON string of mapping dict
    db: AsyncSession = Depends(get_db),
):
    """Ingest CSV data using the confirmed column mapping."""
    ws = await _get_workspace_or_404(workspace_id, db)

    import json
    try:
        mapping_dict = json.loads(mapping)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid mapping JSON")

    content = await file.read()
    service = UploadService(db)

    if claim_type == "medical":
        result = await service.ingest_medical(ws, content, mapping_dict)
    elif claim_type == "pharmacy":
        result = await service.ingest_pharmacy(ws, content, mapping_dict)
    else:
        raise HTTPException(status_code=422, detail="claim_type must be 'medical' or 'pharmacy'")

    return result.to_dict()
