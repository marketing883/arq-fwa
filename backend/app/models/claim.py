from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import String, Date, Boolean, DateTime, Integer, Numeric, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MedicalClaim(Base):
    __tablename__ = "medical_claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True)
    referring_provider_id: Mapped[int | None] = mapped_column(ForeignKey("providers.id"), nullable=True)
    service_date: Mapped[date] = mapped_column(Date, index=True)
    admission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    discharge_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    place_of_service: Mapped[str] = mapped_column(String(5))
    claim_type: Mapped[str] = mapped_column(String(20))  # "professional" | "institutional" | "dental"
    cpt_code: Mapped[str] = mapped_column(String(10), index=True)
    cpt_modifier: Mapped[str | None] = mapped_column(String(10), nullable=True)
    diagnosis_code_primary: Mapped[str] = mapped_column(String(10), index=True)
    diagnosis_code_2: Mapped[str | None] = mapped_column(String(10), nullable=True)
    diagnosis_code_3: Mapped[str | None] = mapped_column(String(10), nullable=True)
    diagnosis_code_4: Mapped[str | None] = mapped_column(String(10), nullable=True)
    amount_billed: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    amount_allowed: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount_paid: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    units: Mapped[int] = mapped_column(Integer, default=1)
    length_of_stay: Mapped[int | None] = mapped_column(Integer, nullable=True)
    drg_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    revenue_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="received")
    batch_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    member: Mapped["Member"] = relationship(foreign_keys=[member_id])
    provider: Mapped["Provider"] = relationship(foreign_keys=[provider_id])
    referring_provider: Mapped["Provider | None"] = relationship(foreign_keys=[referring_provider_id])


class PharmacyClaim(Base):
    __tablename__ = "pharmacy_claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    pharmacy_id: Mapped[int] = mapped_column(ForeignKey("pharmacies.id"), index=True)
    prescriber_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True)
    fill_date: Mapped[date] = mapped_column(Date, index=True)
    ndc_code: Mapped[str] = mapped_column(String(15), index=True)
    drug_name: Mapped[str] = mapped_column(String(200))
    drug_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_generic: Mapped[bool] = mapped_column(Boolean, default=False)
    is_controlled: Mapped[bool] = mapped_column(Boolean, default=False)
    dea_schedule: Mapped[str | None] = mapped_column(String(5), nullable=True)
    quantity_dispensed: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    days_supply: Mapped[int] = mapped_column(Integer)
    refill_number: Mapped[int] = mapped_column(Integer, default=0)
    amount_billed: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    amount_allowed: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount_paid: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    copay: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    prescriber_npi: Mapped[str] = mapped_column(String(10))
    pharmacy_npi: Mapped[str] = mapped_column(String(10))
    prior_auth: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="received")
    batch_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    member: Mapped["Member"] = relationship(foreign_keys=[member_id])
    pharmacy: Mapped["Pharmacy"] = relationship(foreign_keys=[pharmacy_id])
    prescriber: Mapped["Provider"] = relationship(foreign_keys=[prescriber_id])


# Needed for relationship resolution
from app.models.member import Member  # noqa: E402, F811
from app.models.provider import Provider, Pharmacy  # noqa: E402, F811
