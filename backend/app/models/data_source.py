from datetime import datetime

from sqlalchemy import String, DateTime, Integer, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(30))
    # "watched_folder" | "api_endpoint" | "database_query"
    claim_type: Mapped[str] = mapped_column(String(20))
    # "medical" | "pharmacy"
    connection_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    field_mapping: Mapped[dict] = mapped_column(JSONB, default=dict)
    polling_interval_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    auto_run_pipeline: Mapped[bool] = mapped_column(default=True)
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id"), nullable=True, index=True
    )
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_watermark: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
