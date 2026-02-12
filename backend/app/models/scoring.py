from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, Integer, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    claim_type: Mapped[str] = mapped_column(String(20))
    total_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    risk_level: Mapped[str] = mapped_column(String(10), index=True)  # "low" | "medium" | "high" | "critical"
    rules_triggered: Mapped[int] = mapped_column(Integer, default=0)
    rule_contributions: Mapped[dict] = mapped_column(JSONB, default=dict)
    confidence_factor: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    scored_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    batch_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
