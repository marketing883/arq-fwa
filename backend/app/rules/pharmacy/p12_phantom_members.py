"""
P12: Phantom Members Detection

Detects pharmacy claims submitted for members whose eligibility has
expired (eligibility_end < fill_date).

Weight: 8.0 | Type: Fraud | Priority: HIGH
"""

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedPharmacyClaim


class PhantomMembersRule(BaseRule):
    rule_id = "P12"
    category = "Phantom Members"
    fraud_type = "Fraud"
    claim_type = "pharmacy"
    default_weight = 8.0
    default_thresholds = {
        "grace_period_days": 0,
    }

    async def evaluate(
        self, claim: EnrichedPharmacyClaim, thresholds: dict
    ) -> RuleEvaluation:
        grace_period_days = thresholds.get("grace_period_days", 0)

        # Need eligibility end date to evaluate
        if claim.member_eligibility_end is None:
            return self._not_triggered()

        # Calculate days past eligibility, accounting for grace period
        days_past = (claim.fill_date - claim.member_eligibility_end).days - grace_period_days

        if days_past <= 0:
            return self._not_triggered()

        # Graduated severity by days past eligibility
        severity = self.graduated_severity(
            float(days_past),
            [
                (1.0, 1.0),    # 1-30 days past -> 1.0
                (31.0, 2.0),   # 31-90 days past -> 2.0
                (91.0, 3.0),   # >90 days past -> 3.0
            ],
        )

        return self._triggered(
            severity=severity,
            confidence=0.90,
            evidence={
                "member": claim.member_member_id,
                "eligibility_end": str(claim.member_eligibility_end),
                "fill_date": str(claim.fill_date),
                "days_past": days_past,
                "grace_period_days": grace_period_days,
                "drug": claim.drug_name,
                "pharmacy": claim.pharmacy_name,
                "claim_id": claim.claim_id,
                "amount_billed": str(claim.amount_billed),
            },
            details=(
                f"Pharmacy claim for member {claim.member_member_id} whose eligibility "
                f"ended on {claim.member_eligibility_end}. Fill date: {claim.fill_date} "
                f"({days_past} days past eligibility). "
                f"Drug: {claim.drug_name}, Amount: ${claim.amount_billed}"
            ),
        )
