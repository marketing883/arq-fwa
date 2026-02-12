"""
P5: Controlled Substance Diversion Detection

Detects prescribers who write an abnormally high percentage of
controlled substance prescriptions relative to their total volume.

Weight: 9.5 | Type: Fraud/Abuse | Priority: MEDIUM
"""

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


class ControlledSubstanceDiversionRule(BaseRule):
    rule_id = "P5"
    category = "Controlled Substance Diversion"
    fraud_type = "Fraud"
    claim_type = "pharmacy"
    default_weight = 9.5
    default_thresholds = {
        "max_controlled_pct": 60,
        "min_prescriptions": 20,
        "dea_schedules": ["CII", "CIII"],
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        max_controlled_pct = thresholds.get("max_controlled_pct", 60)
        min_prescriptions = thresholds.get("min_prescriptions", 20)

        # Need sufficient prescriber volume to establish a pattern
        if claim.prescriber_total_rx < min_prescriptions:
            return self._not_triggered()

        controlled_pct = claim.prescriber_controlled_pct

        if controlled_pct <= max_controlled_pct:
            return self._not_triggered()

        # Graduated severity by controlled substance rate
        severity = self.graduated_severity(
            controlled_pct,
            [
                (max_controlled_pct, 1.0),  # 60-75% -> 1.0
                (75.0, 2.0),               # 75-90% -> 2.0
                (90.0, 3.0),               # >90% -> 3.0
            ],
        )

        controlled_rx = int(claim.prescriber_total_rx * controlled_pct / 100)

        return self._triggered(
            severity=severity,
            confidence=0.85,
            evidence={
                "prescriber_npi": claim.prescriber_npi,
                "prescriber_name": claim.prescriber_name,
                "controlled_rate": round(controlled_pct, 1),
                "total_rx": claim.prescriber_total_rx,
                "controlled_rx": controlled_rx,
                "threshold_pct": max_controlled_pct,
                "drug": claim.drug_name,
                "claim_id": claim.claim_id,
            },
            details=(
                f"Prescriber {claim.prescriber_name} (NPI: {claim.prescriber_npi}) has "
                f"{controlled_pct:.1f}% controlled substance Rx rate "
                f"({controlled_rx}/{claim.prescriber_total_rx} prescriptions). "
                f"Threshold: {max_controlled_pct}%. Normal range: 15-25%."
            ),
        )
