"""
Governance API — exposes TAO, CAPC, and ODA-RAG methodology data.

Provides endpoints for:
  - TAO: Agent trust profiles, HITL queue, lineage traces, audit receipts
  - CAPC: Evidence packets, IR validation stats
  - ODA-RAG: Signal metrics, drift detection, adaptation events
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.auth.permissions import Permission
from app.auth.context import RequestContext

# TAO models
from app.tao.models import (
    LineageNode, LineageEdge, CapabilityToken,
    AgentTrustProfile, HITLRequest, AuditReceipt,
)
# CAPC models
from app.capc.models import ComplianceIRRecord, EvidencePacket
# ODA-RAG models
from app.oda_rag.models import RAGSignal, AdaptationEvent, RAGFeedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/governance", tags=["governance"])


# ── Overview / Health ────────────────────────────────────────────────────────

@router.get("/health")
async def governance_health(
    ctx: RequestContext = Depends(require(Permission.DASHBOARD_VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """Get overall methodology health summary."""
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)

    # TAO stats
    lineage_count = (await db.execute(
        select(func.count()).select_from(LineageNode)
    )).scalar() or 0
    lineage_24h = (await db.execute(
        select(func.count()).select_from(LineageNode)
        .where(LineageNode.created_at >= last_24h)
    )).scalar() or 0

    trust_profiles = (await db.execute(
        select(func.count()).select_from(AgentTrustProfile)
    )).scalar() or 0
    avg_trust = (await db.execute(
        select(func.avg(AgentTrustProfile.trust_score))
    )).scalar()

    tokens_issued = (await db.execute(
        select(func.count()).select_from(CapabilityToken)
    )).scalar() or 0
    tokens_24h = (await db.execute(
        select(func.count()).select_from(CapabilityToken)
        .where(CapabilityToken.issued_at >= last_24h)
    )).scalar() or 0

    hitl_pending = (await db.execute(
        select(func.count()).select_from(HITLRequest)
        .where(HITLRequest.status == "pending")
    )).scalar() or 0
    hitl_total = (await db.execute(
        select(func.count()).select_from(HITLRequest)
    )).scalar() or 0

    receipts_total = (await db.execute(
        select(func.count()).select_from(AuditReceipt)
    )).scalar() or 0

    # CAPC stats
    evidence_total = (await db.execute(
        select(func.count()).select_from(EvidencePacket)
    )).scalar() or 0
    evidence_24h = (await db.execute(
        select(func.count()).select_from(EvidencePacket)
        .where(EvidencePacket.created_at >= last_24h)
    )).scalar() or 0
    violations = (await db.execute(
        select(func.count()).select_from(EvidencePacket)
        .where(EvidencePacket.exception_action.isnot(None))
    )).scalar() or 0

    # ODA-RAG stats
    signals_total = (await db.execute(
        select(func.count()).select_from(RAGSignal)
    )).scalar() or 0
    signals_24h = (await db.execute(
        select(func.count()).select_from(RAGSignal)
        .where(RAGSignal.created_at >= last_24h)
    )).scalar() or 0
    adaptations_total = (await db.execute(
        select(func.count()).select_from(AdaptationEvent)
    )).scalar() or 0
    avg_feedback = (await db.execute(
        select(func.avg(RAGFeedback.response_quality))
    )).scalar()

    return {
        "tao": {
            "lineage_nodes": lineage_count,
            "lineage_24h": lineage_24h,
            "trust_profiles": trust_profiles,
            "avg_trust_score": round(float(avg_trust), 3) if avg_trust is not None else None,
            "tokens_issued": tokens_issued,
            "tokens_24h": tokens_24h,
            "hitl_pending": hitl_pending,
            "hitl_total": hitl_total,
            "audit_receipts": receipts_total,
        },
        "capc": {
            "evidence_packets": evidence_total,
            "evidence_24h": evidence_24h,
            "policy_violations": violations,
        },
        "oda_rag": {
            "signals_total": signals_total,
            "signals_24h": signals_24h,
            "adaptations": adaptations_total,
            "avg_feedback_quality": round(float(avg_feedback), 3) if avg_feedback is not None else None,
        },
    }


# ── TAO Endpoints ────────────────────────────────────────────────────────────

@router.get("/tao/trust-profiles")
async def list_trust_profiles(
    ctx: RequestContext = Depends(require(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """List all agent trust profiles."""
    result = await db.execute(
        select(AgentTrustProfile).order_by(AgentTrustProfile.trust_score.asc())
    )
    profiles = []
    for p in result.scalars():
        profiles.append({
            "agent_id": p.agent_id,
            "trust_score": round(p.trust_score, 4),
            "escalation_level": p.escalation_level,
            "escalation_reason": p.escalation_reason,
            "decay_model": p.decay_model,
            "last_successful_action": p.last_successful_action.isoformat() if p.last_successful_action else None,
            "last_trust_update": p.last_trust_update.isoformat() if p.last_trust_update else None,
            "history_count": len(p.trust_history) if p.trust_history else 0,
        })
    return {"profiles": profiles}


@router.get("/tao/trust-profiles/{agent_id}")
async def get_trust_profile(
    agent_id: str,
    ctx: RequestContext = Depends(require(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed trust profile for an agent including history."""
    result = await db.execute(
        select(AgentTrustProfile).where(AgentTrustProfile.agent_id == agent_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        return {"error": f"Agent {agent_id} not found"}
    return {
        "agent_id": p.agent_id,
        "trust_score": round(p.trust_score, 4),
        "initial_trust": p.initial_trust,
        "escalation_level": p.escalation_level,
        "escalation_reason": p.escalation_reason,
        "decay_model": p.decay_model,
        "decay_rate": p.decay_rate,
        "last_successful_action": p.last_successful_action.isoformat() if p.last_successful_action else None,
        "trust_history": p.trust_history or [],
    }


@router.get("/tao/hitl-requests")
async def list_hitl_requests(
    ctx: RequestContext = Depends(require(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List HITL approval requests."""
    q = select(HITLRequest).order_by(HITLRequest.created_at.desc()).limit(limit)
    if status:
        q = q.where(HITLRequest.status == status)
    result = await db.execute(q)
    return {
        "requests": [
            {
                "request_id": r.request_id,
                "agent_id": r.agent_id,
                "requested_action": r.requested_action,
                "action_risk_score": round(r.action_risk_score, 3),
                "risk_tier": r.risk_tier,
                "agent_trust_score": round(r.agent_trust_score, 3),
                "justification": r.justification,
                "status": r.status,
                "reviewer": r.reviewer,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            }
            for r in result.scalars()
        ]
    }


@router.get("/tao/lineage")
async def list_lineage_nodes(
    ctx: RequestContext = Depends(require(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
    node_type: str | None = Query(None),
    agent_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """List recent lineage nodes."""
    q = select(LineageNode).order_by(LineageNode.created_at.desc()).limit(limit)
    if node_type:
        q = q.where(LineageNode.node_type == node_type)
    if agent_id:
        q = q.where(LineageNode.agent_id == agent_id)
    result = await db.execute(q)
    return {
        "nodes": [
            {
                "node_id": n.node_id,
                "node_type": n.node_type,
                "agent_id": n.agent_id,
                "action": n.action,
                "trust_score": round(n.trust_score_at_action, 3) if n.trust_score_at_action is not None else None,
                "duration_ms": n.duration_ms,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in result.scalars()
        ]
    }


@router.get("/tao/audit-receipts")
async def list_audit_receipts(
    ctx: RequestContext = Depends(require(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """List recent audit receipts."""
    result = await db.execute(
        select(AuditReceipt).order_by(AuditReceipt.id.desc()).limit(limit)
    )
    return {
        "receipts": [
            {
                "receipt_id": r.receipt_id,
                "action_type": r.action_type,
                "agent_id": r.agent_id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "action_risk_score": round(r.action_risk_score, 3) if r.action_risk_score is not None else None,
                "lineage_node_id": r.lineage_node_id,
                "capability_token_id": r.capability_token_id,
                "output_summary": r.output_summary,
            }
            for r in result.scalars()
        ]
    }


# ── CAPC Endpoints ───────────────────────────────────────────────────────────

@router.get("/capc/evidence-packets")
async def list_evidence_packets(
    ctx: RequestContext = Depends(require(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """List recent evidence packets."""
    result = await db.execute(
        select(EvidencePacket).order_by(EvidencePacket.id.desc()).limit(limit)
    )
    return {
        "packets": [
            {
                "packet_id": p.packet_id,
                "ir_id": p.ir_id,
                "original_request": p.original_request[:200],
                "policy_decisions_count": len(p.policy_decisions) if p.policy_decisions else 0,
                "exception_action": p.exception_action,
                "packet_hash": p.packet_hash[:16] + "...",
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in result.scalars()
        ]
    }


@router.get("/capc/evidence-packets/{packet_id}")
async def get_evidence_packet(
    packet_id: str,
    ctx: RequestContext = Depends(require(Permission.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """Get full evidence packet details."""
    result = await db.execute(
        select(EvidencePacket).where(EvidencePacket.packet_id == packet_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        return {"error": f"Packet {packet_id} not found"}
    return {
        "packet_id": p.packet_id,
        "ir_id": p.ir_id,
        "original_request": p.original_request,
        "compiled_ir": p.compiled_ir,
        "policy_decisions": p.policy_decisions,
        "preconditions": p.preconditions,
        "approvals": p.approvals,
        "lineage_hashes": p.lineage_hashes,
        "model_tool_versions": p.model_tool_versions,
        "results": p.results,
        "exception_action": p.exception_action,
        "packet_hash": p.packet_hash,
        "signature": p.signature[:32] + "...",
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


# ── ODA-RAG Endpoints ───────────────────────────────────────────────────────

@router.get("/oda-rag/signals")
async def list_signals(
    ctx: RequestContext = Depends(require(Permission.DASHBOARD_VIEW)),
    db: AsyncSession = Depends(get_db),
    signal_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """List recent RAG signals."""
    q = select(RAGSignal).order_by(RAGSignal.created_at.desc()).limit(limit)
    if signal_type:
        q = q.where(RAGSignal.signal_type == signal_type)
    result = await db.execute(q)
    return {
        "signals": [
            {
                "signal_id": s.signal_id,
                "signal_type": s.signal_type,
                "metric_name": s.metric_name,
                "metric_value": round(s.metric_value, 4),
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in result.scalars()
        ]
    }


@router.get("/oda-rag/signal-summary")
async def signal_summary(
    ctx: RequestContext = Depends(require(Permission.DASHBOARD_VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated signal summary by type."""
    result = await db.execute(
        select(
            RAGSignal.signal_type,
            func.count().label("count"),
            func.avg(RAGSignal.metric_value).label("avg_value"),
            func.min(RAGSignal.metric_value).label("min_value"),
            func.max(RAGSignal.metric_value).label("max_value"),
        )
        .group_by(RAGSignal.signal_type)
    )
    return {
        "summary": [
            {
                "signal_type": row.signal_type,
                "count": row.count,
                "avg_value": round(float(row.avg_value), 4) if row.avg_value is not None else None,
                "min_value": round(float(row.min_value), 4) if row.min_value is not None else None,
                "max_value": round(float(row.max_value), 4) if row.max_value is not None else None,
            }
            for row in result
        ]
    }


@router.get("/oda-rag/adaptations")
async def list_adaptations(
    ctx: RequestContext = Depends(require(Permission.DASHBOARD_VIEW)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """List recent adaptation events."""
    result = await db.execute(
        select(AdaptationEvent).order_by(AdaptationEvent.created_at.desc()).limit(limit)
    )
    return {
        "adaptations": [
            {
                "event_id": e.event_id,
                "action_type": e.action_type,
                "drift_score": round(e.drift_score, 3) if e.drift_score is not None else None,
                "reason": e.reason,
                "parameters_before": e.parameters_before,
                "parameters_after": e.parameters_after,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in result.scalars()
        ]
    }


@router.get("/oda-rag/feedback")
async def list_feedback(
    ctx: RequestContext = Depends(require(Permission.DASHBOARD_VIEW)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """List recent RAG feedback entries."""
    result = await db.execute(
        select(RAGFeedback).order_by(RAGFeedback.created_at.desc()).limit(limit)
    )
    return {
        "feedback": [
            {
                "feedback_id": f.feedback_id,
                "query": f.query[:200],
                "response_quality": round(f.response_quality, 3),
                "relevance_score": round(f.relevance_score, 3) if f.relevance_score is not None else None,
                "feedback_source": f.feedback_source,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in result.scalars()
        ]
    }


# ── Sync / Refresh ─────────────────────────────────────────────────────────

@router.post("/sync")
async def sync_governance(
    ctx: RequestContext = Depends(require(Permission.DASHBOARD_VIEW)),
    db: AsyncSession = Depends(get_db),
):
    """Re-generate governance data from current pipeline results.

    Truncates existing governance tables and rebuilds from actual
    risk_scores, rule_results, investigation_cases, and pipeline_runs.
    """
    from app.seed.governance_data import (
        GOVERNANCE_TABLES, load_pipeline_data, build_trust_profiles,
        build_capability_tokens, build_lineage_nodes, build_lineage_edges,
        build_hitl_requests, build_audit_receipts, build_compliance_ir_records,
        build_evidence_packets, build_rag_signals, build_adaptation_events,
        build_rag_feedback, insert_batch, SEED,
    )
    import random

    rng = random.Random(SEED)

    # Check pipeline data exists
    from app.models import RiskScore
    score_count = (await db.execute(
        select(func.count()).select_from(RiskScore)
    )).scalar() or 0
    if score_count == 0:
        return {"status": "skipped", "reason": "No pipeline data. Run the pipeline first."}

    # Truncate governance tables
    for t in GOVERNANCE_TABLES:
        await db.execute(text(f"TRUNCATE TABLE {t} CASCADE"))
    await db.flush()

    # Rebuild from pipeline data
    data = await load_pipeline_data(db)

    profiles = build_trust_profiles(rng, data)
    await insert_batch(db, AgentTrustProfile, profiles, "trust profiles")

    tokens = build_capability_tokens(rng, data)
    await insert_batch(db, CapabilityToken, tokens, "capability tokens")

    nodes = build_lineage_nodes(rng, data, tokens)
    await insert_batch(db, LineageNode, nodes, "lineage nodes")
    edges = build_lineage_edges(nodes)
    await insert_batch(db, LineageEdge, edges, "lineage edges")

    hitls = build_hitl_requests(rng, data)
    await insert_batch(db, HITLRequest, hitls, "HITL requests")

    receipts = build_audit_receipts(rng, data, nodes, tokens, hitls)
    await insert_batch(db, AuditReceipt, receipts, "audit receipts")

    ir_records = build_compliance_ir_records(rng, data)
    await insert_batch(db, ComplianceIRRecord, ir_records, "compliance IR records")
    packets = build_evidence_packets(rng, data, ir_records)
    await insert_batch(db, EvidencePacket, packets, "evidence packets")

    signals = build_rag_signals(rng, data)
    await insert_batch(db, RAGSignal, signals, "RAG signals")
    adaptations = build_adaptation_events(rng, data, signals)
    await insert_batch(db, AdaptationEvent, adaptations, "adaptation events")
    fb = build_rag_feedback(rng, data)
    await insert_batch(db, RAGFeedback, fb, "RAG feedback")

    return {
        "status": "synced",
        "from_scores": score_count,
        "tao": {
            "trust_profiles": len(profiles),
            "tokens": len(tokens),
            "lineage_nodes": len(nodes),
            "lineage_edges": len(edges),
            "hitl_requests": len(hitls),
            "audit_receipts": len(receipts),
        },
        "capc": {
            "ir_records": len(ir_records),
            "evidence_packets": len(packets),
        },
        "oda_rag": {
            "signals": len(signals),
            "adaptations": len(adaptations),
            "feedback": len(fb),
        },
    }
