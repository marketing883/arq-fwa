"""
M1: Upcoding Detection

Detects providers billing at rates significantly above CMS expected costs,
indicating potential upcoding of services to higher-reimbursement CPT codes.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class UpcodingRule(BaseRule):
    """
    Flags claims where amount_billed exceeds the CMS expected price
    by more than a configurable percentage AND dollar threshold.

    Severity is graduated by the overpayment ratio.
    """

    rule_id = "M1"
    category = "Upcoding"
    fraud_type = "Fraud"
    claim_type = "medical"
    default_weight = 9.0
    default_thresholds = {
        "percent_over": 20,
        "min_dollar_amount": 300,
        "benchmark": "CMS_fee_schedule",
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        percent_over = thresholds.get("percent_over", self.default_thresholds["percent_over"])
        min_dollar = thresholds.get("min_dollar_amount", self.default_thresholds["min_dollar_amount"])

        # Determine the CMS expected price based on place of service
        expected_price = claim.cpt_facility_price
        if claim.place_of_service != "21":  # Non-inpatient uses non-facility price
            expected_price = claim.cpt_non_facility_price or claim.cpt_facility_price

        if expected_price is None or expected_price <= 0:
            return self._not_triggered()

        amount_billed = float(claim.amount_billed)
        expected = float(expected_price)

        # Calculate overpayment
        dollar_over = amount_billed - expected
        if expected > 0:
            pct_over = (dollar_over / expected) * 100
        else:
            return self._not_triggered()

        # Check both thresholds
        threshold_amount = expected * (1 + percent_over / 100)
        if amount_billed <= threshold_amount or dollar_over <= min_dollar:
            return self._not_triggered()

        # Graduated severity by overpayment ratio
        severity = self.graduated_severity(
            pct_over / 100,
            [
                (0.10, 0.5),
                (0.25, 1.0),
                (0.50, 1.8),
                (1.00, 3.0),
            ],
        )

        confidence = 0.9 if claim.cpt_description else 0.7

        evidence = {
            "billed": amount_billed,
            "expected": expected,
            "overpayment_pct": round(pct_over, 2),
            "dollar_over": round(dollar_over, 2),
            "cpt_code": claim.cpt_code,
            "benchmark_source": thresholds.get("benchmark", "CMS_fee_schedule"),
        }

        details = (
            f"Billed ${amount_billed:,.2f} vs CMS expected ${expected:,.2f} "
            f"({pct_over:.1f}% over, ${dollar_over:,.2f} excess) "
            f"for CPT {claim.cpt_code}"
        )

        return self._triggered(severity, confidence, evidence, details)
