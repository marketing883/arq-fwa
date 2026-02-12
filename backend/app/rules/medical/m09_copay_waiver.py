"""
M9: Copay Waiver Detection

Detects providers who routinely waive patient copays, indicated by
amount_billed consistently equaling amount_allowed across their claims.
This pattern over 6+ months suggests systematic copay waiver abuse.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class CopayWaiverRule(BaseRule):
    """
    Flags claims from providers whose copay waiver rate (% of claims where
    amount_billed == amount_allowed) exceeds the threshold, indicating
    routine copay waiver as an inducement.

    Only triggers when the current claim itself also shows the pattern
    (amount_billed == amount_allowed).
    """

    rule_id = "M9"
    category = "Copay Waiver"
    fraud_type = "Abuse"
    claim_type = "medical"
    default_weight = 2.5
    default_thresholds = {
        "waiver_pct": 90,
        "min_months": 6,
        "min_claims": 30,
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        waiver_pct_threshold = thresholds.get(
            "waiver_pct", self.default_thresholds["waiver_pct"]
        )
        min_claims = thresholds.get(
            "min_claims", self.default_thresholds["min_claims"]
        )

        # Need allowed amount for comparison
        if claim.amount_allowed is None:
            return self._not_triggered()

        # Only flag if this claim itself shows the pattern
        if claim.amount_billed != claim.amount_allowed:
            return self._not_triggered()

        # Need enough claims to establish a pattern
        if claim.provider_total_claims < min_claims:
            return self._not_triggered()

        waiver_rate = claim.provider_copay_waiver_rate

        if waiver_rate < waiver_pct_threshold:
            return self._not_triggered()

        # Graduated severity by waiver rate
        severity = self.graduated_severity(
            waiver_rate,
            [
                (90, 0.5),
                (95, 1.0),
                (100, 1.5),
            ],
        )

        confidence = 0.7 if claim.provider_total_claims >= 50 else 0.5

        evidence = {
            "waiver_rate": round(waiver_rate, 2),
            "total_claims": claim.provider_total_claims,
            "amount_billed": float(claim.amount_billed),
            "amount_allowed": float(claim.amount_allowed),
            "provider_id": claim.provider_id,
        }

        details = (
            f"Provider copay waiver rate at {waiver_rate:.1f}% "
            f"(threshold: {waiver_pct_threshold}%) across "
            f"{claim.provider_total_claims} claims. "
            f"This claim: billed ${float(claim.amount_billed):,.2f} "
            f"== allowed ${float(claim.amount_allowed):,.2f}"
        )

        return self._triggered(severity, confidence, evidence, details)
