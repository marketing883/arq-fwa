"""
M16: Chart Padding Detection

Detects claims with an excessive number of diagnosis codes per encounter,
indicating potential inflation of medical complexity to justify higher
reimbursement. Normal encounters have 2-4 diagnosis codes for most
specialties.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class ChartPaddingRule(BaseRule):
    """
    Flags claims where the number of distinct diagnosis codes exceeds
    the specialty-adjusted threshold.  Also checks the provider's
    average diagnosis code count across all claims for pattern detection.

    Severity is graduated by how many codes exceed the threshold.
    """

    rule_id = "M16"
    category = "Chart Padding"
    fraud_type = "Abuse"
    claim_type = "medical"
    default_weight = 4.0
    default_thresholds = {
        "max_diagnosis_codes": 3,
        "specialty_overrides": {
            "oncology": 4,
            "internal_medicine": 4,
        },
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        default_max = thresholds.get(
            "max_diagnosis_codes",
            self.default_thresholds["max_diagnosis_codes"],
        )
        specialty_overrides = thresholds.get(
            "specialty_overrides",
            self.default_thresholds["specialty_overrides"],
        )

        # Determine the threshold for this provider's specialty
        max_codes = default_max
        if claim.provider_specialty:
            specialty_lower = claim.provider_specialty.lower().replace(" ", "_")
            if specialty_lower in specialty_overrides:
                max_codes = specialty_overrides[specialty_lower]

        dx_count = claim.diagnosis_code_count

        if dx_count <= max_codes:
            # Also check the provider's average — even if this claim is
            # below threshold, flag if the provider's average is abnormally high
            if claim.provider_avg_diagnosis_codes <= max_codes:
                return self._not_triggered()
            # Provider average is high; only flag if this claim also has
            # above-average codes
            if dx_count < claim.provider_avg_diagnosis_codes:
                return self._not_triggered()

        # Calculate how many codes over the threshold
        codes_over = dx_count - max_codes

        # Graduated severity by count over threshold
        severity = self.graduated_severity(
            codes_over,
            [
                (0, 0.3),
                (1, 0.5),
                (3, 1.0),
                (5, 2.0),
            ],
        )

        # Boost severity if provider pattern is also high
        if claim.provider_avg_diagnosis_codes > max_codes:
            severity = min(severity * 1.3, 3.0)

        confidence = 0.7

        # Collect the diagnosis codes
        codes = [claim.diagnosis_code_primary]
        if claim.diagnosis_code_2:
            codes.append(claim.diagnosis_code_2)
        if claim.diagnosis_code_3:
            codes.append(claim.diagnosis_code_3)
        if claim.diagnosis_code_4:
            codes.append(claim.diagnosis_code_4)

        evidence = {
            "diagnosis_count": dx_count,
            "threshold": max_codes,
            "codes_over": codes_over,
            "codes": codes,
            "provider_avg_dx_codes": round(claim.provider_avg_diagnosis_codes, 2),
            "provider_specialty": claim.provider_specialty,
            "provider_id": claim.provider_id,
        }

        details = (
            f"Chart padding: {dx_count} diagnosis codes "
            f"(threshold: {max_codes} for "
            f"{claim.provider_specialty or 'general'} specialty). "
            f"Provider average: {claim.provider_avg_diagnosis_codes:.1f} codes/claim. "
            f"Codes: {', '.join(codes)}"
        )

        return self._triggered(severity, confidence, evidence, details)
