"""
P11: Compound Drug Fraud Detection

Detects compounding pharmacy claims with abnormally high dollar amounts,
which is a common vector for pharmacy fraud.

Weight: 7.0 | Type: Fraud | Priority: LOW
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


class CompoundDrugFraudRule(BaseRule):
    rule_id = "P11"
    category = "Compound Drug Fraud"
    fraud_type = "Fraud"
    claim_type = "pharmacy"
    default_weight = 7.0
    default_thresholds = {
        "max_compound_amount": 3000,
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        max_compound_amount = Decimal(
            str(thresholds.get("max_compound_amount", 3000))
        )

        # Only applies to compounding pharmacies
        if claim.pharmacy_type != "compounding":
            return self._not_triggered()

        if claim.amount_billed <= max_compound_amount:
            return self._not_triggered()

        amount = float(claim.amount_billed)

        # Graduated severity by claim amount
        severity = self.graduated_severity(
            amount,
            [
                (3000.0, 1.0),    # $3K-$5K -> 1.0
                (5000.0, 2.0),    # $5K-$10K -> 2.0
                (10000.0, 3.0),   # >$10K -> 3.0
            ],
        )

        return self._triggered(
            severity=severity,
            confidence=0.80,
            evidence={
                "pharmacy": claim.pharmacy_name,
                "pharmacy_npi": claim.pharmacy_npi,
                "pharmacy_type": claim.pharmacy_type,
                "amount": str(claim.amount_billed),
                "threshold": str(max_compound_amount),
                "drug": claim.drug_name,
                "member": claim.member_member_id,
                "claim_id": claim.claim_id,
            },
            details=(
                f"Compounding pharmacy {claim.pharmacy_name} billed "
                f"${claim.amount_billed} for {claim.drug_name} "
                f"(threshold: ${max_compound_amount}). "
                f"High-cost compound drug claim."
            ),
        )
