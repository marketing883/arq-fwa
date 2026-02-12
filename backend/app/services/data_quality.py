"""
Data Quality Gates — pre-enrichment validation inserted at the start of the pipeline.

Checks for:
- Duplicate claims
- Schema conformance (required fields, valid dates, positive amounts)
- Outlier detection (amount_billed > 3 std deviations from mean for that CPT/NDC)
- Referential integrity (provider_id and member_id exist)
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from statistics import mean, stdev

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MedicalClaim, PharmacyClaim, Provider, Member

logger = logging.getLogger(__name__)


@dataclass
class QualityIssue:
    claim_id: str
    issue_type: str
    detail: str


@dataclass
class QualityReport:
    total_claims: int = 0
    passed: int = 0
    failed: int = 0
    issues: list[QualityIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_claims": self.total_claims,
            "passed": self.passed,
            "failed": self.failed,
            "issues": [
                {"claim_id": i.claim_id, "issue_type": i.issue_type, "detail": i.detail}
                for i in self.issues[:200]  # cap for response size
            ],
        }


class DataQualityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_medical_claims(self, claims: list[MedicalClaim]) -> QualityReport:
        report = QualityReport(total_claims=len(claims))
        if not claims:
            return report

        failed_ids: set[str] = set()

        # ── 1. Duplicate detection ──
        seen: set[tuple] = set()
        for c in claims:
            key = (c.provider_id, c.member_id, str(c.service_date), c.cpt_code)
            if key in seen:
                report.issues.append(QualityIssue(
                    claim_id=c.claim_id,
                    issue_type="duplicate",
                    detail=f"Duplicate: same provider/member/date/CPT as another claim",
                ))
                failed_ids.add(c.claim_id)
            seen.add(key)

        # ── 2. Schema conformance ──
        for c in claims:
            if not c.claim_id:
                report.issues.append(QualityIssue(c.claim_id or "UNKNOWN", "schema", "Missing claim_id"))
                failed_ids.add(c.claim_id or "UNKNOWN")
            if not c.service_date:
                report.issues.append(QualityIssue(c.claim_id, "schema", "Missing service_date"))
                failed_ids.add(c.claim_id)
            if c.amount_billed is not None and c.amount_billed <= 0:
                report.issues.append(QualityIssue(c.claim_id, "schema", f"Non-positive amount_billed: {c.amount_billed}"))
                failed_ids.add(c.claim_id)

        # ── 3. Outlier detection (amount_billed per CPT code) ──
        cpt_amounts: dict[str, list[float]] = defaultdict(list)
        for c in claims:
            if c.cpt_code and c.amount_billed:
                cpt_amounts[c.cpt_code].append(float(c.amount_billed))

        for c in claims:
            if c.cpt_code and c.amount_billed and len(cpt_amounts.get(c.cpt_code, [])) >= 5:
                amounts = cpt_amounts[c.cpt_code]
                m = mean(amounts)
                s = stdev(amounts) if len(amounts) > 1 else 0
                if s > 0 and abs(float(c.amount_billed) - m) > 3 * s:
                    report.issues.append(QualityIssue(
                        claim_id=c.claim_id,
                        issue_type="outlier",
                        detail=f"amount_billed ${float(c.amount_billed):,.2f} is >3 std devs from mean ${m:,.2f} for CPT {c.cpt_code}",
                    ))
                    failed_ids.add(c.claim_id)

        # ── 4. Referential integrity ──
        provider_ids = {c.provider_id for c in claims if c.provider_id}
        if provider_ids:
            existing = set((await self.db.execute(
                select(Provider.id).where(Provider.id.in_(provider_ids))
            )).scalars())
            for c in claims:
                if c.provider_id and c.provider_id not in existing:
                    report.issues.append(QualityIssue(c.claim_id, "referential_integrity", f"provider_id {c.provider_id} not found"))
                    failed_ids.add(c.claim_id)

        member_ids = {c.member_id for c in claims if c.member_id}
        if member_ids:
            existing = set((await self.db.execute(
                select(Member.id).where(Member.id.in_(member_ids))
            )).scalars())
            for c in claims:
                if c.member_id and c.member_id not in existing:
                    report.issues.append(QualityIssue(c.claim_id, "referential_integrity", f"member_id {c.member_id} not found"))
                    failed_ids.add(c.claim_id)

        report.failed = len(failed_ids)
        report.passed = report.total_claims - report.failed
        return report

    async def validate_pharmacy_claims(self, claims: list[PharmacyClaim]) -> QualityReport:
        report = QualityReport(total_claims=len(claims))
        if not claims:
            return report

        failed_ids: set[str] = set()

        # ── 1. Duplicate detection ──
        seen: set[tuple] = set()
        for c in claims:
            key = (c.member_id, str(c.fill_date), c.ndc_code)
            if key in seen:
                report.issues.append(QualityIssue(
                    claim_id=c.claim_id,
                    issue_type="duplicate",
                    detail="Duplicate: same member/fill_date/NDC as another claim",
                ))
                failed_ids.add(c.claim_id)
            seen.add(key)

        # ── 2. Schema conformance ──
        for c in claims:
            if not c.fill_date:
                report.issues.append(QualityIssue(c.claim_id, "schema", "Missing fill_date"))
                failed_ids.add(c.claim_id)
            if c.amount_billed is not None and c.amount_billed <= 0:
                report.issues.append(QualityIssue(c.claim_id, "schema", f"Non-positive amount_billed: {c.amount_billed}"))
                failed_ids.add(c.claim_id)

        # ── 3. Outlier detection (amount_billed per NDC) ──
        ndc_amounts: dict[str, list[float]] = defaultdict(list)
        for c in claims:
            if c.ndc_code and c.amount_billed:
                ndc_amounts[c.ndc_code].append(float(c.amount_billed))

        for c in claims:
            if c.ndc_code and c.amount_billed and len(ndc_amounts.get(c.ndc_code, [])) >= 5:
                amounts = ndc_amounts[c.ndc_code]
                m = mean(amounts)
                s = stdev(amounts) if len(amounts) > 1 else 0
                if s > 0 and abs(float(c.amount_billed) - m) > 3 * s:
                    report.issues.append(QualityIssue(
                        claim_id=c.claim_id,
                        issue_type="outlier",
                        detail=f"amount_billed ${float(c.amount_billed):,.2f} is >3 std devs from mean ${m:,.2f} for NDC {c.ndc_code}",
                    ))
                    failed_ids.add(c.claim_id)

        report.failed = len(failed_ids)
        report.passed = report.total_claims - report.failed
        return report
