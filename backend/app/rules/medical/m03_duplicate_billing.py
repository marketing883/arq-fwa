"""
M3: Duplicate Billing Detection

Detects claims that are exact duplicates of another claim — same member,
same provider, same CPT code, same service date — but with a different
claim ID, indicating double billing.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class DuplicateBillingRule(BaseRule):
    """
    Flags claims where duplicate_claim_ids is non-empty, meaning another
    claim exists with the same (member_id, provider_id, cpt_code, service_date).

    Allows modifier exceptions: modifier 76 (repeat procedure) and 77
    (repeat by another provider) are legitimate repeats.
    """

    rule_id = "M3"
    category = "Duplicate Billing"
    fraud_type = "Fraud"
    claim_type = "medical"
    default_weight = 8.0
    default_thresholds = {
        "exact_match": True,
        "exclude_modifiers": ["76", "77"],
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        exclude_modifiers = thresholds.get(
            "exclude_modifiers",
            self.default_thresholds["exclude_modifiers"],
        )

        # Check for modifier exceptions — legitimate repeat procedures
        if claim.cpt_modifier and claim.cpt_modifier in exclude_modifiers:
            return self._not_triggered()

        # Check if there are any duplicate claims
        if not claim.duplicate_claim_ids:
            return self._not_triggered()

        duplicate_count = len(claim.duplicate_claim_ids)
        amount = float(claim.amount_billed)

        # Graduated severity by dollar amount
        severity = self.graduated_severity(
            amount,
            [
                (0, 0.5),
                (200, 1.0),
                (1000, 2.0),
                (5000, 3.0),
            ],
        )

        confidence = 0.95  # High confidence — exact match on key fields

        evidence = {
            "original_claim": claim.claim_id,
            "duplicate_claims": claim.duplicate_claim_ids,
            "duplicate_count": duplicate_count,
            "amount": amount,
            "date": str(claim.service_date),
            "cpt_code": claim.cpt_code,
            "member_id": claim.member_id,
            "provider_id": claim.provider_id,
        }

        details = (
            f"Claim {claim.claim_id} has {duplicate_count} duplicate(s) "
            f"({', '.join(str(d) for d in claim.duplicate_claim_ids[:3])}) "
            f"for CPT {claim.cpt_code} on {claim.service_date} "
            f"totaling ${amount:,.2f}"
        )

        return self._triggered(severity, confidence, evidence, details)
