"""
M4: Phantom Billing Detection

Detects claims for services that likely never occurred — the provider has
minimal other activity and the member has no corroborating claims nearby.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class PhantomBillingRule(BaseRule):
    """
    Flags claims from providers with very few claims in the same 30-day
    period AND where the member has no other claims within a configurable
    corroboration window (default 7 days).

    Severity is always high (2.0) if triggered; 3.0 if the provider
    has NO other claims at all.
    """

    rule_id = "M4"
    category = "Phantom Billing"
    fraud_type = "Fraud"
    claim_type = "medical"
    default_weight = 10.0
    default_thresholds = {
        "min_provider_claims_period": 5,
        "corroboration_window_days": 7,
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        min_provider_claims = thresholds.get(
            "min_provider_claims_period",
            self.default_thresholds["min_provider_claims_period"],
        )

        # Check provider claim volume in 30-day period
        provider_claims_30d = claim.provider_claims_30d

        if provider_claims_30d >= min_provider_claims:
            return self._not_triggered()

        # Check member corroborating claims — member_claims_30d is used as a
        # proxy.  If member also has very few claims, there is no corroboration.
        member_claims = claim.member_claims_30d

        # If the member has other recent claims, there is some corroboration
        if member_claims > 0 and provider_claims_30d > 0:
            return self._not_triggered()

        # Determine severity
        if provider_claims_30d == 0:
            severity = 3.0  # Provider has NO other claims — highly suspicious
        else:
            severity = 2.0  # Provider has very few claims

        confidence = 0.8
        amount = float(claim.amount_billed)

        evidence = {
            "provider_claim_count_30d": provider_claims_30d,
            "member_corroborating_claims": member_claims,
            "claim_amount": amount,
            "provider_id": claim.provider_id,
            "member_id": claim.member_id,
            "service_date": str(claim.service_date),
        }

        details = (
            f"Potential phantom billing: provider has only {provider_claims_30d} "
            f"claims in 30-day period (threshold: {min_provider_claims}) "
            f"and member has {member_claims} corroborating claims. "
            f"Claim amount: ${amount:,.2f}"
        )

        return self._triggered(severity, confidence, evidence, details)
