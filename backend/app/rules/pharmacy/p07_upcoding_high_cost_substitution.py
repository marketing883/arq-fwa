"""
P7: High-Cost Substitution / Upcoding Detection

Detects pharmacies dispensing brand-name drugs when a generic equivalent
is available and costs significantly less.

Weight: 5.5 | Type: Fraud | Priority: MEDIUM
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


class UpcodingHighCostSubstitutionRule(BaseRule):
    rule_id = "P7"
    category = "High-Cost Substitution"
    fraud_type = "Fraud"
    claim_type = "pharmacy"
    default_weight = 5.5
    default_thresholds = {
        "cost_diff_pct": 50,
        "require_generic_available": True,
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        cost_diff_pct = thresholds.get("cost_diff_pct", 50)
        require_generic = thresholds.get("require_generic_available", True)

        # Only applies to brand-name drugs
        if claim.is_generic:
            return self._not_triggered()

        # Check if a generic equivalent is available
        if require_generic and not claim.ndc_generic_available:
            return self._not_triggered()

        # Need pricing data to calculate cost difference
        if claim.ndc_avg_wholesale_price is None or claim.ndc_generic_price is None:
            return self._not_triggered()

        if claim.ndc_avg_wholesale_price <= Decimal("0") or claim.ndc_generic_price <= Decimal("0"):
            return self._not_triggered()

        # Calculate cost difference percentage
        brand_cost = claim.ndc_avg_wholesale_price
        generic_cost = claim.ndc_generic_price
        cost_diff = float((brand_cost - generic_cost) / brand_cost * 100)

        if cost_diff < cost_diff_pct:
            return self._not_triggered()

        # Calculate per-claim savings
        savings = claim.amount_billed * Decimal(str(cost_diff / 100))

        # Graduated severity by cost difference
        severity = self.graduated_severity(
            cost_diff,
            [
                (50.0, 0.8),   # 50-70% difference -> 0.8
                (70.0, 1.5),   # 70-85% difference -> 1.5
                (85.0, 2.5),   # >85% difference -> 2.5
            ],
        )

        return self._triggered(
            severity=severity,
            confidence=0.85,
            evidence={
                "brand_drug": claim.drug_name,
                "brand_cost": str(brand_cost),
                "generic_available": claim.ndc_generic_available,
                "generic_cost": str(generic_cost),
                "cost_diff_pct": round(cost_diff, 1),
                "savings": str(savings),
                "amount_billed": str(claim.amount_billed),
                "pharmacy_name": claim.pharmacy_name,
                "claim_id": claim.claim_id,
            },
            details=(
                f"Brand-name drug {claim.drug_name} dispensed at ${brand_cost} when "
                f"generic is available at ${generic_cost} ({cost_diff:.1f}% cost difference). "
                f"Potential savings: ${savings:.2f}. "
                f"Pharmacy: {claim.pharmacy_name}"
            ),
        )
