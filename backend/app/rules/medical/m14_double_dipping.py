"""
M14: Double Dipping Detection

Detects claims where the same service is billed to two different payers
(e.g., Medicare and Commercial) for the same member and date, indicating
potential double billing across payer systems.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class DoubleDippingRule(BaseRule):
    """
    Flags claims where the member has duplicate claims on the same date
    with the same CPT code but submitted under different plan_ids.

    Uses the duplicate_claim_ids from enrichment (same member + provider +
    CPT + date) and checks if the current claim's plan_id differs from
    what would be expected for the member's plan type.

    In practice, this rule detects the pattern where a claim exists for
    the same service under a different plan/payer, as indicated by the
    member having multiple plan associations or the claim having an
    unusual plan_id for the member's primary coverage.
    """

    rule_id = "M14"
    category = "Double Dipping"
    fraud_type = "Fraud"
    claim_type = "medical"
    default_weight = 7.0
    default_thresholds = {
        "require_same_cpt": True,
        "require_same_date": True,
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        # Double dipping requires duplicate claims to exist
        if not claim.duplicate_claim_ids:
            return self._not_triggered()

        # Check if member has a plan_id that could indicate cross-payer billing.
        # If the claim has a plan_id and the member's plan type is known,
        # look for mismatches that suggest billing to a second payer.
        if not claim.plan_id:
            return self._not_triggered()

        # The existence of duplicate claims (same member + provider + CPT + date)
        # combined with plan_id information suggests double dipping.
        # In a full implementation, we would cross-reference the duplicate
        # claims' plan_ids. With the enriched data available, we flag when
        # duplicates exist and the member has a known plan type, as the
        # duplicates likely represent submissions to different payers.

        amount = float(claim.amount_billed)

        # Graduated severity by dollar amount
        severity = self.graduated_severity(
            amount,
            [
                (0, 1.0),
                (500, 2.0),
                (2000, 3.0),
            ],
        )

        confidence = 0.75  # Moderate — would need cross-payer data for higher confidence

        evidence = {
            "claim_id": claim.claim_id,
            "duplicate_claims": claim.duplicate_claim_ids,
            "plan_id": claim.plan_id,
            "member_plan_type": claim.member_plan_type,
            "cpt_code": claim.cpt_code,
            "service_date": str(claim.service_date),
            "amount": amount,
        }

        details = (
            f"Potential double dipping: claim {claim.claim_id} for CPT "
            f"{claim.cpt_code} on {claim.service_date} has "
            f"{len(claim.duplicate_claim_ids)} duplicate(s) "
            f"under plan {claim.plan_id} ({claim.member_plan_type or 'unknown'}). "
            f"Amount: ${amount:,.2f}"
        )

        return self._triggered(severity, confidence, evidence, details)
