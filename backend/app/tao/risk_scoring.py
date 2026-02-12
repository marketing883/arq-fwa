"""
Per-Action Risk Scoring — evaluates the risk of allowing an agent to perform
a specific action BEFORE execution.

This is distinct from the claim fraud risk score. This scores the operational
risk of permitting an autonomous agent to take an action.

Algorithm: weighted linear combination with policy multipliers.
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RiskTier(str, Enum):
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class RiskDecision(str, Enum):
    AUTO_APPROVE = "auto_approve"
    APPROVE_WITH_LOGGING = "auto_approve_with_logging"
    REQUIRE_HITL = "require_hitl_approval"
    DENY = "deny"


@dataclass
class ActionRiskInput:
    """Feature vector for per-action risk scoring."""
    action_type: str
    agent_id: str
    agent_trust_score: float              # [0.0 - 1.0]
    resource_sensitivity: float = 0.5     # [0.0 - 1.0], PHI=1.0, agg stats=0.1
    mutation_scope: str = "read"          # read, write, delete, escalate
    record_count: int = 1
    dollar_exposure: float = 0.0
    requires_phi_access: bool = False
    recent_action_count: int = 0
    recent_error_count: int = 0
    deviation_from_pattern: float = 0.0   # [0.0 - 1.0]
    business_hours: bool = True


@dataclass
class ContributingFactor:
    factor: str
    weight: float
    raw_value: float
    weighted_value: float


@dataclass
class ActionRiskResult:
    """Output of per-action risk scoring."""
    action_risk_score: float
    risk_tier: RiskTier
    decision: RiskDecision
    justification: str
    contributing_factors: list[ContributingFactor] = field(default_factory=list)


# Default weights (admin-configurable in production)
DEFAULT_WEIGHTS = {
    "w1_trust": 0.25,
    "w2_sensitivity": 0.20,
    "w3_mutation": 0.15,
    "w4_record_count": 0.10,
    "w5_dollar_exposure": 0.15,
    "w6_deviation": 0.15,
}

MUTATION_WEIGHTS = {
    "read": 0.1,
    "write": 0.5,
    "delete": 0.9,
    "escalate": 0.3,
}

# Risk tier thresholds → decisions
TIER_THRESHOLDS = [
    (0.0, 0.2, RiskTier.MINIMAL, RiskDecision.AUTO_APPROVE),
    (0.2, 0.4, RiskTier.LOW, RiskDecision.APPROVE_WITH_LOGGING),
    (0.4, 0.6, RiskTier.MODERATE, RiskDecision.APPROVE_WITH_LOGGING),
    (0.6, 0.8, RiskTier.HIGH, RiskDecision.REQUIRE_HITL),
    (0.8, 1.0, RiskTier.CRITICAL, RiskDecision.DENY),
]


class ActionRiskScorer:
    """Per-action risk scoring engine."""

    def __init__(self, weights: dict | None = None):
        self.weights = weights or DEFAULT_WEIGHTS

    def score(self, inp: ActionRiskInput) -> ActionRiskResult:
        """
        Score the risk of an agent action request.

        Returns an ActionRiskResult with score, tier, decision, and explanation.
        """
        w = self.weights
        factors: list[ContributingFactor] = []

        # Factor 1: Inverse trust (lower trust = higher risk)
        trust_risk = 1.0 - inp.agent_trust_score
        f1 = w["w1_trust"] * trust_risk
        factors.append(ContributingFactor("agent_trust_inverse", w["w1_trust"], trust_risk, f1))

        # Factor 2: Resource sensitivity
        f2 = w["w2_sensitivity"] * inp.resource_sensitivity
        factors.append(ContributingFactor("resource_sensitivity", w["w2_sensitivity"], inp.resource_sensitivity, f2))

        # Factor 3: Mutation scope
        mut_w = MUTATION_WEIGHTS.get(inp.mutation_scope, 0.5)
        f3 = w["w3_mutation"] * mut_w
        factors.append(ContributingFactor("mutation_scope", w["w3_mutation"], mut_w, f3))

        # Factor 4: Record count (log-scaled)
        rc = math.log(inp.record_count + 1) / 10.0
        f4 = w["w4_record_count"] * rc
        factors.append(ContributingFactor("record_count", w["w4_record_count"], rc, f4))

        # Factor 5: Dollar exposure
        de = min(inp.dollar_exposure / 1_000_000, 1.0)
        f5 = w["w5_dollar_exposure"] * de
        factors.append(ContributingFactor("dollar_exposure", w["w5_dollar_exposure"], de, f5))

        # Factor 6: Deviation from pattern
        f6 = w["w6_deviation"] * inp.deviation_from_pattern
        factors.append(ContributingFactor("deviation_from_pattern", w["w6_deviation"], inp.deviation_from_pattern, f6))

        base_risk = f1 + f2 + f3 + f4 + f5 + f6

        # Multipliers
        multiplier_reasons = []
        if not inp.business_hours:
            base_risk *= 1.3
            multiplier_reasons.append("off-hours (+30%)")
        if inp.recent_error_count > 3:
            base_risk *= 1.5
            multiplier_reasons.append(f"recent errors ({inp.recent_error_count}) (+50%)")
        if inp.requires_phi_access:
            base_risk *= 1.2
            multiplier_reasons.append("PHI access (+20%)")

        score = max(0.0, min(base_risk, 1.0))

        # Determine tier and decision
        tier = RiskTier.MINIMAL
        decision = RiskDecision.AUTO_APPROVE
        for low, high, t, d in TIER_THRESHOLDS:
            if low <= score < high or (high == 1.0 and score >= high):
                tier = t
                decision = d
                break

        justification = (
            f"Action '{inp.action_type}' by {inp.agent_id}: "
            f"risk={score:.3f} ({tier.value}). "
            f"Trust={inp.agent_trust_score:.2f}, "
            f"sensitivity={inp.resource_sensitivity:.2f}, "
            f"mutation={inp.mutation_scope}."
        )
        if multiplier_reasons:
            justification += f" Multipliers: {', '.join(multiplier_reasons)}."

        return ActionRiskResult(
            action_risk_score=score,
            risk_tier=tier,
            decision=decision,
            justification=justification,
            contributing_factors=factors,
        )
