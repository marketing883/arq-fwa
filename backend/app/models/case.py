from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, Integer, Numeric, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvestigationCase(Base):
    __tablename__ = "investigation_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    claim_id: Mapped[str] = mapped_column(String(30), index=True)
    claim_type: Mapped[str] = mapped_column(String(20))
    risk_score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    risk_level: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    priority: Mapped[str] = mapped_column(String(5), index=True)  # "P1" | "P2" | "P3" | "P4"
    assigned_to: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolution_path: Mapped[str | None] = mapped_column(String(30), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    estimated_fraud_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    recovery_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    notes: Mapped[list["CaseNote"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    evidence: Mapped[list["CaseEvidence"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class CaseNote(Base):
    __tablename__ = "case_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("investigation_cases.id"), index=True)
    author: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(String(5000))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    case: Mapped["InvestigationCase"] = relationship(back_populates="notes")


class CaseEvidence(Base):
    __tablename__ = "case_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("investigation_cases.id"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    case: Mapped["InvestigationCase"] = relationship(back_populates="evidence")
