"""
Risk Scoring Engine (Phase 6)

Aggregates triggered rule results into a single 0-100 risk score per claim,
classifies risk level, and stores results.

Algorithm (from POC spec):
  Total Risk Score (0-100) = Normalized( SUM(Rule_Weight × Severity × Confidence) )
  Normalization: raw / max_possible × 100, clamped to [0, 100]
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rule, RuleResult, RiskScore


# Default thresholds — admin-configurable
DEFAULT_RISK_THRESHOLDS = {
    "low_max": 30,
    "medium_max": 60,
    "high_max": 85,
}


class ScoringEngine:
    """Calculates risk scores from rule evaluation results."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._rule_weights: dict[str, float] = {}
        self.risk_thresholds = DEFAULT_RISK_THRESHOLDS.copy()

    async def load_weights(self) -> None:
        """Load rule weights from DB."""
        result = await self.session.execute(select(Rule.rule_id, Rule.weight))
        for row in result:
            self._rule_weights[row[0]] = float(row[1])

    def classify_risk(self, score: float) -> str:
        """Classify a numeric score into a risk level."""
        if score <= self.risk_thresholds["low_max"]:
            return "low"
        elif score <= self.risk_thresholds["medium_max"]:
            return "medium"
        elif score <= self.risk_thresholds["high_max"]:
            return "high"
        else:
            return "critical"

    async def score_claim(
        self,
        claim_id: str,
        claim_type: str,
        rule_results: list[RuleResult],
        batch_id: str | None = None,
    ) -> RiskScore:
        """Calculate risk score for a claim from its rule results."""
        if not self._rule_weights:
            await self.load_weights()

        triggered = [r for r in rule_results if r.triggered]

        if not triggered:
            return RiskScore(
                claim_id=claim_id,
                claim_type=claim_type,
                total_score=Decimal("0"),
                risk_level="low",
                rules_triggered=0,
                rule_contributions={},
                confidence_factor=Decimal("1.0"),
                batch_id=batch_id,
            )

        # Calculate raw score and max possible
        raw_score = Decimal("0")
        max_possible = Decimal("0")
        contributions = {}
        total_confidence = Decimal("0")

        for rr in triggered:
            weight = Decimal(str(self._rule_weights.get(rr.rule_id, 5.0)))
            severity = rr.severity or Decimal("1.0")
            confidence = rr.confidence or Decimal("1.0")

            contribution = weight * severity * confidence
            raw_score += contribution
            max_possible += weight * Decimal("3.0")  # Max severity is 3.0

            contributions[rr.rule_id] = {
                "weight": float(weight),
                "severity": float(severity),
                "confidence": float(confidence),
                "contribution": float(contribution),
            }
            total_confidence += confidence

        # Normalize to 0-100
        if max_possible > 0:
            normalized = (raw_score / max_possible) * 100
        else:
            normalized = Decimal("0")

        normalized = min(normalized, Decimal("100"))
        normalized = normalized.quantize(Decimal("0.01"))

        avg_confidence = total_confidence / len(triggered) if triggered else Decimal("1.0")

        risk_level = self.classify_risk(float(normalized))

        return RiskScore(
            claim_id=claim_id,
            claim_type=claim_type,
            total_score=normalized,
            risk_level=risk_level,
            rules_triggered=len(triggered),
            rule_contributions=contributions,
            confidence_factor=avg_confidence.quantize(Decimal("0.01")),
            batch_id=batch_id,
        )

    async def score_batch(
        self,
        results: dict[str, list[RuleResult]],
        claim_type: str,
        batch_id: str | None = None,
    ) -> list[RiskScore]:
        """Score all claims in a batch."""
        scores = []
        for claim_id, rule_results in results.items():
            score = await self.score_claim(claim_id, claim_type, rule_results, batch_id)
            scores.append(score)
        return scores

    async def save_scores(self, scores: list[RiskScore]) -> int:
        """Persist scores to DB. Returns count saved."""
        count = 0
        batch = []
        for score in scores:
            batch.append(score)
            count += 1
            if len(batch) >= 500:
                self.session.add_all(batch)
                await self.session.flush()
                batch = []

        if batch:
            self.session.add_all(batch)
            await self.session.flush()

        return count
