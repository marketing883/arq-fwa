"""
Pattern Confidence Service — computes confidence scores for fraud patterns
by analysing historical case outcomes and rule effectiveness.

A rule with high historical accuracy (many true-positive confirmed cases vs
false positives) produces higher confidence. New rules or those with few
resolved cases default to a moderate confidence of 0.5.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InvestigationCase, RuleResult, RiskScore


class PatternConfidenceService:
    """Produces pattern-level confidence metrics for a given claim."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute_for_claim(self, claim_id: str) -> dict[str, Any]:
        """Return confidence metadata for *claim_id*.

        Response shape::

            {
              "claim_id": "...",
              "overall_confidence": 0.82,
              "pattern_scores": [
                {
                  "rule_id": "M1",
                  "rule_confidence": 0.90,
                  "historical_accuracy": 0.88,
                  "sample_size": 124,
                  "confirmed_rate": 0.88,
                }
              ]
            }
        """

        # 1. Get the rule results for the claim
        rr_q = await self.db.execute(
            select(RuleResult).where(
                and_(RuleResult.claim_id == claim_id, RuleResult.triggered == True)  # noqa: E712
            )
        )
        triggered_rules = list(rr_q.scalars())

        if not triggered_rules:
            return {
                "claim_id": claim_id,
                "overall_confidence": 0.0,
                "pattern_scores": [],
            }

        # 2. For each triggered rule, compute historical accuracy
        pattern_scores: list[dict[str, Any]] = []
        weighted_sum = 0.0
        weight_total = 0.0

        for rr in triggered_rules:
            rule_confidence = float(rr.confidence) if rr.confidence is not None else 0.5
            accuracy, sample_size, confirmed_rate = await self._historical_accuracy(rr.rule_id)

            # Blend rule confidence with historical accuracy
            if sample_size >= 10:
                blended = 0.4 * rule_confidence + 0.6 * accuracy
            elif sample_size >= 3:
                blended = 0.6 * rule_confidence + 0.4 * accuracy
            else:
                blended = rule_confidence  # Not enough history

            severity_weight = float(rr.severity) if rr.severity is not None else 1.0
            weighted_sum += blended * severity_weight
            weight_total += severity_weight

            pattern_scores.append({
                "rule_id": rr.rule_id,
                "rule_confidence": round(rule_confidence, 3),
                "historical_accuracy": round(accuracy, 3),
                "sample_size": sample_size,
                "confirmed_rate": round(confirmed_rate, 3),
            })

        overall = weighted_sum / weight_total if weight_total > 0 else 0.5

        return {
            "claim_id": claim_id,
            "overall_confidence": round(overall, 3),
            "pattern_scores": pattern_scores,
        }

    async def _historical_accuracy(self, rule_id: str) -> tuple[float, int, float]:
        """Return (accuracy, sample_size, confirmed_rate) for a rule.

        We look at all claims where this rule triggered, check whether the
        resulting investigation case was resolved as 'confirmed fraud'
        (resolution_path == 'confirmed') vs 'false positive' (resolution_path
        == 'false_positive').  Unresolved cases are excluded.
        """

        # Claims where this rule triggered
        triggered_claims = (
            select(RuleResult.claim_id)
            .where(and_(RuleResult.rule_id == rule_id, RuleResult.triggered == True))  # noqa: E712
        )

        # Resolved cases for those claims
        resolved_q = await self.db.execute(
            select(
                InvestigationCase.resolution_path,
                func.count().label("cnt"),
            )
            .where(
                and_(
                    InvestigationCase.claim_id.in_(triggered_claims),
                    InvestigationCase.status.in_(["resolved", "closed"]),
                    InvestigationCase.resolution_path.isnot(None),
                )
            )
            .group_by(InvestigationCase.resolution_path)
        )
        rows = resolved_q.all()

        if not rows:
            return 0.5, 0, 0.0  # no history

        count_map = {row[0]: row[1] for row in rows}
        confirmed = count_map.get("confirmed", 0)
        false_positive = count_map.get("false_positive", 0)
        total = confirmed + false_positive

        if total == 0:
            return 0.5, 0, 0.0

        confirmed_rate = confirmed / total
        # Accuracy = confirmed rate for this context
        accuracy = confirmed_rate

        return accuracy, total, confirmed_rate
