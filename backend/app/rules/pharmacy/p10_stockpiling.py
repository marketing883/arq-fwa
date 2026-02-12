"""
P10: Stockpiling Detection

Detects members who accumulate excessive days of drug supply within a
rolling window, suggesting diversion or stockpiling behavior.

Weight: 4.0 | Type: Waste | Priority: LOW
"""

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


class StockpilingRule(BaseRule):
    rule_id = "P10"
    category = "Stockpiling"
    fraud_type = "Waste"
    claim_type = "pharmacy"
    default_weight = 4.0
    default_thresholds = {
        "window_days": 90,
        "max_supply_ratio": 1.5,
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        window_days = thresholds.get("window_days", 90)
        max_supply_ratio = thresholds.get("max_supply_ratio", 1.5)

        cumulative_supply = claim.member_cumulative_supply_90d

        # Need some supply to evaluate
        if cumulative_supply <= 0:
            return self._not_triggered()

        # Calculate the supply-to-calendar ratio
        supply_ratio = cumulative_supply / window_days

        if supply_ratio < max_supply_ratio:
            return self._not_triggered()

        # Graduated severity by ratio
        severity = self.graduated_severity(
            supply_ratio,
            [
                (1.5, 0.8),   # 1.5-2.0x -> 0.8
                (2.0, 1.5),   # 2.0-3.0x -> 1.5
                (3.0, 2.5),   # >3.0x -> 2.5
            ],
        )

        return self._triggered(
            severity=severity,
            confidence=0.80,
            evidence={
                "member": claim.member_member_id,
                "drug": claim.drug_name,
                "cumulative_supply": cumulative_supply,
                "calendar_days": window_days,
                "ratio": round(supply_ratio, 2),
                "threshold_ratio": max_supply_ratio,
                "claim_id": claim.claim_id,
                "is_controlled": claim.is_controlled,
            },
            details=(
                f"Member {claim.member_member_id} accumulated {cumulative_supply} days of "
                f"{claim.drug_name} supply in {window_days} calendar days "
                f"(ratio: {supply_ratio:.2f}x, threshold: {max_supply_ratio}x)."
            ),
        )
