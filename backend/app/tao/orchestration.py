"""
Orchestration Controller — the central decision point for all agent actions.

Flow:
    1. Agent requests an action
    2. Validate existing capability token (or request new one)
    3. Calculate per-action risk score
    4. Check agent trust / escalation level
    5. Decision: auto-approve, approve-with-logging, require HITL, or deny
    6. If approved: issue scoped token, record in lineage graph
    7. If HITL required: create HITLRequest, pause until resolved
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.tao.risk_scoring import (
    ActionRiskScorer, ActionRiskInput, ActionRiskResult,
    RiskDecision, RiskTier,
)
from app.tao.trust import TrustManager
from app.tao.capability_tokens import CapabilityTokenService
from app.tao.lineage import LineageService
from app.tao.models import HITLRequest, CapabilityToken
from app.auth.data_classification import Sensitivity, TOOL_SENSITIVITY

logger = logging.getLogger(__name__)

# Actions that ALWAYS require HITL regardless of risk score
ALWAYS_HITL_ACTIONS = frozenset({
    "delete_case", "change_rule_config", "override_score",
    "release_phi", "export_financial",
})

# Map tool sensitivity to resource_sensitivity float
SENSITIVITY_TO_FLOAT: dict[Sensitivity, float] = {
    Sensitivity.PUBLIC: 0.1,
    Sensitivity.INTERNAL: 0.3,
    Sensitivity.SENSITIVE: 0.6,
    Sensitivity.RESTRICTED: 0.8,
    Sensitivity.CLASSIFIED: 1.0,
}


@dataclass
class OrchestrationDecision:
    """The output of the orchestration controller."""
    allowed: bool
    decision: RiskDecision
    risk_result: ActionRiskResult
    token: CapabilityToken | None = None
    hitl_request_id: str | None = None
    reason: str = ""


class OrchestrationController:
    """
    Central decision point for all agent action requests.
    Combines per-action risk scoring, trust evaluation, and HITL routing.
    """

    def __init__(
        self,
        session: AsyncSession,
        workspace_id: int | None = None,
        max_session_risk_budget: float = 3.0,
    ):
        self.session = session
        self.workspace_id = workspace_id
        self.risk_scorer = ActionRiskScorer()
        self.trust_manager = TrustManager(session)
        self.token_service = CapabilityTokenService(session)
        self.lineage_service = LineageService(session, workspace_id)
        self._session_risk_total: float = 0.0
        self._session_action_count: int = 0
        self._max_session_risk = max_session_risk_budget

    async def evaluate_action(
        self,
        agent_id: str,
        action: str,
        resource_scope: dict | None = None,
        record_count: int = 1,
        dollar_exposure: float = 0.0,
        parent_node_ids: list[str] | None = None,
    ) -> OrchestrationDecision:
        """
        Evaluate whether an agent action should be permitted.

        This is the main entry point — called before every agent action.
        """
        # 1. Get agent trust score
        trust_score = await self.trust_manager.get_trust_score(agent_id)
        escalation_level = await self.trust_manager.get_escalation_level(agent_id)

        # 2. Check if agent is suspended
        if escalation_level >= 3:
            risk_result = ActionRiskResult(
                action_risk_score=1.0,
                risk_tier=RiskTier.CRITICAL,
                decision=RiskDecision.DENY,
                justification=f"Agent {agent_id} is suspended (trust={trust_score:.3f}). "
                              f"Requires human re-certification.",
            )
            return OrchestrationDecision(
                allowed=False,
                decision=RiskDecision.DENY,
                risk_result=risk_result,
                reason="agent_suspended",
            )

        # 3. Determine resource sensitivity
        tool_sensitivity = TOOL_SENSITIVITY.get(action, Sensitivity.INTERNAL)
        resource_sensitivity = SENSITIVITY_TO_FLOAT.get(tool_sensitivity, 0.5)

        # 4. Determine mutation scope
        mutation_scope = "read"
        if any(kw in action for kw in ("create", "update", "change", "override")):
            mutation_scope = "write"
        elif "delete" in action:
            mutation_scope = "delete"
        elif "escalate" in action:
            mutation_scope = "escalate"

        # 5. Calculate per-action risk score
        risk_input = ActionRiskInput(
            action_type=action,
            agent_id=agent_id,
            agent_trust_score=trust_score,
            resource_sensitivity=resource_sensitivity,
            mutation_scope=mutation_scope,
            record_count=record_count,
            dollar_exposure=dollar_exposure,
            requires_phi_access=tool_sensitivity >= Sensitivity.SENSITIVE,
            business_hours=True,  # TODO: check actual business hours
        )
        risk_result = self.risk_scorer.score(risk_input)

        # 6. Check ALWAYS_HITL actions
        if action in ALWAYS_HITL_ACTIONS:
            risk_result.decision = RiskDecision.REQUIRE_HITL
            risk_result.justification += f" Action '{action}' always requires HITL approval."

        # 7. Check cumulative session risk budget
        self._session_risk_total += risk_result.action_risk_score
        self._session_action_count += 1
        if self._session_risk_total > self._max_session_risk:
            risk_result.decision = RiskDecision.REQUIRE_HITL
            risk_result.justification += (
                f" Session risk budget exceeded "
                f"({self._session_risk_total:.2f} > {self._max_session_risk})."
            )

        # 8. Apply escalation level overrides
        if escalation_level >= 2 and risk_result.decision != RiskDecision.DENY:
            risk_result.decision = RiskDecision.REQUIRE_HITL
            risk_result.justification += (
                f" Agent at escalation level {escalation_level} (HITL required)."
            )
        elif escalation_level == 1 and risk_result.decision == RiskDecision.AUTO_APPROVE:
            risk_result.decision = RiskDecision.APPROVE_WITH_LOGGING

        # 9. Route based on decision
        if risk_result.decision == RiskDecision.DENY:
            await self.trust_manager.record_event(
                agent_id, "policy_violation",
                f"Denied action '{action}': {risk_result.justification}",
            )
            return OrchestrationDecision(
                allowed=False,
                decision=RiskDecision.DENY,
                risk_result=risk_result,
                reason="risk_too_high",
            )

        if risk_result.decision == RiskDecision.REQUIRE_HITL:
            hitl_request = await self._create_hitl_request(
                agent_id, action, resource_scope or {},
                risk_result, trust_score,
            )
            # In a real system, this would pause and wait for human approval.
            # For POC, we auto-approve HITL requests to keep the pipeline flowing,
            # but the request is recorded for audit.
            hitl_request.status = "auto_approved_poc"
            hitl_request.reviewer = "system:poc_auto_approve"
            hitl_request.resolved_at = datetime.utcnow()
            await self.session.flush()

            logger.info("HITL request %s auto-approved (POC mode) for %s:%s",
                        hitl_request.request_id, agent_id, action)

        # 10. Issue capability token
        token = await self.token_service.issue(
            agent_id=agent_id,
            action=action,
            resource_scope=resource_scope,
            constraints={"read_only": mutation_scope == "read"},
            max_uses=50 if action in ("investigate", "chat") else 1,
        )

        # 11. Record in lineage graph
        await self.lineage_service.record_node(
            node_type="policy_enforcement",
            agent_id="orchestration_controller",
            action=f"Approved {action} for {agent_id} (risk={risk_result.action_risk_score:.3f})",
            payload={
                "action": action,
                "agent_id": agent_id,
                "risk_score": risk_result.action_risk_score,
                "risk_tier": risk_result.risk_tier.value,
                "decision": risk_result.decision.value,
                "trust_score": trust_score,
                "token_id": token.token_id,
            },
            trust_score=trust_score,
            capability_token_id=token.token_id,
            parent_node_ids=parent_node_ids,
        )

        return OrchestrationDecision(
            allowed=True,
            decision=risk_result.decision,
            risk_result=risk_result,
            token=token,
            hitl_request_id=(
                hitl_request.request_id
                if risk_result.decision == RiskDecision.REQUIRE_HITL
                else None
            ),
            reason="approved",
        )

    async def record_action_outcome(
        self,
        agent_id: str,
        action: str,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Record the outcome of an action for trust updates."""
        if success:
            await self.trust_manager.record_event(
                agent_id, "successful_action", f"Completed {action}",
            )
        else:
            await self.trust_manager.record_event(
                agent_id, "action_error", f"Failed {action}: {error or 'unknown'}",
            )

    async def _create_hitl_request(
        self,
        agent_id: str,
        action: str,
        resource_scope: dict,
        risk_result: ActionRiskResult,
        trust_score: float,
    ) -> HITLRequest:
        """Create a HITL approval request."""
        request = HITLRequest(
            request_id=str(uuid4()),
            agent_id=agent_id,
            requested_action=action,
            resource_scope=resource_scope,
            action_risk_score=risk_result.action_risk_score,
            risk_tier=risk_result.risk_tier.value,
            agent_trust_score=trust_score,
            justification=risk_result.justification,
            contributing_factors=[
                {
                    "factor": f.factor,
                    "weight": f.weight,
                    "raw_value": f.raw_value,
                    "weighted_value": f.weighted_value,
                }
                for f in risk_result.contributing_factors
            ],
            context={
                "session_risk_total": self._session_risk_total,
                "session_action_count": self._session_action_count,
            },
            status="pending",
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        )
        self.session.add(request)
        await self.session.flush()
        logger.info("Created HITL request %s for %s:%s (risk=%.3f)",
                     request.request_id, agent_id, action,
                     risk_result.action_risk_score)
        return request
