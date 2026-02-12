"""
P13: Pharmacy-Provider Collusion Detection

Detects specific (pharmacy, prescriber) pairs that generate claim volume
significantly above the statistical mean for all such pairs, indicating
potential collusion.

Weight: 6.0 | Type: Fraud | Priority: LOW
"""

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


class PharmacyProviderCollusionRule(BaseRule):
    rule_id = "P13"
    category = "Pharmacy-Provider Collusion"
    fraud_type = "Fraud"
    claim_type = "pharmacy"
    default_weight = 6.0
    default_thresholds = {
        "std_dev_threshold": 3.0,
        "min_claims": 20,
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        std_dev_threshold = thresholds.get("std_dev_threshold", 3.0)
        min_claims = thresholds.get("min_claims", 20)

        pair_count = claim.pharmacy_prescriber_pair_count
        pair_mean = claim.pharmacy_prescriber_mean
        pair_std = claim.pharmacy_prescriber_std

        # Need sufficient claim volume to evaluate
        if pair_count < min_claims:
            return self._not_triggered()

        # Need valid statistical data
        if pair_std <= 0 or pair_mean <= 0:
            return self._not_triggered()

        # Calculate z-score: how many std devs above mean
        z_score = (pair_count - pair_mean) / pair_std

        if z_score < std_dev_threshold:
            return self._not_triggered()

        # Graduated severity by z-score
        severity = self.graduated_severity(
            z_score,
            [
                (3.0, 1.0),   # 3-4 std devs -> 1.0
                (4.0, 2.0),   # 4-5 std devs -> 2.0
                (5.0, 3.0),   # >5 std devs -> 3.0
            ],
        )

        return self._triggered(
            severity=severity,
            confidence=0.80,
            evidence={
                "pharmacy": claim.pharmacy_name,
                "pharmacy_npi": claim.pharmacy_npi,
                "prescriber": claim.prescriber_npi,
                "prescriber_name": claim.prescriber_name,
                "claim_count": pair_count,
                "mean": round(pair_mean, 1),
                "std_dev": round(pair_std, 1),
                "z_score": round(z_score, 2),
                "threshold_std_devs": std_dev_threshold,
                "claim_id": claim.claim_id,
            },
            details=(
                f"Pharmacy {claim.pharmacy_name} and prescriber {claim.prescriber_name} "
                f"(NPI: {claim.prescriber_npi}) have {pair_count} shared claims, "
                f"which is {z_score:.1f} standard deviations above the mean "
                f"(mean: {pair_mean:.1f}, std: {pair_std:.1f}, threshold: {std_dev_threshold} SD)."
            ),
        )
