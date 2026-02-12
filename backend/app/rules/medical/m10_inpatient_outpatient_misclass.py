"""
M10: Inpatient/Outpatient Misclassification Detection

Detects claims billed as inpatient admissions (place_of_service=21) with
very short stays for procedures that are typically performed in outpatient
settings, indicating upcoding from outpatient to inpatient rates.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class InpatientOutpatientMisclassRule(BaseRule):
    """
    Flags claims with inpatient place of service (21) but length of stay
    at or below the threshold (default 1 day) AND the CPT code is
    typically performed outpatient (cpt_is_outpatient_typical from
    reference data).

    Severity is graduated by the cost difference between inpatient and
    outpatient billing.
    """

    rule_id = "M10"
    category = "IP/OP Misclassification"
    fraud_type = "Fraud"
    claim_type = "medical"
    default_weight = 6.0
    default_thresholds = {
        "max_los_for_flag": 1,
        "outpatient_cpt_list": "from_reference",
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        max_los = thresholds.get(
            "max_los_for_flag", self.default_thresholds["max_los_for_flag"]
        )

        # Must be an inpatient claim
        if claim.place_of_service != "21":
            return self._not_triggered()

        # Check length of stay
        los = claim.length_of_stay
        if los is None or los > max_los:
            return self._not_triggered()

        # Check if the procedure is typically outpatient
        if not claim.cpt_is_outpatient_typical:
            return self._not_triggered()

        amount_billed = float(claim.amount_billed)

        # Estimate the cost difference — use non-facility price as outpatient benchmark
        outpatient_cost = float(claim.cpt_non_facility_price or 0)
        cost_difference = amount_billed - outpatient_cost if outpatient_cost > 0 else amount_billed

        # Graduated severity by cost difference
        severity = self.graduated_severity(
            cost_difference,
            [
                (0, 0.5),
                (1000, 1.5),
                (5000, 2.5),
            ],
        )

        confidence = 0.8 if claim.cpt_description else 0.65

        evidence = {
            "place_of_service": claim.place_of_service,
            "length_of_stay": los,
            "procedure": claim.cpt_code,
            "cpt_description": claim.cpt_description,
            "expected_setting": "outpatient",
            "amount_billed": amount_billed,
            "outpatient_benchmark": outpatient_cost,
            "cost_difference": round(cost_difference, 2),
        }

        details = (
            f"Inpatient claim (POS 21) with LOS={los} day(s) for "
            f"CPT {claim.cpt_code} ({claim.cpt_description or 'unknown'}), "
            f"which is typically an outpatient procedure. "
            f"Billed ${amount_billed:,.2f} vs outpatient benchmark "
            f"${outpatient_cost:,.2f}"
        )

        return self._triggered(severity, confidence, evidence, details)
