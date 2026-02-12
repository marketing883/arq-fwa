"""
Data Enrichment Pipeline (Phase 4)

After claims are in the DB, enrich them with reference lookups,
provider/member context, and historical patterns needed by the rule engine.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MedicalClaim, PharmacyClaim, Provider, Pharmacy, Member,
    CPTReference, ICDReference, NDCReference,
)


@dataclass
class EnrichedMedicalClaim:
    """Medical claim with all enrichment data attached."""
    # Original claim fields
    claim_id: str
    member_id: int
    provider_id: int
    referring_provider_id: int | None
    service_date: date
    place_of_service: str
    claim_type: str
    cpt_code: str
    cpt_modifier: str | None
    diagnosis_code_primary: str
    diagnosis_code_2: str | None
    diagnosis_code_3: str | None
    diagnosis_code_4: str | None
    amount_billed: Decimal
    amount_allowed: Decimal | None
    amount_paid: Decimal | None
    units: int
    length_of_stay: int | None
    drg_code: str | None
    plan_id: str | None
    status: str
    batch_id: str | None

    # CPT enrichment
    cpt_description: str | None = None
    cpt_category: str | None = None
    cpt_facility_price: Decimal | None = None
    cpt_non_facility_price: Decimal | None = None
    cpt_is_outpatient_typical: bool = False
    cpt_is_lab_diagnostic: bool = False
    cpt_is_dme: bool = False
    cpt_bundled_codes: dict | None = None

    # ICD enrichment
    icd_description: str | None = None
    icd_valid_cpt_codes: list[str] = field(default_factory=list)
    icd_gender_specific: str | None = None
    icd_age_range_min: int | None = None
    icd_age_range_max: int | None = None

    # Provider enrichment
    provider_npi: str | None = None
    provider_name: str | None = None
    provider_specialty: str | None = None
    provider_is_active: bool = True
    provider_oig_excluded: bool = False
    provider_entity_type: str | None = None

    # Referring provider enrichment
    referring_provider_npi: str | None = None

    # Member enrichment
    member_member_id: str | None = None
    member_gender: str | None = None
    member_age: int | None = None
    member_plan_type: str | None = None
    member_is_active: bool = True
    member_eligibility_end: date | None = None

    # Historical context
    member_claims_30d: int = 0
    member_claims_90d: int = 0
    member_total_billed_30d: Decimal = Decimal("0")
    provider_claims_30d: int = 0
    provider_total_claims: int = 0
    duplicate_claim_ids: list[str] = field(default_factory=list)

    # Provider pattern stats
    provider_modifier_25_rate: float = 0.0
    provider_modifier_59_rate: float = 0.0
    provider_copay_waiver_rate: float = 0.0
    provider_lab_order_rate: float = 0.0
    provider_telehealth_per_day_max: int = 0
    provider_avg_diagnosis_codes: float = 0.0
    provider_referral_concentration: float = 0.0
    provider_top_referral_target: int | None = None

    # Diagnosis code count
    diagnosis_code_count: int = 1

    # Same-visit CPT codes (for unbundling detection)
    same_visit_other_cpt_codes: list[str] = field(default_factory=list)


@dataclass
class EnrichedPharmacyClaim:
    """Pharmacy claim with all enrichment data attached."""
    # Original
    claim_id: str
    member_id: int
    pharmacy_id: int
    prescriber_id: int
    fill_date: date
    ndc_code: str
    drug_name: str
    drug_class: str | None
    is_generic: bool
    is_controlled: bool
    dea_schedule: str | None
    quantity_dispensed: Decimal
    days_supply: int
    refill_number: int
    amount_billed: Decimal
    amount_allowed: Decimal | None
    amount_paid: Decimal | None
    copay: Decimal | None
    prescriber_npi: str
    pharmacy_npi: str
    prior_auth: bool
    status: str
    batch_id: str | None

    # NDC enrichment
    ndc_proprietary_name: str | None = None
    ndc_nonproprietary_name: str | None = None
    ndc_dea_schedule: str | None = None
    ndc_therapeutic_class: str | None = None
    ndc_avg_wholesale_price: Decimal | None = None
    ndc_generic_available: bool = False
    ndc_generic_price: Decimal | None = None

    # Prescriber enrichment
    prescriber_name: str | None = None
    prescriber_specialty: str | None = None
    prescriber_is_active: bool = True
    prescriber_oig_excluded: bool = False
    prescriber_dea_registration: str | None = None
    prescriber_dea_schedule: str | None = None
    prescriber_exists: bool = True

    # Pharmacy enrichment
    pharmacy_name: str | None = None
    pharmacy_type: str | None = None
    pharmacy_is_active: bool = True

    # Member enrichment
    member_member_id: str | None = None
    member_gender: str | None = None
    member_age: int | None = None
    member_is_active: bool = True
    member_eligibility_end: date | None = None

    # Historical context
    days_since_last_fill: int | None = None
    last_fill_days_supply: int | None = None
    member_medical_claims_180d: int = 0
    member_unique_prescribers_90d: int = 0
    member_unique_pharmacies_60d: int = 0
    member_cumulative_supply_90d: int = 0
    prescriber_controlled_pct: float = 0.0
    prescriber_total_rx: int = 0
    prescriber_pharmacy_concentration: float = 0.0
    prescriber_top_pharmacy_id: int | None = None
    pharmacy_prescriber_pair_count: int = 0
    pharmacy_prescriber_mean: float = 0.0
    pharmacy_prescriber_std: float = 0.0


class EnrichmentService:
    """Enriches claims with reference data, provider/member context, and historical patterns."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._cpt_cache: dict[str, CPTReference] = {}
        self._icd_cache: dict[str, ICDReference] = {}
        self._ndc_cache: dict[str, NDCReference] = {}
        self._provider_cache: dict[int, Provider] = {}
        self._pharmacy_cache: dict[int, Pharmacy] = {}
        self._member_cache: dict[int, Member] = {}

    async def _warm_caches(self) -> None:
        """Load all reference data into memory for fast lookups."""
        result = await self.session.execute(select(CPTReference))
        for row in result.scalars():
            self._cpt_cache[row.cpt_code] = row

        result = await self.session.execute(select(ICDReference))
        for row in result.scalars():
            self._icd_cache[row.icd_code] = row

        result = await self.session.execute(select(NDCReference))
        for row in result.scalars():
            self._ndc_cache[row.ndc_code] = row

        result = await self.session.execute(select(Provider))
        for row in result.scalars():
            self._provider_cache[row.id] = row

        result = await self.session.execute(select(Pharmacy))
        for row in result.scalars():
            self._pharmacy_cache[row.id] = row

        result = await self.session.execute(select(Member))
        for row in result.scalars():
            self._member_cache[row.id] = row

    async def enrich_medical_batch(self, claims: list[MedicalClaim]) -> list[EnrichedMedicalClaim]:
        """Enrich a batch of medical claims."""
        if not self._cpt_cache:
            await self._warm_caches()

        # Pre-compute provider-level stats in bulk
        provider_ids = list({c.provider_id for c in claims})
        provider_stats = await self._compute_medical_provider_stats(provider_ids)

        enriched = []
        for claim in claims:
            ec = await self._enrich_single_medical(claim, provider_stats)
            enriched.append(ec)
        return enriched

    async def _enrich_single_medical(
        self, claim: MedicalClaim, provider_stats: dict
    ) -> EnrichedMedicalClaim:
        """Enrich a single medical claim."""
        cpt = self._cpt_cache.get(claim.cpt_code)
        icd = self._icd_cache.get(claim.diagnosis_code_primary)
        provider = self._provider_cache.get(claim.provider_id)
        member = self._member_cache.get(claim.member_id)

        # Count diagnosis codes
        dx_count = 1
        if claim.diagnosis_code_2:
            dx_count += 1
        if claim.diagnosis_code_3:
            dx_count += 1
        if claim.diagnosis_code_4:
            dx_count += 1

        # Member age
        member_age = None
        if member and member.date_of_birth:
            member_age = (claim.service_date - member.date_of_birth).days // 365

        # ICD valid CPT codes
        valid_cpts = []
        if icd and icd.valid_cpt_codes:
            valid_cpts = icd.valid_cpt_codes.get("codes", []) if isinstance(icd.valid_cpt_codes, dict) else []

        # Check for duplicates
        dup_result = await self.session.execute(
            select(MedicalClaim.claim_id).where(
                and_(
                    MedicalClaim.member_id == claim.member_id,
                    MedicalClaim.provider_id == claim.provider_id,
                    MedicalClaim.cpt_code == claim.cpt_code,
                    MedicalClaim.service_date == claim.service_date,
                    MedicalClaim.claim_id != claim.claim_id,
                )
            )
        )
        dup_ids = [r for r in dup_result.scalars()]

        # Same-visit other CPT codes (for unbundling)
        same_visit_q = await self.session.execute(
            select(MedicalClaim.cpt_code).where(
                and_(
                    MedicalClaim.member_id == claim.member_id,
                    MedicalClaim.provider_id == claim.provider_id,
                    MedicalClaim.service_date == claim.service_date,
                    MedicalClaim.claim_id != claim.claim_id,
                )
            )
        )
        same_visit_cpts = [r for r in same_visit_q.scalars()]

        # Member historical
        window_30 = claim.service_date - timedelta(days=30)
        window_90 = claim.service_date - timedelta(days=90)

        mem_30d = await self.session.execute(
            select(func.count()).select_from(MedicalClaim).where(
                and_(MedicalClaim.member_id == claim.member_id,
                     MedicalClaim.service_date >= window_30,
                     MedicalClaim.service_date <= claim.service_date,
                     MedicalClaim.claim_id != claim.claim_id)
            )
        )
        mem_90d = await self.session.execute(
            select(func.count()).select_from(MedicalClaim).where(
                and_(MedicalClaim.member_id == claim.member_id,
                     MedicalClaim.service_date >= window_90,
                     MedicalClaim.service_date <= claim.service_date,
                     MedicalClaim.claim_id != claim.claim_id)
            )
        )
        mem_billed_30d = await self.session.execute(
            select(func.coalesce(func.sum(MedicalClaim.amount_billed), 0)).where(
                and_(MedicalClaim.member_id == claim.member_id,
                     MedicalClaim.service_date >= window_30,
                     MedicalClaim.service_date <= claim.service_date)
            )
        )

        # Provider claims in 30d
        prov_30d = await self.session.execute(
            select(func.count()).select_from(MedicalClaim).where(
                and_(MedicalClaim.provider_id == claim.provider_id,
                     MedicalClaim.service_date >= window_30,
                     MedicalClaim.service_date <= claim.service_date)
            )
        )

        stats = provider_stats.get(claim.provider_id, {})

        return EnrichedMedicalClaim(
            # Original fields
            claim_id=claim.claim_id,
            member_id=claim.member_id,
            provider_id=claim.provider_id,
            referring_provider_id=claim.referring_provider_id,
            service_date=claim.service_date,
            place_of_service=claim.place_of_service,
            claim_type=claim.claim_type,
            cpt_code=claim.cpt_code,
            cpt_modifier=claim.cpt_modifier,
            diagnosis_code_primary=claim.diagnosis_code_primary,
            diagnosis_code_2=claim.diagnosis_code_2,
            diagnosis_code_3=claim.diagnosis_code_3,
            diagnosis_code_4=claim.diagnosis_code_4,
            amount_billed=claim.amount_billed,
            amount_allowed=claim.amount_allowed,
            amount_paid=claim.amount_paid,
            units=claim.units,
            length_of_stay=claim.length_of_stay,
            drg_code=claim.drg_code,
            plan_id=claim.plan_id,
            status=claim.status,
            batch_id=claim.batch_id,
            # CPT
            cpt_description=cpt.description if cpt else None,
            cpt_category=cpt.category if cpt else None,
            cpt_facility_price=cpt.facility_price if cpt else None,
            cpt_non_facility_price=cpt.non_facility_price if cpt else None,
            cpt_is_outpatient_typical=cpt.is_outpatient_typical if cpt else False,
            cpt_is_lab_diagnostic=cpt.is_lab_diagnostic if cpt else False,
            cpt_is_dme=cpt.is_dme if cpt else False,
            cpt_bundled_codes=cpt.bundled_codes if cpt else None,
            # ICD
            icd_description=icd.description if icd else None,
            icd_valid_cpt_codes=valid_cpts,
            icd_gender_specific=icd.gender_specific if icd else None,
            icd_age_range_min=icd.age_range_min if icd else None,
            icd_age_range_max=icd.age_range_max if icd else None,
            # Provider
            provider_npi=provider.npi if provider else None,
            provider_name=provider.name if provider else None,
            provider_specialty=provider.specialty if provider else None,
            provider_is_active=provider.is_active if provider else True,
            provider_oig_excluded=provider.oig_excluded if provider else False,
            provider_entity_type=provider.entity_type if provider else None,
            # Referring
            referring_provider_npi=(
                self._provider_cache[claim.referring_provider_id].npi
                if claim.referring_provider_id and claim.referring_provider_id in self._provider_cache
                else None
            ),
            # Member
            member_member_id=member.member_id if member else None,
            member_gender=member.gender if member else None,
            member_age=member_age,
            member_plan_type=member.plan_type if member else None,
            member_is_active=member.is_active if member else True,
            member_eligibility_end=member.eligibility_end if member else None,
            # Historical
            member_claims_30d=mem_30d.scalar() or 0,
            member_claims_90d=mem_90d.scalar() or 0,
            member_total_billed_30d=Decimal(str(mem_billed_30d.scalar() or 0)),
            provider_claims_30d=prov_30d.scalar() or 0,
            provider_total_claims=stats.get("total_claims", 0),
            duplicate_claim_ids=dup_ids,
            # Provider stats
            provider_modifier_25_rate=stats.get("modifier_25_rate", 0.0),
            provider_modifier_59_rate=stats.get("modifier_59_rate", 0.0),
            provider_copay_waiver_rate=stats.get("copay_waiver_rate", 0.0),
            provider_lab_order_rate=stats.get("lab_order_rate", 0.0),
            provider_telehealth_per_day_max=stats.get("telehealth_per_day_max", 0),
            provider_avg_diagnosis_codes=stats.get("avg_diagnosis_codes", 0.0),
            provider_referral_concentration=stats.get("referral_concentration", 0.0),
            provider_top_referral_target=stats.get("top_referral_target"),
            diagnosis_code_count=dx_count,
            same_visit_other_cpt_codes=same_visit_cpts,
        )

    async def _compute_medical_provider_stats(self, provider_ids: list[int]) -> dict:
        """Pre-compute provider-level aggregate stats for a batch."""
        stats = {}
        for pid in provider_ids:
            # Total claims
            total_q = await self.session.execute(
                select(func.count()).select_from(MedicalClaim).where(MedicalClaim.provider_id == pid)
            )
            total = total_q.scalar() or 0
            if total == 0:
                stats[pid] = {"total_claims": 0}
                continue

            # Modifier rates
            mod25_q = await self.session.execute(
                select(func.count()).select_from(MedicalClaim).where(
                    and_(MedicalClaim.provider_id == pid, MedicalClaim.cpt_modifier.like("%25%"))
                )
            )
            mod59_q = await self.session.execute(
                select(func.count()).select_from(MedicalClaim).where(
                    and_(MedicalClaim.provider_id == pid, MedicalClaim.cpt_modifier.like("%59%"))
                )
            )

            # Copay waiver rate
            waiver_q = await self.session.execute(
                select(func.count()).select_from(MedicalClaim).where(
                    and_(
                        MedicalClaim.provider_id == pid,
                        MedicalClaim.amount_billed == MedicalClaim.amount_allowed,
                        MedicalClaim.amount_allowed.is_not(None),
                    )
                )
            )

            # Lab order rate (claims with lab CPT on same date as E&M visit)
            em_codes = [f"9921{i}" for i in range(1, 6)] + [f"9920{i}" for i in range(1, 6)]
            em_q = await self.session.execute(
                select(func.count()).select_from(MedicalClaim).where(
                    and_(MedicalClaim.provider_id == pid, MedicalClaim.cpt_code.in_(em_codes))
                )
            )
            em_count = em_q.scalar() or 0

            lab_on_visit_q = await self.session.execute(
                select(func.count(func.distinct(MedicalClaim.service_date))).where(
                    and_(
                        MedicalClaim.provider_id == pid,
                        MedicalClaim.cpt_code.in_(em_codes),
                    )
                )
            )
            em_dates = lab_on_visit_q.scalar() or 0

            # Telehealth per day max
            th_q = await self.session.execute(
                select(MedicalClaim.service_date, func.count()).where(
                    and_(MedicalClaim.provider_id == pid, MedicalClaim.place_of_service == "02")
                ).group_by(MedicalClaim.service_date).order_by(func.count().desc()).limit(1)
            )
            th_row = th_q.first()
            th_max = th_row[1] if th_row else 0

            # Avg diagnosis codes
            dx_q = await self.session.execute(
                select(
                    func.avg(
                        1 + func.cast(MedicalClaim.diagnosis_code_2.is_not(None), type_=sa_int())
                        + func.cast(MedicalClaim.diagnosis_code_3.is_not(None), type_=sa_int())
                        + func.cast(MedicalClaim.diagnosis_code_4.is_not(None), type_=sa_int())
                    )
                ).where(MedicalClaim.provider_id == pid)
            )
            avg_dx = float(dx_q.scalar() or 1.0)

            # Referral concentration
            ref_q = await self.session.execute(
                select(
                    MedicalClaim.referring_provider_id,
                    func.count().label("cnt")
                ).where(
                    and_(
                        MedicalClaim.referring_provider_id.is_not(None),
                        or_(
                            MedicalClaim.provider_id == pid,
                            MedicalClaim.referring_provider_id == pid,
                        )
                    )
                ).group_by(MedicalClaim.referring_provider_id)
                .order_by(func.count().desc()).limit(1)
            )
            ref_row = ref_q.first()

            # For kickback: calculate what % of referrals FROM this provider go to top target
            ref_from_q = await self.session.execute(
                select(MedicalClaim.provider_id, func.count().label("cnt")).where(
                    MedicalClaim.referring_provider_id == pid
                ).group_by(MedicalClaim.provider_id).order_by(func.count().desc()).limit(1)
            )
            ref_from_row = ref_from_q.first()
            total_referrals_q = await self.session.execute(
                select(func.count()).select_from(MedicalClaim).where(
                    MedicalClaim.referring_provider_id == pid
                )
            )
            total_referrals = total_referrals_q.scalar() or 0

            ref_conc = 0.0
            top_target = None
            if ref_from_row and total_referrals > 0:
                ref_conc = ref_from_row[1] / total_referrals * 100
                top_target = ref_from_row[0]

            stats[pid] = {
                "total_claims": total,
                "modifier_25_rate": (mod25_q.scalar() or 0) / total * 100 if total else 0,
                "modifier_59_rate": (mod59_q.scalar() or 0) / total * 100 if total else 0,
                "copay_waiver_rate": (waiver_q.scalar() or 0) / total * 100 if total else 0,
                "lab_order_rate": em_count / max(em_dates, 1) * 100 if em_dates else 0,
                "telehealth_per_day_max": th_max,
                "avg_diagnosis_codes": avg_dx,
                "referral_concentration": ref_conc,
                "top_referral_target": top_target,
            }

        return stats

    async def enrich_pharmacy_batch(self, claims: list[PharmacyClaim]) -> list[EnrichedPharmacyClaim]:
        """Enrich a batch of pharmacy claims."""
        if not self._ndc_cache:
            await self._warm_caches()

        # Pre-compute prescriber stats
        prescriber_ids = list({c.prescriber_id for c in claims})
        prescriber_stats = await self._compute_prescriber_stats(prescriber_ids)

        enriched = []
        for claim in claims:
            ec = await self._enrich_single_pharmacy(claim, prescriber_stats)
            enriched.append(ec)
        return enriched

    async def _enrich_single_pharmacy(
        self, claim: PharmacyClaim, prescriber_stats: dict
    ) -> EnrichedPharmacyClaim:
        """Enrich a single pharmacy claim."""
        ndc = self._ndc_cache.get(claim.ndc_code)
        prescriber = self._provider_cache.get(claim.prescriber_id)
        pharmacy = self._pharmacy_cache.get(claim.pharmacy_id)
        member = self._member_cache.get(claim.member_id)

        member_age = None
        if member and member.date_of_birth:
            member_age = (claim.fill_date - member.date_of_birth).days // 365

        # Check if prescriber NPI actually exists
        prescriber_exists = True
        if prescriber:
            # If the claim's prescriber_npi doesn't match the provider's NPI, it's forged
            prescriber_exists = claim.prescriber_npi == prescriber.npi

        # Last fill of same drug for this member
        last_fill_q = await self.session.execute(
            select(PharmacyClaim.fill_date, PharmacyClaim.days_supply).where(
                and_(
                    PharmacyClaim.member_id == claim.member_id,
                    PharmacyClaim.ndc_code == claim.ndc_code,
                    PharmacyClaim.fill_date < claim.fill_date,
                )
            ).order_by(PharmacyClaim.fill_date.desc()).limit(1)
        )
        last_fill = last_fill_q.first()
        days_since = None
        last_supply = None
        if last_fill:
            days_since = (claim.fill_date - last_fill[0]).days
            last_supply = last_fill[1]

        # Member medical claims in 180d
        window_180 = claim.fill_date - timedelta(days=180)
        med_180d_q = await self.session.execute(
            select(func.count()).select_from(MedicalClaim).where(
                and_(
                    MedicalClaim.member_id == claim.member_id,
                    MedicalClaim.service_date >= window_180,
                    MedicalClaim.service_date <= claim.fill_date,
                )
            )
        )

        # Unique prescribers for controlled in 90d
        window_90 = claim.fill_date - timedelta(days=90)
        uniq_prescribers_q = await self.session.execute(
            select(func.count(func.distinct(PharmacyClaim.prescriber_id))).where(
                and_(
                    PharmacyClaim.member_id == claim.member_id,
                    PharmacyClaim.is_controlled == True,  # noqa: E712
                    PharmacyClaim.fill_date >= window_90,
                    PharmacyClaim.fill_date <= claim.fill_date,
                )
            )
        )

        # Unique pharmacies in 60d for same drug
        window_60 = claim.fill_date - timedelta(days=60)
        uniq_pharm_q = await self.session.execute(
            select(func.count(func.distinct(PharmacyClaim.pharmacy_id))).where(
                and_(
                    PharmacyClaim.member_id == claim.member_id,
                    PharmacyClaim.drug_name == claim.drug_name,
                    PharmacyClaim.fill_date >= window_60,
                    PharmacyClaim.fill_date <= claim.fill_date,
                )
            )
        )

        # Cumulative supply in 90d
        cum_supply_q = await self.session.execute(
            select(func.coalesce(func.sum(PharmacyClaim.days_supply), 0)).where(
                and_(
                    PharmacyClaim.member_id == claim.member_id,
                    PharmacyClaim.ndc_code == claim.ndc_code,
                    PharmacyClaim.fill_date >= window_90,
                    PharmacyClaim.fill_date <= claim.fill_date,
                )
            )
        )

        pstats = prescriber_stats.get(claim.prescriber_id, {})

        # Pharmacy-prescriber pair stats
        pair_q = await self.session.execute(
            select(func.count()).select_from(PharmacyClaim).where(
                and_(
                    PharmacyClaim.pharmacy_id == claim.pharmacy_id,
                    PharmacyClaim.prescriber_id == claim.prescriber_id,
                )
            )
        )

        return EnrichedPharmacyClaim(
            # Original
            claim_id=claim.claim_id,
            member_id=claim.member_id,
            pharmacy_id=claim.pharmacy_id,
            prescriber_id=claim.prescriber_id,
            fill_date=claim.fill_date,
            ndc_code=claim.ndc_code,
            drug_name=claim.drug_name,
            drug_class=claim.drug_class,
            is_generic=claim.is_generic,
            is_controlled=claim.is_controlled,
            dea_schedule=claim.dea_schedule,
            quantity_dispensed=claim.quantity_dispensed,
            days_supply=claim.days_supply,
            refill_number=claim.refill_number,
            amount_billed=claim.amount_billed,
            amount_allowed=claim.amount_allowed,
            amount_paid=claim.amount_paid,
            copay=claim.copay,
            prescriber_npi=claim.prescriber_npi,
            pharmacy_npi=claim.pharmacy_npi,
            prior_auth=claim.prior_auth,
            status=claim.status,
            batch_id=claim.batch_id,
            # NDC
            ndc_proprietary_name=ndc.proprietary_name if ndc else None,
            ndc_nonproprietary_name=ndc.nonproprietary_name if ndc else None,
            ndc_dea_schedule=ndc.dea_schedule if ndc else None,
            ndc_therapeutic_class=ndc.therapeutic_class if ndc else None,
            ndc_avg_wholesale_price=ndc.avg_wholesale_price if ndc else None,
            ndc_generic_available=ndc.generic_available if ndc else False,
            ndc_generic_price=ndc.generic_price if ndc else None,
            # Prescriber
            prescriber_name=prescriber.name if prescriber else None,
            prescriber_specialty=prescriber.specialty if prescriber else None,
            prescriber_is_active=prescriber.is_active if prescriber else True,
            prescriber_oig_excluded=prescriber.oig_excluded if prescriber else False,
            prescriber_dea_registration=prescriber.dea_registration if prescriber else None,
            prescriber_dea_schedule=prescriber.dea_schedule if prescriber else None,
            prescriber_exists=prescriber_exists,
            # Pharmacy
            pharmacy_name=pharmacy.name if pharmacy else None,
            pharmacy_type=pharmacy.pharmacy_type if pharmacy else None,
            pharmacy_is_active=pharmacy.is_active if pharmacy else True,
            # Member
            member_member_id=member.member_id if member else None,
            member_gender=member.gender if member else None,
            member_age=member_age,
            member_is_active=member.is_active if member else True,
            member_eligibility_end=member.eligibility_end if member else None,
            # Historical
            days_since_last_fill=days_since,
            last_fill_days_supply=last_supply,
            member_medical_claims_180d=med_180d_q.scalar() or 0,
            member_unique_prescribers_90d=uniq_prescribers_q.scalar() or 0,
            member_unique_pharmacies_60d=uniq_pharm_q.scalar() or 0,
            member_cumulative_supply_90d=cum_supply_q.scalar() or 0,
            prescriber_controlled_pct=pstats.get("controlled_pct", 0.0),
            prescriber_total_rx=pstats.get("total_rx", 0),
            prescriber_pharmacy_concentration=pstats.get("pharmacy_concentration", 0.0),
            prescriber_top_pharmacy_id=pstats.get("top_pharmacy_id"),
            pharmacy_prescriber_pair_count=pair_q.scalar() or 0,
            pharmacy_prescriber_mean=pstats.get("pair_mean", 0.0),
            pharmacy_prescriber_std=pstats.get("pair_std", 0.0),
        )

    async def _compute_prescriber_stats(self, prescriber_ids: list[int]) -> dict:
        """Pre-compute prescriber-level aggregate stats."""
        stats = {}
        for pid in prescriber_ids:
            total_q = await self.session.execute(
                select(func.count()).select_from(PharmacyClaim).where(PharmacyClaim.prescriber_id == pid)
            )
            total = total_q.scalar() or 0
            if total == 0:
                stats[pid] = {"total_rx": 0}
                continue

            controlled_q = await self.session.execute(
                select(func.count()).select_from(PharmacyClaim).where(
                    and_(PharmacyClaim.prescriber_id == pid, PharmacyClaim.is_controlled == True)  # noqa: E712
                )
            )

            # Pharmacy concentration
            top_pharm_q = await self.session.execute(
                select(PharmacyClaim.pharmacy_id, func.count().label("cnt")).where(
                    PharmacyClaim.prescriber_id == pid
                ).group_by(PharmacyClaim.pharmacy_id).order_by(func.count().desc()).limit(1)
            )
            top_pharm = top_pharm_q.first()

            pharm_conc = 0.0
            top_pharm_id = None
            if top_pharm and total > 0:
                pharm_conc = top_pharm[1] / total * 100
                top_pharm_id = top_pharm[0]

            # Pharmacy-prescriber pair stats for collusion detection
            # Mean and std of claims per pharmacy for this prescriber
            pair_counts_q = await self.session.execute(
                select(func.count().label("cnt")).where(
                    PharmacyClaim.prescriber_id == pid
                ).group_by(PharmacyClaim.pharmacy_id)
            )
            pair_counts = [r[0] for r in pair_counts_q]
            pair_mean = sum(pair_counts) / len(pair_counts) if pair_counts else 0.0
            pair_std = (
                (sum((c - pair_mean) ** 2 for c in pair_counts) / len(pair_counts)) ** 0.5
                if len(pair_counts) > 1 else 0.0
            )

            stats[pid] = {
                "total_rx": total,
                "controlled_pct": (controlled_q.scalar() or 0) / total * 100 if total else 0,
                "pharmacy_concentration": pharm_conc,
                "top_pharmacy_id": top_pharm_id,
                "pair_mean": pair_mean,
                "pair_std": pair_std,
            }
        return stats


# Needed for the diagnosis code count query
from sqlalchemy import Integer as sa_int  # noqa: E402
