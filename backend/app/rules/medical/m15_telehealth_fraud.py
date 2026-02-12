"""
M15: Telehealth Fraud Detection

Detects two types of telehealth fraud:
(a) Telehealth visits billed at in-person (non-facility) rates instead
    of the lower facility rate.
(b) Providers with an impossibly high volume of telehealth visits per day.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class TelehealthFraudRule(BaseRule):
    """
    Flags telehealth claims (place_of_service='02') where:
    1. The amount billed exceeds the facility price (telehealth should use
       facility rates), indicating billing at in-person rates.
    2. The provider's maximum telehealth visits per day exceeds the
       configured threshold (e.g., >40 per day is physically impossible).

    Either condition independently triggers the rule.
    """

    rule_id = "M15"
    category = "Telehealth Fraud"
    fraud_type = "Fraud"
    claim_type = "medical"
    default_weight = 6.0
    default_thresholds = {
        "max_telehealth_per_day": 40,
        "check_pricing": True,
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        max_per_day = thresholds.get(
            "max_telehealth_per_day",
            self.default_thresholds["max_telehealth_per_day"],
        )
        check_pricing = thresholds.get(
            "check_pricing", self.default_thresholds["check_pricing"]
        )

        # Must be a telehealth claim
        if claim.place_of_service != "02":
            return self._not_triggered()

        issues = []
        max_severity = 0.0

        # Check volume — provider telehealth per day max
        telehealth_daily_max = claim.provider_telehealth_per_day_max
        if telehealth_daily_max > max_per_day:
            volume_severity = self.graduated_severity(
                telehealth_daily_max,
                [
                    (40, 1.0),
                    (60, 2.0),
                    (80, 3.0),
                ],
            )
            max_severity = max(max_severity, volume_severity)
            issues.append(f"volume ({telehealth_daily_max} visits/day)")

        # Check pricing — telehealth should use facility rate
        if check_pricing and claim.cpt_facility_price and claim.cpt_non_facility_price:
            facility_price = float(claim.cpt_facility_price)
            non_facility_price = float(claim.cpt_non_facility_price)
            billed = float(claim.amount_billed)

            # If billed is closer to non-facility price than facility price,
            # the provider may be billing at in-person rates
            if facility_price < non_facility_price and billed > facility_price * 1.1:
                pricing_severity = 1.5
                max_severity = max(max_severity, pricing_severity)
                issues.append(
                    f"pricing (billed ${billed:,.2f} vs "
                    f"facility ${facility_price:,.2f})"
                )

        if not issues:
            return self._not_triggered()

        confidence = 0.8

        evidence = {
            "telehealth_count_day": telehealth_daily_max,
            "max_allowed_per_day": max_per_day,
            "date": str(claim.service_date),
            "amount_billed": float(claim.amount_billed),
            "facility_price": float(claim.cpt_facility_price) if claim.cpt_facility_price else None,
            "non_facility_price": float(claim.cpt_non_facility_price) if claim.cpt_non_facility_price else None,
            "pricing_issue": "pricing" in " ".join(issues),
            "volume_issue": "volume" in " ".join(issues),
            "provider_id": claim.provider_id,
        }

        details = (
            f"Telehealth fraud indicators: {', '.join(issues)}. "
            f"Provider {claim.provider_id} on {claim.service_date}, "
            f"CPT {claim.cpt_code}"
        )

        return self._triggered(max_severity, confidence, evidence, details)
