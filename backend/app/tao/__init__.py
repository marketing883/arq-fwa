"""
TAO — Trust-Aware Agent Orchestration (ArqFlow).

Patent-pending methodology for governing autonomous AI agent actions in
regulated environments.  Every agent action passes through the Orchestration
Controller, which evaluates per-action risk, checks the agent's trust score,
issues scoped capability tokens, and routes high-risk actions to human review.

Components:
    models              — SQLAlchemy models (lineage, tokens, trust, HITL, receipts)
    lineage             — Lineage graph engine (DAG of processing events)
    capability_tokens   — Ephemeral, scoped authorization tokens
    risk_scoring        — Per-action risk scoring (weighted linear model)
    trust               — Agent trust profiles, decay, and escalation
    orchestration       — Central orchestration controller
    audit_receipts      — Cryptographically attested audit receipts
"""

from app.tao.models import (
    LineageNode, LineageEdge, CapabilityToken,
    AgentTrustProfile, HITLRequest, AuditReceipt,
)
from app.tao.lineage import LineageService
from app.tao.capability_tokens import CapabilityTokenService
from app.tao.risk_scoring import ActionRiskScorer, ActionRiskResult, RiskTier
from app.tao.trust import TrustManager
from app.tao.orchestration import OrchestrationController, OrchestrationDecision
from app.tao.audit_receipts import AuditReceiptService

__all__ = [
    "LineageNode", "LineageEdge", "CapabilityToken",
    "AgentTrustProfile", "HITLRequest", "AuditReceipt",
    "LineageService", "CapabilityTokenService",
    "ActionRiskScorer", "ActionRiskResult", "RiskTier",
    "TrustManager", "OrchestrationController", "OrchestrationDecision",
    "AuditReceiptService",
]
