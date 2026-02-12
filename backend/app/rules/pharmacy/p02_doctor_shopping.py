"""
P2: Doctor Shopping Detection

Detects members who obtain prescriptions for controlled substances from
an unusually high number of unique prescribers within a rolling window.

Weight: 7.5 | Type: Abuse | Priority: MEDIUM
"""

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


class DoctorShoppingRule(BaseRule):
    rule_id = "P2"
    category = "Doctor Shopping"
    fraud_type = "Abuse"
    claim_type = "pharmacy"
    default_weight = 7.5
    default_thresholds = {
        "max_prescribers": 4,
        "window_days": 90,
        "dea_schedules": ["CII", "CIII"],
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        max_prescribers = thresholds.get("max_prescribers", 4)
        target_schedules = thresholds.get("dea_schedules", ["CII", "CIII"])

        # Only applies to controlled substances in the target schedules
        if not claim.is_controlled:
            return self._not_triggered()

        if claim.dea_schedule not in target_schedules and claim.ndc_dea_schedule not in target_schedules:
            return self._not_triggered()

        prescriber_count = claim.member_unique_prescribers_90d

        if prescriber_count <= max_prescribers:
            return self._not_triggered()

        # Graduated severity by prescriber count
        severity = self.graduated_severity(
            prescriber_count,
            [
                (max_prescribers + 1, 1.0),  # 5 prescribers -> 1.0
                (max_prescribers + 2, 1.5),  # 6-7 prescribers -> 1.5
                (max_prescribers + 4, 3.0),  # 8+ prescribers -> 3.0
            ],
        )

        return self._triggered(
            severity=severity,
            confidence=0.85,
            evidence={
                "member": claim.member_member_id,
                "prescriber_count": prescriber_count,
                "window": f"{thresholds.get('window_days', 90)}d",
                "threshold": max_prescribers,
                "drug_name": claim.drug_name,
                "drug_class": claim.drug_class,
                "dea_schedule": claim.dea_schedule or claim.ndc_dea_schedule,
                "claim_id": claim.claim_id,
            },
            details=(
                f"Member {claim.member_member_id} visited {prescriber_count} unique prescribers "
                f"for controlled substances in 90 days (threshold: {max_prescribers}). "
                f"Drug: {claim.drug_name} (Schedule {claim.dea_schedule or claim.ndc_dea_schedule})"
            ),
        )
