"""
Rule Trace Service — generates human-readable, step-by-step rule evaluation
explanations for a given claim.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RuleResult, RiskScore, Rule


class RuleTraceService:
    """Builds a detailed rule-evaluation trace for a single claim."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def get_trace(self, claim_id: str) -> dict[str, Any] | None:
        """Return a full rule trace dict for *claim_id*, or ``None`` when
        no rule results exist for the claim."""

        # 1. Fetch all RuleResult rows for the claim
        rr_q = await self.db.execute(
            select(RuleResult).where(RuleResult.claim_id == claim_id)
        )
        rule_results: list[RuleResult] = list(rr_q.scalars())

        if not rule_results:
            return None

        # 2. Fetch the RiskScore for the claim
        rs_q = await self.db.execute(
            select(RiskScore).where(RiskScore.claim_id == claim_id)
        )
        risk_score: RiskScore | None = rs_q.scalar_one_or_none()

        # 3. Fetch Rule definitions for every rule_id we saw
        rule_ids = {rr.rule_id for rr in rule_results}
        rules_q = await self.db.execute(
            select(Rule).where(Rule.rule_id.in_(rule_ids))
        )
        rules_by_id: dict[str, Rule] = {
            r.rule_id: r for r in rules_q.scalars()
        }

        # 4. Build contribution map from the risk score (if available)
        #    rule_contributions values are dicts: {"weight":…,"contribution":…}
        contributions: dict[str, float] = {}
        if risk_score and risk_score.rule_contributions:
            for k, v in risk_score.rule_contributions.items():
                if isinstance(v, dict):
                    contributions[k] = float(v.get("contribution", 0.0))
                else:
                    contributions[k] = float(v)

        # 5. Build step entries
        steps: list[dict[str, Any]] = []
        for rr in rule_results:
            rule_def = rules_by_id.get(rr.rule_id)
            weight = float(rule_def.weight) if rule_def else 0.0
            contribution = contributions.get(rr.rule_id, 0.0)

            explanation = self._build_explanation(rr, rule_def)

            steps.append({
                "rule_id": rr.rule_id,
                "rule_name": rule_def.description if rule_def else rr.rule_id,
                "category": rule_def.category if rule_def else "Unknown",
                "fraud_type": rule_def.fraud_type if rule_def else "Unknown",
                "triggered": rr.triggered,
                "severity": float(rr.severity) if rr.severity is not None else None,
                "confidence": float(rr.confidence) if rr.confidence is not None else None,
                "weight": weight,
                "contribution": contribution,
                "explanation": explanation,
                "evidence": rr.evidence or {},
            })

        # 6. Sort: triggered rules first (by contribution desc), then
        #    non-triggered rules (alphabetical by rule_id)
        triggered = [s for s in steps if s["triggered"]]
        passed = [s for s in steps if not s["triggered"]]

        triggered.sort(key=lambda s: s["contribution"], reverse=True)
        passed.sort(key=lambda s: s["rule_id"])

        sorted_steps = triggered + passed

        # Number the steps sequentially
        for idx, step in enumerate(sorted_steps, start=1):
            step["step"] = idx

        # 7. Assemble the response
        total_score = float(risk_score.total_score) if risk_score else 0.0
        risk_level = risk_score.risk_level if risk_score else "unknown"
        rules_triggered_count = len(triggered)
        rules_passed_count = len(passed)

        return {
            "claim_id": claim_id,
            "total_score": total_score,
            "risk_level": risk_level,
            "steps": sorted_steps,
            "score_calculation": {
                "formula": "SUM(weight x severity x confidence) / max_possible x 100",
                "rules_triggered": rules_triggered_count,
                "rules_passed": rules_passed_count,
            },
        }

    # ------------------------------------------------------------------
    # Explanation templates
    # ------------------------------------------------------------------

    @staticmethod
    def _build_explanation(rr: RuleResult, rule_def: Rule | None) -> str:
        """Generate a human-readable explanation from the evidence dict
        and optional rule definition."""

        evidence: dict[str, Any] = rr.evidence or {}

        # Template 1 — high-volume / daily count pattern
        if "daily_count" in evidence:
            specialty = evidence.get("specialty", "this specialty")
            specialty_average = evidence.get("specialty_average", "N/A")
            ratio = evidence.get("ratio", "N/A")
            threshold = evidence.get("threshold", "N/A")
            return (
                f"Provider billed {evidence['daily_count']} patients on this date. "
                f"Average for {specialty} is {specialty_average}. "
                f"This is {ratio}x above the threshold of {threshold}."
            )

        # Template 2 — billed amount vs expected max
        if "billed_amount" in evidence and "expected_max" in evidence:
            billed = evidence["billed_amount"]
            expected = evidence["expected_max"]
            ratio = evidence.get("ratio", "N/A")
            cpt_code = evidence.get("cpt_code", "N/A")
            benchmark = evidence.get("benchmark", "N/A")
            return (
                f"Billed ${billed} vs expected max of ${expected} "
                f"({ratio}x over). "
                f"CMS benchmark for {cpt_code}: ${benchmark}."
            )

        # Fallback — use the rule's detection_logic + key evidence values
        if rule_def and rule_def.detection_logic:
            base = rule_def.detection_logic
        else:
            base = rr.details or "Rule evaluated"

        if evidence:
            key_values = ", ".join(
                f"{k}={v}" for k, v in evidence.items()
            )
            return f"{base}. Evidence: {key_values}"

        return base
