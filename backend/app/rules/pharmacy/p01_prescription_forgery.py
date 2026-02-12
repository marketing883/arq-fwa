"""
P1: Prescription Forgery Detection

Detects pharmacy claims where the prescriber NPI does not exist in the
providers table, or the prescriber is inactive / OIG-excluded.

Weight: 8.0 | Type: Fraud | Priority: MEDIUM
"""

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


class PrescriptionForgeryRule(BaseRule):
    rule_id = "P1"
    category = "Prescription Forgery"
    fraud_type = "Fraud"
    claim_type = "pharmacy"
    default_weight = 8.0
    default_thresholds = {
        "check_active": True,
        "check_exists": True,
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        check_exists = thresholds.get("check_exists", True)
        check_active = thresholds.get("check_active", True)

        # Check if prescriber NPI exists in the providers table
        if check_exists and not claim.prescriber_exists:
            return self._triggered(
                severity=3.0,
                confidence=0.95,
                evidence={
                    "prescriber_npi": claim.prescriber_npi,
                    "status": "not_found",
                    "drug": claim.drug_name,
                    "member": claim.member_member_id,
                    "claim_id": claim.claim_id,
                    "amount_billed": str(claim.amount_billed),
                },
                details=(
                    f"Prescriber NPI {claim.prescriber_npi} not found in provider registry. "
                    f"Drug: {claim.drug_name}, Amount: ${claim.amount_billed}"
                ),
            )

        # Check if prescriber is inactive
        if check_active and not claim.prescriber_is_active:
            return self._triggered(
                severity=2.0,
                confidence=0.90,
                evidence={
                    "prescriber_npi": claim.prescriber_npi,
                    "status": "inactive",
                    "prescriber_name": claim.prescriber_name,
                    "drug": claim.drug_name,
                    "member": claim.member_member_id,
                    "claim_id": claim.claim_id,
                    "amount_billed": str(claim.amount_billed),
                },
                details=(
                    f"Prescriber {claim.prescriber_name} (NPI: {claim.prescriber_npi}) is inactive. "
                    f"Drug: {claim.drug_name}, Amount: ${claim.amount_billed}"
                ),
            )

        # Check if prescriber is OIG-excluded
        if claim.prescriber_oig_excluded:
            return self._triggered(
                severity=3.0,
                confidence=0.95,
                evidence={
                    "prescriber_npi": claim.prescriber_npi,
                    "status": "oig_excluded",
                    "prescriber_name": claim.prescriber_name,
                    "drug": claim.drug_name,
                    "member": claim.member_member_id,
                    "claim_id": claim.claim_id,
                    "amount_billed": str(claim.amount_billed),
                },
                details=(
                    f"Prescriber {claim.prescriber_name} (NPI: {claim.prescriber_npi}) is on OIG exclusion list. "
                    f"Drug: {claim.drug_name}, Amount: ${claim.amount_billed}"
                ),
            )

        return self._not_triggered()
