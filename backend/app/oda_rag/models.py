"""
ODA-RAG SQLAlchemy models — RAG signals, adaptation events, and feedback.
"""

from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RAGSignal(Base):
    """A single observability signal from the RAG pipeline."""
    __tablename__ = "rag_signal"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    signal_type: Mapped[str] = mapped_column(String(30), index=True)
    metric_name: Mapped[str] = mapped_column(String(100), index=True)
    metric_value: Mapped[float] = mapped_column(Float)
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    workspace_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class AdaptationEvent(Base):
    """Record of an adaptation action taken by the controller."""
    __tablename__ = "adaptation_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    trigger_signal_ids: Mapped[dict] = mapped_column(JSONB, default=list)
    drift_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    action_type: Mapped[str] = mapped_column(String(50), index=True)
    parameters_before: Mapped[dict] = mapped_column(JSONB, default=dict)
    parameters_after: Mapped[dict] = mapped_column(JSONB, default=dict)
    reason: Mapped[str] = mapped_column(Text)
    workspace_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RAGFeedback(Base):
    """User feedback on RAG response quality."""
    __tablename__ = "rag_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    feedback_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    query: Mapped[str] = mapped_column(Text)
    response_quality: Mapped[float] = mapped_column(Float)  # 0.0-1.0
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback_source: Mapped[str] = mapped_column(String(30))  # explicit, implicit
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    workspace_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
