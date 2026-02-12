"""
P9: Invalid Prescriber Detection

Detects controlled substance prescriptions written by prescribers who
lack valid DEA registration or whose DEA schedule does not cover the
prescribed drug's schedule.

Weight: 8.5 | Type: Fraud | Priority: HIGH
"""

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


# DEA schedule hierarchy: lower number = more restricted
_SCHEDULE_RANK = {
    "CII": 2,
    "CIII": 3,
    "CIV": 4,
    "CV": 5,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
}


class InvalidPrescriberRule(BaseRule):
    rule_id = "P9"
    category = "Invalid Prescriber"
    fraud_type = "Fraud"
    claim_type = "pharmacy"
    default_weight = 8.5
    default_thresholds = {
        "check_dea": True,
        "check_schedule_match": True,
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        check_dea = thresholds.get("check_dea", True)
        check_schedule_match = thresholds.get("check_schedule_match", True)

        # Only relevant for controlled substances
        if not claim.is_controlled:
            return self._not_triggered()

        drug_schedule = claim.dea_schedule or claim.ndc_dea_schedule

        # Check if prescriber has no DEA registration at all
        if check_dea and not claim.prescriber_dea_registration:
            return self._triggered(
                severity=3.0,
                confidence=0.95,
                evidence={
                    "prescriber_npi": claim.prescriber_npi,
                    "prescriber_name": claim.prescriber_name,
                    "dea_status": "none",
                    "drug_schedule": drug_schedule,
                    "drug": claim.drug_name,
                    "claim_id": claim.claim_id,
                    "amount_billed": str(claim.amount_billed),
                },
                details=(
                    f"Prescriber {claim.prescriber_name} (NPI: {claim.prescriber_npi}) has "
                    f"no DEA registration but prescribed controlled substance "
                    f"{claim.drug_name} (Schedule {drug_schedule})."
                ),
            )

        # Check if prescriber's DEA schedule covers the drug's schedule
        if check_schedule_match and drug_schedule and claim.prescriber_dea_schedule:
            drug_rank = _SCHEDULE_RANK.get(drug_schedule, 99)
            prescriber_rank = _SCHEDULE_RANK.get(claim.prescriber_dea_schedule, 99)

            # Prescriber can only prescribe at their level or lower restriction
            # (higher rank number = less restricted). If drug is more restricted
            # than prescriber's authorization, it's a mismatch.
            if drug_rank < prescriber_rank:
                return self._triggered(
                    severity=2.0,
                    confidence=0.90,
                    evidence={
                        "prescriber_npi": claim.prescriber_npi,
                        "prescriber_name": claim.prescriber_name,
                        "dea_status": "schedule_mismatch",
                        "prescriber_dea_schedule": claim.prescriber_dea_schedule,
                        "drug_schedule": drug_schedule,
                        "drug": claim.drug_name,
                        "claim_id": claim.claim_id,
                        "amount_billed": str(claim.amount_billed),
                    },
                    details=(
                        f"Prescriber {claim.prescriber_name} (NPI: {claim.prescriber_npi}) "
                        f"is authorized for DEA Schedule {claim.prescriber_dea_schedule} "
                        f"but prescribed a Schedule {drug_schedule} drug ({claim.drug_name}). "
                        f"Schedule mismatch."
                    ),
                )

        return self._not_triggered()
