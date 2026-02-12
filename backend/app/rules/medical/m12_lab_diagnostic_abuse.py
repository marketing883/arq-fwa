"""
M12: Lab/Diagnostic Abuse Detection

Detects providers who order laboratory or diagnostic tests on an
abnormally high percentage of their office visits, regardless of
diagnosis, indicating wasteful or abusive ordering patterns.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class LabDiagnosticAbuseRule(BaseRule):
    """
    Flags claims from providers whose lab order rate (percentage of
    office visits with lab orders on the same date) exceeds the
    threshold. Industry norm is approximately 40-50%.

    Uses the pre-computed provider_lab_order_rate from enrichment data.
    Only evaluates claims that are themselves lab/diagnostic claims
    (cpt_is_lab_diagnostic flag).
    """

    rule_id = "M12"
    category = "Lab/Diagnostic Abuse"
    fraud_type = "Waste"
    claim_type = "medical"
    default_weight = 5.0
    default_thresholds = {
        "lab_rate_max_pct": 70,
        "min_visits_for_pattern": 20,
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        lab_rate_max = thresholds.get(
            "lab_rate_max_pct", self.default_thresholds["lab_rate_max_pct"]
        )
        min_visits = thresholds.get(
            "min_visits_for_pattern",
            self.default_thresholds["min_visits_for_pattern"],
        )

        # Only evaluate lab/diagnostic claims
        if not claim.cpt_is_lab_diagnostic:
            return self._not_triggered()

        # Need enough visits to establish a pattern
        if claim.provider_total_claims < min_visits:
            return self._not_triggered()

        lab_rate = claim.provider_lab_order_rate

        if lab_rate < lab_rate_max:
            return self._not_triggered()

        # Graduated severity by overuse level
        severity = self.graduated_severity(
            lab_rate,
            [
                (70, 0.8),
                (85, 1.5),
                (95, 2.5),
            ],
        )

        confidence = 0.75 if claim.provider_total_claims >= 50 else 0.6

        evidence = {
            "lab_order_rate": round(lab_rate, 2),
            "benchmark": 45,
            "threshold": lab_rate_max,
            "total_claims": claim.provider_total_claims,
            "provider_id": claim.provider_id,
            "cpt_code": claim.cpt_code,
            "cpt_description": claim.cpt_description,
        }

        details = (
            f"Provider lab order rate at {lab_rate:.1f}% "
            f"(threshold: {lab_rate_max}%, benchmark: ~45%). "
            f"Provider has {claim.provider_total_claims} total claims. "
            f"Current claim: CPT {claim.cpt_code} "
            f"({claim.cpt_description or 'lab/diagnostic'})"
        )

        return self._triggered(severity, confidence, evidence, details)
