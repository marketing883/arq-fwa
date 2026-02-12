"""
TAO SQLAlchemy models — lineage graph, capability tokens, trust profiles,
HITL requests, and attested audit receipts.
"""

from datetime import datetime

from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, Index, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ── Lineage Graph ────────────────────────────────────────────────────────────

class LineageNode(Base):
    """A single processing event in the lineage DAG."""
    __tablename__ = "lineage_node"

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    node_type: Mapped[str] = mapped_column(String(30), index=True)
    agent_id: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(500))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    trust_score_at_action: Mapped[float | None] = mapped_column(Float, nullable=True)
    capability_token_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workspace_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_lineage_node_agent_created", "agent_id", "created_at"),
    )


class LineageEdge(Base):
    """A causal/data-flow dependency between two lineage nodes."""
    __tablename__ = "lineage_edge"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_node_id: Mapped[str] = mapped_column(String(36), index=True)
    target_node_id: Mapped[str] = mapped_column(String(36), index=True)
    relationship: Mapped[str] = mapped_column(String(30))  # produced, consumed, triggered, overrode, escalated_to
    data_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_lineage_edge_source_target", "source_node_id", "target_node_id"),
    )


# ── Capability Tokens ────────────────────────────────────────────────────────

class CapabilityToken(Base):
    """Ephemeral, scoped authorization token for agent actions."""
    __tablename__ = "capability_token"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    issuer: Mapped[str] = mapped_column(String(100))
    subject_agent_id: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(100))
    resource_scope: Mapped[dict] = mapped_column(JSONB, default=dict)
    constraints: Mapped[dict] = mapped_column(JSONB, default=dict)
    issued_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    max_uses: Mapped[int] = mapped_column(Integer, default=1)
    uses_remaining: Mapped[int] = mapped_column(Integer, default=1)
    parent_token_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    signature: Mapped[str] = mapped_column(String(128))


# ── Agent Trust Profiles ─────────────────────────────────────────────────────

class AgentTrustProfile(Base):
    """Dynamic trust score and escalation state for an agent."""
    __tablename__ = "agent_trust_profile"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    trust_score: Mapped[float] = mapped_column(Float, default=0.7)
    initial_trust: Mapped[float] = mapped_column(Float, default=0.7)
    decay_model: Mapped[str] = mapped_column(String(20), default="exponential")
    decay_rate: Mapped[float] = mapped_column(Float, default=0.01)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    escalation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_successful_action: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_trust_update: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    trust_history: Mapped[dict] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── HITL Requests ────────────────────────────────────────────────────────────

class HITLRequest(Base):
    """Human-in-the-loop approval request for high-risk agent actions."""
    __tablename__ = "hitl_request"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    agent_id: Mapped[str] = mapped_column(String(100), index=True)
    requested_action: Mapped[str] = mapped_column(String(100))
    resource_scope: Mapped[dict] = mapped_column(JSONB, default=dict)
    action_risk_score: Mapped[float] = mapped_column(Float)
    risk_tier: Mapped[str] = mapped_column(String(20))
    agent_trust_score: Mapped[float] = mapped_column(Float)
    justification: Mapped[str] = mapped_column(Text)
    contributing_factors: Mapped[dict] = mapped_column(JSONB, default=list)
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reviewer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


# ── Attested Audit Receipts ──────────────────────────────────────────────────

class AuditReceipt(Base):
    """Cryptographically attested, tamper-evident audit receipt."""
    __tablename__ = "audit_receipt"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    lineage_node_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(100))
    agent_id: Mapped[str] = mapped_column(String(100), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Input / output attestation
    input_data_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_data_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_summary: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Authorization attestation
    capability_token_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    token_scope_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    hitl_request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Risk attestation
    action_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    agent_trust_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Evidence payload
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Integrity chain
    previous_receipt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receipt_hash: Mapped[str] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(String(128))
