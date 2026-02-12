from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Boolean, DateTime, Integer, Numeric, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(50))
    fraud_type: Mapped[str] = mapped_column(String(20))  # "Fraud" | "Waste" | "Abuse"
    claim_type: Mapped[str] = mapped_column(String(20))  # "medical" | "pharmacy"
    description: Mapped[str] = mapped_column(String(500))
    detection_logic: Mapped[str] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[Decimal] = mapped_column(Numeric(4, 1))
    thresholds: Mapped[dict] = mapped_column(JSONB, default=dict)
    benchmark_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    implementation_priority: Mapped[str] = mapped_column(String(10))  # "HIGH" | "MEDIUM" | "LOW"
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_modified_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class RuleResult(Base):
    __tablename__ = "rule_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(30), index=True)
    claim_type: Mapped[str] = mapped_column(String(20))
    rule_id: Mapped[str] = mapped_column(String(10), index=True)
    triggered: Mapped[bool] = mapped_column(Boolean)
    severity: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    details: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True, index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    batch_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
