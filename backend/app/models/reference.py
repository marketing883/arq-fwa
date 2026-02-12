from decimal import Decimal

from sqlalchemy import String, Boolean, Integer, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NDCReference(Base):
    """National Drug Code directory"""
    __tablename__ = "ndc_reference"

    id: Mapped[int] = mapped_column(primary_key=True)
    ndc_code: Mapped[str] = mapped_column(String(15), unique=True, index=True)
    proprietary_name: Mapped[str] = mapped_column(String(200))
    nonproprietary_name: Mapped[str] = mapped_column(String(200))
    dosage_form: Mapped[str] = mapped_column(String(50))
    route: Mapped[str] = mapped_column(String(50))
    substance_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    dea_schedule: Mapped[str | None] = mapped_column(String(5), nullable=True)
    therapeutic_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avg_wholesale_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    generic_available: Mapped[bool] = mapped_column(default=False)
    generic_ndc: Mapped[str | None] = mapped_column(String(15), nullable=True)
    generic_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)


class CPTReference(Base):
    """CPT/HCPCS code reference with CMS fee schedule benchmarks"""
    __tablename__ = "cpt_reference"

    id: Mapped[int] = mapped_column(primary_key=True)
    cpt_code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(50))
    facility_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    non_facility_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    rvu_work: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    rvu_practice: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    rvu_malpractice: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    global_period: Mapped[str | None] = mapped_column(String(5), nullable=True)
    bundled_codes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_outpatient_typical: Mapped[bool] = mapped_column(default=False)
    is_lab_diagnostic: Mapped[bool] = mapped_column(default=False)
    is_dme: Mapped[bool] = mapped_column(default=False)


class ICDReference(Base):
    """ICD-10-CM diagnosis code reference"""
    __tablename__ = "icd_reference"

    id: Mapped[int] = mapped_column(primary_key=True)
    icd_code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(100))
    is_billable: Mapped[bool] = mapped_column(default=True)
    valid_cpt_codes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    gender_specific: Mapped[str | None] = mapped_column(String(1), nullable=True)
    age_range_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_range_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
