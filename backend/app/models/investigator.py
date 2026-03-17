from datetime import datetime

from sqlalchemy import String, DateTime, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Investigator(Base):
    __tablename__ = "investigators"

    id: Mapped[int] = mapped_column(primary_key=True)
    investigator_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    specialty: Mapped[str] = mapped_column(String(30), default="both")
    # "medical" | "pharmacy" | "both"
    seniority: Mapped[str] = mapped_column(String(20), default="standard")
    # "junior" | "standard" | "senior"
    max_caseload: Mapped[int] = mapped_column(Integer, default=20)
    is_available: Mapped[bool] = mapped_column(default=True)
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspaces.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
