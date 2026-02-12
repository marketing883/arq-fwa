"""
P3: Pharmacy Shopping Detection

Detects members who fill the same drug at an unusually high number of
different pharmacies within a rolling window.

Weight: 3.0 | Type: Abuse | Priority: LOW
"""

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


class PharmacyShoppingRule(BaseRule):
    rule_id = "P3"
    category = "Pharmacy Shopping"
    fraud_type = "Abuse"
    claim_type = "pharmacy"
    default_weight = 3.0
    default_thresholds = {
        "max_pharmacies": 3,
        "window_days": 60,
        "match_by": "generic_name",
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        max_pharmacies = thresholds.get("max_pharmacies", 3)

        pharmacy_count = claim.member_unique_pharmacies_60d

        if pharmacy_count <= max_pharmacies:
            return self._not_triggered()

        # Graduated severity by pharmacy count
        severity = self.graduated_severity(
            pharmacy_count,
            [
                (max_pharmacies + 1, 0.8),  # 4 pharmacies -> 0.8
                (max_pharmacies + 2, 1.5),  # 5-6 pharmacies -> 1.5
                (max_pharmacies + 4, 2.5),  # 7+ pharmacies -> 2.5
            ],
        )

        return self._triggered(
            severity=severity,
            confidence=0.80,
            evidence={
                "member": claim.member_member_id,
                "pharmacy_count": pharmacy_count,
                "threshold": max_pharmacies,
                "window": f"{thresholds.get('window_days', 60)}d",
                "drug": claim.drug_name,
                "drug_class": claim.drug_class,
                "claim_id": claim.claim_id,
            },
            details=(
                f"Member {claim.member_member_id} filled {claim.drug_name} at "
                f"{pharmacy_count} different pharmacies in 60 days "
                f"(threshold: {max_pharmacies})."
            ),
        )
