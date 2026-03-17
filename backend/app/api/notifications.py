"""
Notifications API — in-app notifications with SSE real-time streaming.
"""

import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.auth.permissions import Permission
from app.auth.context import RequestContext
from app.config import settings
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class NotificationResponse(BaseModel):
    notification_id: str
    recipient: str
    notification_type: str
    title: str
    body: str
    resource_type: str | None
    resource_id: str | None
    is_read: bool
    created_at: str | None
    read_at: str | None


class PreferencesUpdate(BaseModel):
    preferences: dict


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("")
async def list_notifications(
    is_read: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: RequestContext = Depends(require(Permission.CASES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """List notifications for current user."""
    svc = NotificationService(db)
    notifications = await svc.get_notifications(
        ctx.user_id, is_read=is_read, limit=limit, offset=offset
    )

    return {
        "notifications": [
            NotificationResponse(
                notification_id=n.notification_id,
                recipient=n.recipient,
                notification_type=n.notification_type,
                title=n.title,
                body=n.body,
                resource_type=n.resource_type,
                resource_id=n.resource_id,
                is_read=n.is_read,
                created_at=str(n.created_at) if n.created_at else None,
                read_at=str(n.read_at) if n.read_at else None,
            )
            for n in notifications
        ],
        "total": len(notifications),
    }


@router.get("/unread-count")
async def get_unread_count(
    ctx: RequestContext = Depends(require(Permission.CASES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Get unread notification count."""
    svc = NotificationService(db)
    count = await svc.get_unread_count(ctx.user_id)
    return {"unread_count": count}


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    ctx: RequestContext = Depends(require(Permission.CASES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    svc = NotificationService(db)
    success = await svc.mark_read(notification_id, ctx.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "ok"}


@router.put("/mark-all-read")
async def mark_all_read(
    ctx: RequestContext = Depends(require(Permission.CASES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read."""
    svc = NotificationService(db)
    count = await svc.mark_all_read(ctx.user_id)
    return {"marked_read": count}


@router.get("/stream")
async def notification_stream(
    ctx: RequestContext = Depends(require(Permission.CASES_READ)),
):
    """SSE endpoint for real-time notifications."""
    recipient = ctx.user_id

    async def generate():
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"notifications:{recipient}")
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=30
                )
                if message and message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
                else:
                    yield ": keepalive\n\n"
        finally:
            await pubsub.unsubscribe()
            await r.aclose()

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/preferences")
async def get_preferences(
    ctx: RequestContext = Depends(require(Permission.CASES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Get notification preferences."""
    from sqlalchemy import select
    from app.models.notification import NotificationPreference

    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.recipient == ctx.user_id
        )
    )
    pref = result.scalar_one_or_none()

    default_prefs = {
        "case_assigned": {"in_app": True, "email": False},
        "case_status_changed": {"in_app": True, "email": False},
        "sla_warning": {"in_app": True, "email": True},
        "sla_breached": {"in_app": True, "email": True},
        "case_escalated": {"in_app": True, "email": False},
        "pipeline_completed": {"in_app": True, "email": False},
    }

    return {"preferences": pref.preferences if pref else default_prefs}


@router.put("/preferences")
async def update_preferences(
    body: PreferencesUpdate,
    ctx: RequestContext = Depends(require(Permission.CASES_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Update notification preferences."""
    from sqlalchemy import select
    from app.models.notification import NotificationPreference

    result = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.recipient == ctx.user_id
        )
    )
    pref = result.scalar_one_or_none()

    if pref:
        pref.preferences = body.preferences
    else:
        pref = NotificationPreference(
            recipient=ctx.user_id, preferences=body.preferences
        )
        db.add(pref)

    await db.flush()
    return {"preferences": pref.preferences}
