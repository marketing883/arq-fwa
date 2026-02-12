"""
P4: Early Refill Detection

Detects refills that are requested significantly before the previous
supply should have been exhausted.

Weight: 4.5 | Type: Waste/Abuse | Priority: HIGH
"""

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


class EarlyRefillRule(BaseRule):
    rule_id = "P4"
    category = "Early Refill"
    fraud_type = "Waste"
    claim_type = "pharmacy"
    default_weight = 4.5
    default_thresholds = {
        "early_pct": 75,
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        early_pct = thresholds.get("early_pct", 75)

        # Need previous fill data to evaluate
        if claim.days_since_last_fill is None or claim.last_fill_days_supply is None:
            return self._not_triggered()

        # Skip if last fill had 0 days supply (avoids division issues)
        if claim.last_fill_days_supply <= 0:
            return self._not_triggered()

        # Calculate expected refill day and the early threshold
        expected_refill_day = claim.last_fill_days_supply
        early_threshold_day = expected_refill_day * (early_pct / 100.0)

        if claim.days_since_last_fill >= early_threshold_day:
            return self._not_triggered()

        # Calculate how early the refill is as a percentage of supply used
        pct_supply_used = (claim.days_since_last_fill / expected_refill_day) * 100

        # Graduated severity by how early the refill is
        # pct_supply_used: lower = more suspicious
        severity = self.graduated_severity(
            100 - pct_supply_used,  # invert: higher value = more severe
            [
                (25.0, 0.3),   # borderline (70-75% used) -> 0.3
                (30.0, 0.8),   # somewhat early (50-70% used) -> 0.8
                (50.0, 1.5),   # very early (30-50% used) -> 1.5
                (70.0, 2.5),   # extreme (<30% used) -> 2.5
            ],
        )

        return self._triggered(
            severity=severity,
            confidence=0.85,
            evidence={
                "days_supply": claim.last_fill_days_supply,
                "days_since_last_fill": claim.days_since_last_fill,
                "expected_refill_day": expected_refill_day,
                "pct_supply_used": round(pct_supply_used, 1),
                "early_threshold_pct": early_pct,
                "drug": claim.drug_name,
                "member": claim.member_member_id,
                "claim_id": claim.claim_id,
                "is_controlled": claim.is_controlled,
            },
            details=(
                f"Early refill: {claim.days_since_last_fill} days since last fill of "
                f"{claim.last_fill_days_supply}-day supply ({pct_supply_used:.0f}% consumed). "
                f"Drug: {claim.drug_name}. "
                f"Expected refill at day {expected_refill_day}."
            ),
        )
