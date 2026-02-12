"""
M7: Provider Collusion Detection

Detects patterns where two providers frequently bill the same member
on the same date for complementary services, suggesting coordinated
fraudulent billing.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class ProviderCollusionRule(BaseRule):
    """
    Flags claims where the member has multiple claims on the same date
    from different providers (detected via duplicate_claim_ids which
    captures same member+provider+CPT+date, but here we look at
    member_claims_30d as a proxy for co-billing patterns).

    In the enrichment data, if a referring provider exists and the
    referral concentration is high, this can also indicate collusion
    patterns.

    This rule uses provider_referral_concentration and checks if the
    current claim has a referring provider relationship with high
    shared patient volume.
    """

    rule_id = "M7"
    category = "Provider Collusion"
    fraud_type = "Fraud"
    claim_type = "medical"
    default_weight = 6.5
    default_thresholds = {
        "min_shared_patients": 5,
        "same_day_required": True,
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        min_shared = thresholds.get(
            "min_shared_patients",
            self.default_thresholds["min_shared_patients"],
        )

        # Check if this claim involves a referring provider relationship
        if not claim.referring_provider_id:
            return self._not_triggered()

        # The referring provider and the rendering provider are a pair.
        # provider_referral_concentration measures how concentrated the
        # referral pattern is. A high concentration indicates these two
        # providers have an unusually tight relationship.
        referral_concentration = claim.provider_referral_concentration

        # We also use provider_total_claims as a proxy for shared patient
        # volume. If the referral concentration is high and there are
        # enough total claims, it suggests collusion.
        if claim.provider_total_claims < min_shared:
            return self._not_triggered()

        # Only flag if the concentration suggests a tight relationship
        # (above 50% indicates unusually high co-billing)
        if referral_concentration < 50:
            return self._not_triggered()

        # Estimate shared patient count from concentration and total claims
        estimated_shared = int(
            claim.provider_total_claims * referral_concentration / 100
        )

        if estimated_shared < min_shared:
            return self._not_triggered()

        # Graduated severity by shared patient count
        severity = self.graduated_severity(
            estimated_shared,
            [
                (5, 0.8),
                (10, 1.5),
                (20, 2.5),
            ],
        )

        confidence = 0.7

        evidence = {
            "provider_a": claim.provider_id,
            "provider_b": claim.referring_provider_id,
            "referral_concentration": round(referral_concentration, 2),
            "estimated_shared_patients": estimated_shared,
            "total_claims": claim.provider_total_claims,
            "service_date": str(claim.service_date),
        }

        details = (
            f"Possible collusion between provider {claim.provider_id} and "
            f"referring provider {claim.referring_provider_id}: "
            f"referral concentration {referral_concentration:.1f}%, "
            f"~{estimated_shared} shared patients"
        )

        return self._triggered(severity, confidence, evidence, details)
