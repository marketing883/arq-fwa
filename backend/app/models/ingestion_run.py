from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    data_source_id: Mapped[int] = mapped_column(
        ForeignKey("data_sources.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="running")
    # "running" | "completed" | "failed" | "no_data"
    rows_found: Mapped[int] = mapped_column(Integer, default=0)
    rows_ingested: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pipeline_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
