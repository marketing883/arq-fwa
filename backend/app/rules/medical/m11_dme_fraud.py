"""
M11: Durable Medical Equipment (DME) Fraud Detection

Detects high-cost DME claims (HCPCS K-codes, E-codes) for equipment
that may not be medically necessary, especially when the member's
activity patterns contradict the need for the equipment.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class DMEFraudRule(BaseRule):
    """
    Flags DME claims that exceed the minimum dollar threshold.
    Uses the cpt_is_dme flag from reference data to identify DME claims.

    Severity is graduated by the claim amount.
    """

    rule_id = "M11"
    category = "DME Fraud"
    fraud_type = "Fraud"
    claim_type = "medical"
    default_weight = 6.0
    default_thresholds = {
        "min_dme_amount": 1000,
        "check_contradicting_claims": True,
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        min_amount = thresholds.get(
            "min_dme_amount", self.default_thresholds["min_dme_amount"]
        )

        # Check if this is a DME claim
        if not claim.cpt_is_dme:
            return self._not_triggered()

        amount = float(claim.amount_billed)

        if amount < min_amount:
            return self._not_triggered()

        # Graduated severity by DME amount
        severity = self.graduated_severity(
            amount,
            [
                (1000, 1.0),
                (5000, 2.0),
                (15000, 3.0),
            ],
        )

        # Higher confidence if the member has high activity (contradicts DME need)
        # member_claims_30d being high for a DME patient is suspicious
        confidence = 0.7
        contradicting = False
        if claim.member_claims_30d > 5:
            confidence = 0.85
            contradicting = True

        evidence = {
            "dme_item": claim.cpt_code,
            "cpt_description": claim.cpt_description,
            "amount": amount,
            "member_id": claim.member_id,
            "provider_id": claim.provider_id,
            "member_claims_30d": claim.member_claims_30d,
            "contradicting_activity": contradicting,
        }

        details = (
            f"High-cost DME claim: CPT {claim.cpt_code} "
            f"({claim.cpt_description or 'DME equipment'}) "
            f"billed at ${amount:,.2f} (threshold: ${min_amount:,.2f})"
        )
        if contradicting:
            details += (
                f". Member has {claim.member_claims_30d} other claims in 30d, "
                f"suggesting activity inconsistent with DME need"
            )

        return self._triggered(severity, confidence, evidence, details)
