"""
M8: Modifier Misuse Detection

Detects providers who use CPT modifiers 25 (separately identifiable E&M)
or 59 (distinct procedural service) at rates far exceeding industry norms,
indicating potential abuse to bypass bundling edits.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class ModifierMisuseRule(BaseRule):
    """
    Flags claims where the provider's modifier usage rate exceeds
    configurable thresholds. Industry benchmark for modifier 25 is ~30%.

    Only evaluates claims that actually have modifier 25 or 59, and
    checks the provider's overall rate for that modifier.
    """

    rule_id = "M8"
    category = "Modifier Misuse"
    fraud_type = "Fraud"
    claim_type = "medical"
    default_weight = 5.5
    default_thresholds = {
        "modifier_25_max_pct": 40,
        "modifier_59_max_pct": 35,
        "min_claims_for_pattern": 20,
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        mod25_max = thresholds.get(
            "modifier_25_max_pct",
            self.default_thresholds["modifier_25_max_pct"],
        )
        mod59_max = thresholds.get(
            "modifier_59_max_pct",
            self.default_thresholds["modifier_59_max_pct"],
        )
        min_claims = thresholds.get(
            "min_claims_for_pattern",
            self.default_thresholds["min_claims_for_pattern"],
        )

        # Only evaluate if this claim has a relevant modifier
        if not claim.cpt_modifier:
            return self._not_triggered()

        # Need enough claims to establish a pattern
        if claim.provider_total_claims < min_claims:
            return self._not_triggered()

        modifier = claim.cpt_modifier
        usage_rate = 0.0
        threshold_rate = 0.0
        benchmark = 0.0

        if "25" in modifier:
            usage_rate = claim.provider_modifier_25_rate
            threshold_rate = mod25_max
            benchmark = 30.0  # Industry norm ~30%
        elif "59" in modifier:
            usage_rate = claim.provider_modifier_59_rate
            threshold_rate = mod59_max
            benchmark = 25.0  # Industry norm ~25%
        else:
            return self._not_triggered()

        if usage_rate < threshold_rate:
            return self._not_triggered()

        # Graduated severity by overuse level
        severity = self.graduated_severity(
            usage_rate,
            [
                (40, 0.8),
                (60, 1.5),
                (80, 2.5),
            ],
        )

        confidence = 0.8 if claim.provider_total_claims >= 50 else 0.65

        evidence = {
            "modifier": modifier,
            "usage_rate": round(usage_rate, 2),
            "threshold_rate": threshold_rate,
            "benchmark_rate": benchmark,
            "total_claims": claim.provider_total_claims,
            "provider_id": claim.provider_id,
        }

        details = (
            f"Modifier {modifier} used on {usage_rate:.1f}% of claims "
            f"(threshold: {threshold_rate}%, benchmark: {benchmark}%). "
            f"Provider has {claim.provider_total_claims} total claims"
        )

        return self._triggered(severity, confidence, evidence, details)
