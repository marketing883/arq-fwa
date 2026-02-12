"""
CAPC SQLAlchemy models — compiled IR records and evidence packets.
"""

from datetime import datetime

from sqlalchemy import String, Float, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ComplianceIRRecord(Base):
    """Persisted record of a compiled Compliance IR."""
    __tablename__ = "compliance_ir_record"

    id: Mapped[int] = mapped_column(primary_key=True)
    ir_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    original_request: Mapped[str] = mapped_column(Text)
    parsed_intents: Mapped[dict] = mapped_column(JSONB, default=list)
    parsed_entities: Mapped[dict] = mapped_column(JSONB, default=list)
    sensitivity_level: Mapped[str] = mapped_column(String(30))
    opcodes: Mapped[dict] = mapped_column(JSONB, default=list)
    edges: Mapped[dict] = mapped_column(JSONB, default=list)
    validation_status: Mapped[str] = mapped_column(String(20), default="pending")
    validation_errors: Mapped[dict] = mapped_column(JSONB, default=list)
    runtime_checks_attached: Mapped[dict] = mapped_column(JSONB, default=list)
    agent_id: Mapped[str] = mapped_column(String(100), index=True)
    workspace_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EvidencePacket(Base):
    """Signed evidence packet for compliance audit."""
    __tablename__ = "evidence_packet"

    id: Mapped[int] = mapped_column(primary_key=True)
    packet_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    ir_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    original_request: Mapped[str] = mapped_column(Text)
    compiled_ir: Mapped[dict] = mapped_column(JSONB, default=dict)
    policy_decisions: Mapped[dict] = mapped_column(JSONB, default=list)
    preconditions: Mapped[dict] = mapped_column(JSONB, default=list)
    approvals: Mapped[dict] = mapped_column(JSONB, default=list)
    lineage_hashes: Mapped[dict] = mapped_column(JSONB, default=list)
    model_tool_versions: Mapped[dict] = mapped_column(JSONB, default=dict)
    results: Mapped[dict] = mapped_column(JSONB, default=dict)
    exception_action: Mapped[str | None] = mapped_column(String(30), nullable=True)
    previous_packet_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    packet_hash: Mapped[str] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
