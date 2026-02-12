"""
M13: Provider Ghosting Detection

Detects claims submitted by providers who are inactive or excluded from
federal healthcare programs (OIG exclusion list), indicating billing
by "ghost" providers who should not be rendering services.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class ProviderGhostingRule(BaseRule):
    """
    Flags claims where:
    1. The provider's is_active flag is False (inactive/deactivated provider).
    2. The provider is on the OIG exclusion list (oig_excluded=True).

    OIG exclusion carries higher severity (3.0) than simple inactivity (2.0)
    because billing with an excluded provider is a federal offense.
    """

    rule_id = "M13"
    category = "Provider Ghosting"
    fraud_type = "Fraud"
    claim_type = "medical"
    default_weight = 7.0
    default_thresholds = {
        "check_active_status": True,
        "check_oig_exclusion": True,
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        check_active = thresholds.get(
            "check_active_status",
            self.default_thresholds["check_active_status"],
        )
        check_oig = thresholds.get(
            "check_oig_exclusion",
            self.default_thresholds["check_oig_exclusion"],
        )

        reasons = []
        max_severity = 0.0

        # Check OIG exclusion (higher severity)
        if check_oig and claim.provider_oig_excluded:
            reasons.append("Provider is on OIG exclusion list")
            max_severity = max(max_severity, 3.0)

        # Check active status
        if check_active and not claim.provider_is_active:
            reasons.append("Provider is inactive/deactivated")
            max_severity = max(max_severity, 2.0)

        if not reasons:
            return self._not_triggered()

        confidence = 0.95  # High confidence — based on provider registry data

        evidence = {
            "provider_npi": claim.provider_npi,
            "provider_name": claim.provider_name,
            "provider_id": claim.provider_id,
            "active_status": claim.provider_is_active,
            "oig_excluded": claim.provider_oig_excluded,
            "reasons": reasons,
            "claim_amount": float(claim.amount_billed),
            "service_date": str(claim.service_date),
        }

        details = (
            f"Ghost provider detected: {'; '.join(reasons)}. "
            f"Provider {claim.provider_npi or claim.provider_id} "
            f"({claim.provider_name or 'unknown'}) "
            f"billed ${float(claim.amount_billed):,.2f} on {claim.service_date}"
        )

        return self._triggered(max_severity, confidence, evidence, details)
