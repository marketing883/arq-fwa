"""
Base rule class for all FWA detection rules.

Every rule implements `evaluate()` which takes an enriched claim
and returns a RuleEvaluation result.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class RuleEvaluation:
    """Result of evaluating a single rule against a single claim."""
    rule_id: str
    triggered: bool
    severity: Decimal = Decimal("0")       # 0.0 - 3.0
    confidence: Decimal = Decimal("1.0")   # 0.3 - 1.0
    evidence: dict = field(default_factory=dict)
    details: str = ""


class BaseRule(ABC):
    """Abstract base class for all FWA detection rules."""

    rule_id: str
    category: str
    fraud_type: str         # "Fraud" | "Waste" | "Abuse"
    claim_type: str         # "medical" | "pharmacy"
    default_weight: float
    default_thresholds: dict

    @abstractmethod
    async def evaluate(self, claim, thresholds: dict) -> RuleEvaluation:
        """
        Evaluate a single enriched claim against this rule.

        Args:
            claim: EnrichedMedicalClaim or EnrichedPharmacyClaim
            thresholds: Admin-configurable thresholds from DB

        Returns:
            RuleEvaluation with triggered, severity, confidence, evidence, details
        """
        pass

    def _not_triggered(self) -> RuleEvaluation:
        """Helper for rules that don't fire."""
        return RuleEvaluation(rule_id=self.rule_id, triggered=False)

    def _triggered(
        self,
        severity: float,
        confidence: float,
        evidence: dict,
        details: str,
    ) -> RuleEvaluation:
        """Helper for rules that fire."""
        return RuleEvaluation(
            rule_id=self.rule_id,
            triggered=True,
            severity=Decimal(str(min(max(severity, 0.1), 3.0))),
            confidence=Decimal(str(min(max(confidence, 0.3), 1.0))),
            evidence=evidence,
            details=details,
        )

    @staticmethod
    def graduated_severity(value: float, thresholds: list[tuple[float, float]]) -> float:
        """
        Calculate graduated severity from a list of (threshold, severity) tuples.
        Tuples should be in ascending order of threshold.

        Example: graduated_severity(0.35, [(0.10, 0.5), (0.25, 1.0), (0.50, 1.8), (1.0, 3.0)])
        Returns 1.8 because 0.35 >= 0.25 but < 0.50
        """
        result = thresholds[0][1] if thresholds else 1.0
        for threshold_val, sev in thresholds:
            if value >= threshold_val:
                result = sev
            else:
                break
        return result
