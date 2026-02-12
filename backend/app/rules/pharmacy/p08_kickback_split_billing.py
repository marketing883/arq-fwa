"""
P8: Kickback / Split Billing Detection

Detects prescribers who send an abnormally high percentage of their
prescriptions to a single pharmacy, indicating a potential kickback
arrangement.

Weight: 6.5 | Type: Fraud | Priority: MEDIUM
"""

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


class KickbackSplitBillingRule(BaseRule):
    rule_id = "P8"
    category = "Kickback/Split Billing"
    fraud_type = "Fraud"
    claim_type = "pharmacy"
    default_weight = 6.5
    default_thresholds = {
        "concentration_pct": 80,
        "min_prescriptions": 15,
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        concentration_pct = thresholds.get("concentration_pct", 80)
        min_prescriptions = thresholds.get("min_prescriptions", 15)

        # Need sufficient prescription volume to establish a pattern
        if claim.prescriber_total_rx < min_prescriptions:
            return self._not_triggered()

        pharmacy_concentration = claim.prescriber_pharmacy_concentration

        if pharmacy_concentration < concentration_pct:
            return self._not_triggered()

        # Graduated severity by concentration percentage
        severity = self.graduated_severity(
            pharmacy_concentration,
            [
                (80.0, 1.0),   # 80-90% -> 1.0
                (90.0, 2.0),   # 90-95% -> 2.0
                (95.0, 3.0),   # >95% -> 3.0
            ],
        )

        return self._triggered(
            severity=severity,
            confidence=0.80,
            evidence={
                "prescriber": claim.prescriber_npi,
                "prescriber_name": claim.prescriber_name,
                "pharmacy": claim.pharmacy_name,
                "pharmacy_id": claim.pharmacy_id,
                "top_pharmacy_id": claim.prescriber_top_pharmacy_id,
                "concentration": round(pharmacy_concentration, 1),
                "total_rx": claim.prescriber_total_rx,
                "threshold_pct": concentration_pct,
                "claim_id": claim.claim_id,
            },
            details=(
                f"Prescriber {claim.prescriber_name} (NPI: {claim.prescriber_npi}) sends "
                f"{pharmacy_concentration:.1f}% of prescriptions to a single pharmacy "
                f"(threshold: {concentration_pct}%). "
                f"Total prescriptions: {claim.prescriber_total_rx}."
            ),
        )
