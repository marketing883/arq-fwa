"""
Notification Service — in-app notifications with Redis pub/sub for real-time SSE.
"""

import json
import logging
from uuid import uuid4

import redis.asyncio as aioredis
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.notification import Notification, NotificationPreference
from app.models.case import InvestigationCase

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def notify(
        self,
        recipient: str,
        notification_type: str,
        title: str,
        body: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> Notification:
        """Create an in-app notification and publish to Redis SSE channel."""
        notification = Notification(
            notification_id=str(uuid4()),
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            body=body,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        self.db.add(notification)
        await self.db.flush()

        # Publish to Redis pub/sub for real-time SSE delivery
        try:
            r = aioredis.from_url(settings.redis_url, decode_responses=True)
            await r.publish(
                f"notifications:{recipient}",
                json.dumps(
                    {
                        "notification_id": notification.notification_id,
                        "type": notification_type,
                        "title": title,
                        "body": body,
                        "resource_type": resource_type,
                        "resource_id": resource_id,
                        "created_at": notification.created_at.isoformat()
                        if notification.created_at
                        else None,
                    }
                ),
            )
            await r.aclose()
        except Exception as exc:
            logger.warning("Failed to publish notification to Redis: %s", exc)

        return notification

    async def notify_case_assigned(
        self, case: InvestigationCase, assignee: str, assigner: str
    ):
        await self.notify(
            recipient=assignee,
            notification_type="case_assigned",
            title=f"Case {case.case_id} assigned to you",
            body=f"{assigner} assigned {case.risk_level} risk case ({case.priority}) for claim {case.claim_id}",
            resource_type="case",
            resource_id=case.case_id,
        )

    async def notify_case_status_changed(
        self, case: InvestigationCase, old_status: str, actor: str
    ):
        if case.assigned_to:
            await self.notify(
                recipient=case.assigned_to,
                notification_type="case_status_changed",
                title=f"Case {case.case_id}: {old_status} -> {case.status}",
                body=f"{actor} changed status from {old_status} to {case.status}",
                resource_type="case",
                resource_id=case.case_id,
            )

    async def notify_sla_warning(self, case: InvestigationCase):
        if case.assigned_to:
            await self.notify(
                recipient=case.assigned_to,
                notification_type="sla_warning",
                title=f"SLA warning: Case {case.case_id}",
                body=f"Case {case.case_id} ({case.priority}) SLA deadline approaching in 24 hours",
                resource_type="case",
                resource_id=case.case_id,
            )

    async def notify_sla_breached(self, case: InvestigationCase):
        if case.assigned_to:
            await self.notify(
                recipient=case.assigned_to,
                notification_type="sla_breached",
                title=f"SLA BREACHED: Case {case.case_id}",
                body=f"Case {case.case_id} ({case.priority}) has exceeded its SLA deadline",
                resource_type="case",
                resource_id=case.case_id,
            )

    async def notify_case_escalated(
        self, case: InvestigationCase, reason: str, actor: str
    ):
        if case.assigned_to:
            await self.notify(
                recipient=case.assigned_to,
                notification_type="case_escalated",
                title=f"Case {case.case_id} escalated",
                body=f"{actor} escalated case: {reason}",
                resource_type="case",
                resource_id=case.case_id,
            )

    async def notify_pipeline_completed(
        self, run_stats: dict, workspace_id: int | None
    ):
        """Notify about pipeline completion with summary stats."""
        cases_created = run_stats.get("cases_created", 0)
        if cases_created > 0:
            # Notify all available investigators in the workspace
            from app.models.investigator import Investigator
            from sqlalchemy import or_

            conditions = [Investigator.is_available == True]
            if workspace_id is not None:
                conditions.append(
                    or_(
                        Investigator.workspace_id == workspace_id,
                        Investigator.workspace_id.is_(None),
                    )
                )

            result = await self.db.execute(
                select(Investigator).where(and_(*conditions))
            )
            for inv in result.scalars():
                await self.notify(
                    recipient=inv.name,
                    notification_type="pipeline_completed",
                    title=f"Pipeline completed: {cases_created} new cases",
                    body=f"Pipeline processed {run_stats.get('total_claims', 0)} claims, created {cases_created} investigation cases",
                    resource_type="pipeline",
                    resource_id=run_stats.get("batch_id"),
                )

    async def get_unread_count(self, recipient: str) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                and_(
                    Notification.recipient == recipient,
                    Notification.is_read == False,
                )
            )
        )
        return result.scalar() or 0

    async def get_notifications(
        self,
        recipient: str,
        *,
        is_read: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Notification]:
        conditions = [Notification.recipient == recipient]
        if is_read is not None:
            conditions.append(Notification.is_read == is_read)

        result = await self.db.execute(
            select(Notification)
            .where(and_(*conditions))
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars())

    async def mark_read(self, notification_id: str, recipient: str) -> bool:
        from datetime import datetime

        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.notification_id == notification_id,
                    Notification.recipient == recipient,
                )
            )
        )
        notification = result.scalar_one_or_none()
        if not notification:
            return False

        notification.is_read = True
        notification.read_at = datetime.utcnow()
        return True

    async def mark_all_read(self, recipient: str) -> int:
        from datetime import datetime

        result = await self.db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.recipient == recipient,
                    Notification.is_read == False,
                )
            )
            .values(is_read=True, read_at=datetime.utcnow())
        )
        return result.rowcount
