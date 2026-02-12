"""
M5: Kickback / Self-Referral Detection

Detects providers whose referrals are heavily concentrated toward a single
receiving provider, indicating potential kickback arrangements or illegal
self-referral (Stark Law violations).
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class KickbackSelfReferralRule(BaseRule):
    """
    Flags claims where the referring provider sends > X% of all referrals
    to a single target provider.  Uses pre-computed provider_referral_concentration
    (percentage) from the enrichment pipeline.

    Only triggers when the claim has a referring_provider_id (i.e., it is
    part of a referral relationship).
    """

    rule_id = "M5"
    category = "Kickback/Self-Referral"
    fraud_type = "Fraud"
    claim_type = "medical"
    default_weight = 9.5
    default_thresholds = {
        "concentration_pct": 80,
        "min_referral_count": 10,
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        concentration_pct = thresholds.get(
            "concentration_pct",
            self.default_thresholds["concentration_pct"],
        )
        min_referrals = thresholds.get(
            "min_referral_count",
            self.default_thresholds["min_referral_count"],
        )

        # Only evaluate claims that are part of a referral
        if not claim.referring_provider_id:
            return self._not_triggered()

        referral_concentration = claim.provider_referral_concentration

        # Need enough referrals to establish a pattern
        if claim.provider_total_claims < min_referrals:
            return self._not_triggered()

        if referral_concentration < concentration_pct:
            return self._not_triggered()

        # Graduated severity by concentration level
        severity = self.graduated_severity(
            referral_concentration,
            [
                (80, 1.0),
                (90, 2.0),
                (95, 3.0),
            ],
        )

        confidence = 0.85

        evidence = {
            "referring_provider": claim.referring_provider_id,
            "receiving_provider": claim.provider_id,
            "concentration": round(referral_concentration, 2),
            "top_referral_target": claim.provider_top_referral_target,
            "total_claims": claim.provider_total_claims,
        }

        details = (
            f"Referral concentration at {referral_concentration:.1f}% "
            f"(threshold: {concentration_pct}%). "
            f"Referring provider {claim.referring_provider_id} sends majority "
            f"of referrals to provider {claim.provider_top_referral_target or claim.provider_id}"
        )

        return self._triggered(severity, confidence, evidence, details)
