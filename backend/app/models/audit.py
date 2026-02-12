from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(30), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(500))
    resource_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
