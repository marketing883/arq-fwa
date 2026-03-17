from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    notification_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    recipient: Mapped[str] = mapped_column(String(100), index=True)
    notification_type: Mapped[str] = mapped_column(String(30), index=True)
    # "case_assigned" | "case_status_changed" | "sla_warning" | "sla_breached"
    # "case_resolved" | "pipeline_completed" | "case_escalated"
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(2000))
    resource_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_read: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
