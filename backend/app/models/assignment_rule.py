from datetime import datetime

from sqlalchemy import String, DateTime, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AssignmentRule(Base):
    __tablename__ = "assignment_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    # Lower number = higher priority. Rules evaluated in priority order.
    conditions: Mapped[dict] = mapped_column(JSONB, default=dict)
    # {"case_priority": ["P1"], "claim_type": ["pharmacy"], "risk_level": ["critical"]}
    strategy: Mapped[str] = mapped_column(String(30), default="round_robin")
    # "round_robin" | "workload_balanced" | "skill_matched"
    target_filter: Mapped[dict] = mapped_column(JSONB, default=dict)
    # {"seniority": ["senior"], "specialty": ["pharmacy"]}
    is_enabled: Mapped[bool] = mapped_column(default=True)
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
