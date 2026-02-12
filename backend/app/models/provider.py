from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    npi: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    specialty: Mapped[str] = mapped_column(String(100))
    taxonomy_code: Mapped[str | None] = mapped_column(String(20))
    practice_address: Mapped[str | None] = mapped_column(String(300))
    practice_city: Mapped[str | None] = mapped_column(String(100))
    practice_state: Mapped[str] = mapped_column(String(2))
    practice_zip: Mapped[str | None] = mapped_column(String(10))
    phone: Mapped[str | None] = mapped_column(String(20))
    entity_type: Mapped[str] = mapped_column(String(20))  # "individual" | "organization"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    oig_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    dea_registration: Mapped[str | None] = mapped_column(String(20))
    dea_schedule: Mapped[str | None] = mapped_column(String(10))
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Pharmacy(Base):
    __tablename__ = "pharmacies"

    id: Mapped[int] = mapped_column(primary_key=True)
    npi: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    chain_name: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str] = mapped_column(String(300))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    zip_code: Mapped[str] = mapped_column(String(10))
    phone: Mapped[str | None] = mapped_column(String(20))
    pharmacy_type: Mapped[str] = mapped_column(String(20))  # "retail" | "mail_order" | "specialty" | "compounding"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    oig_excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
