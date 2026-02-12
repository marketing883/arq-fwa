"""
P6: Phantom Claims (Pharmacy) Detection

Detects pharmacy claims for members who have zero medical claims in a
lookback window (never visit a doctor but receive drugs), or whose
eligibility has expired.

Weight: 10.0 | Type: Fraud | Priority: HIGH
"""

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


class PhantomClaimsRule(BaseRule):
    rule_id = "P6"
    category = "Phantom Claims"
    fraud_type = "Fraud"
    claim_type = "pharmacy"
    default_weight = 10.0
    default_thresholds = {
        "no_medical_claims_days": 180,
        "check_eligibility": True,
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        check_eligibility = thresholds.get("check_eligibility", True)

        # Check for expired eligibility
        if check_eligibility and claim.member_eligibility_end is not None:
            if claim.fill_date > claim.member_eligibility_end:
                days_past = (claim.fill_date - claim.member_eligibility_end).days
                return self._triggered(
                    severity=2.5,
                    confidence=0.90,
                    evidence={
                        "member": claim.member_member_id,
                        "eligibility_end": str(claim.member_eligibility_end),
                        "fill_date": str(claim.fill_date),
                        "days_past_eligibility": days_past,
                        "pharmacy_name": claim.pharmacy_name,
                        "drug": claim.drug_name,
                        "claim_id": claim.claim_id,
                        "amount_billed": str(claim.amount_billed),
                    },
                    details=(
                        f"Pharmacy claim for member {claim.member_member_id} whose eligibility "
                        f"ended {claim.member_eligibility_end}. Claim filled {days_past} days "
                        f"after eligibility expiration. Drug: {claim.drug_name}, "
                        f"Amount: ${claim.amount_billed}"
                    ),
                )

        # Check for no medical claims in lookback window
        medical_claims_180d = claim.member_medical_claims_180d

        if medical_claims_180d == 0:
            # No medical claims at all — highly suspicious
            return self._triggered(
                severity=3.0,
                confidence=0.80,
                evidence={
                    "member": claim.member_member_id,
                    "last_medical_claim": "never",
                    "lookback_days": thresholds.get("no_medical_claims_days", 180),
                    "pharmacy_name": claim.pharmacy_name,
                    "drug": claim.drug_name,
                    "claim_id": claim.claim_id,
                    "amount_billed": str(claim.amount_billed),
                },
                details=(
                    f"Pharmacy claim for member {claim.member_member_id} who has zero "
                    f"medical claims in the last 180 days. Drug: {claim.drug_name}, "
                    f"Amount: ${claim.amount_billed}. No corroborating medical visits."
                ),
            )

        # Check if member is inactive
        if not claim.member_is_active:
            return self._triggered(
                severity=2.0,
                confidence=0.85,
                evidence={
                    "member": claim.member_member_id,
                    "member_is_active": False,
                    "pharmacy_name": claim.pharmacy_name,
                    "drug": claim.drug_name,
                    "claim_id": claim.claim_id,
                    "amount_billed": str(claim.amount_billed),
                },
                details=(
                    f"Pharmacy claim for inactive member {claim.member_member_id}. "
                    f"Drug: {claim.drug_name}, Amount: ${claim.amount_billed}"
                ),
            )

        return self._not_triggered()
