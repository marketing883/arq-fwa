"""
Governance seed — generates TAO, CAPC, and ODA-RAG records derived from
actual pipeline data (risk_scores, rule_results, investigation_cases,
pipeline_runs, claims).

Run after the pipeline so governance tables reflect real pipeline activity.

Usage:
    python -m app.seed.governance_data
    python -m app.seed.governance_data --clean
"""

import asyncio
import hashlib
import random
import sys
import time
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings
from app.models import (
    RiskScore, RuleResult, InvestigationCase, PipelineRun,
    MedicalClaim, PharmacyClaim, Rule, AuditLog,
)
from app.tao.models import (
    LineageNode, LineageEdge, CapabilityToken,
    AgentTrustProfile, HITLRequest, AuditReceipt,
)
from app.capc.models import ComplianceIRRecord, EvidencePacket
from app.oda_rag.models import RAGSignal, AdaptationEvent, RAGFeedback

SEED = 42

# Pipeline agents — these match the actual pipeline steps
PIPELINE_AGENTS = {
    "claims-ingestion":    {"step": 1, "desc": "Loads and normalizes raw claims"},
    "data-quality":        {"step": 2, "desc": "Validates claim data quality"},
    "enrichment-engine":   {"step": 3, "desc": "Enriches claims with reference data"},
    "rule-engine":         {"step": 4, "desc": "Evaluates FWA detection rules"},
    "risk-scorer":         {"step": 5, "desc": "Calculates composite risk scores"},
    "case-builder":        {"step": 6, "desc": "Creates investigation cases"},
    "audit-logger":        {"step": 7, "desc": "Records audit trail entries"},
    "llm-summarizer":      {"step": 8, "desc": "Generates AI case summaries"},
    "compliance-auditor":  {"step": 9, "desc": "Audits pipeline for compliance"},
    "rag-retriever":       {"step": 10, "desc": "Retrieves regulatory context"},
}


def _uid() -> str:
    return str(uuid.uuid4())


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _sig(*parts: str) -> str:
    return hashlib.sha256(("sig:" + "|".join(parts)).encode()).hexdigest() + hashlib.md5(
        "|".join(parts).encode()
    ).hexdigest()


# ── Data loaders ─────────────────────────────────────────────────────────────

async def load_pipeline_data(session: AsyncSession) -> dict:
    """Query actual pipeline results to base governance records on."""
    # Risk scores
    scores_q = await session.execute(
        select(RiskScore).order_by(RiskScore.scored_at.desc()).limit(2000)
    )
    scores = list(scores_q.scalars())

    # Investigation cases
    cases_q = await session.execute(
        select(InvestigationCase).order_by(InvestigationCase.created_at.desc()).limit(500)
    )
    cases = list(cases_q.scalars())

    # Triggered rule results (only those that fired)
    rules_q = await session.execute(
        select(RuleResult).where(RuleResult.triggered.is_(True))
        .order_by(RuleResult.evaluated_at.desc()).limit(5000)
    )
    triggered_rules = list(rules_q.scalars())

    # Rules catalog
    rule_catalog_q = await session.execute(select(Rule))
    rule_catalog = {r.rule_id: r for r in rule_catalog_q.scalars()}

    # Pipeline runs (table may not exist yet)
    runs = []
    table_check = await session.execute(text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'pipeline_runs')"
    ))
    if table_check.scalar():
        runs_q = await session.execute(
            select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(10)
        )
        runs = list(runs_q.scalars())

    # Audit logs
    audits_q = await session.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)
    )
    audit_logs = list(audits_q.scalars())

    # Sample claims for reference
    med_q = await session.execute(select(MedicalClaim).limit(500))
    med_claims = list(med_q.scalars())
    rx_q = await session.execute(select(PharmacyClaim).limit(500))
    rx_claims = list(rx_q.scalars())

    print(f"  Loaded: {len(scores)} scores, {len(cases)} cases, "
          f"{len(triggered_rules)} rule hits, {len(runs)} pipeline runs")

    return {
        "scores": scores,
        "cases": cases,
        "triggered_rules": triggered_rules,
        "rule_catalog": rule_catalog,
        "runs": runs,
        "audit_logs": audit_logs,
        "med_claims": med_claims,
        "rx_claims": rx_claims,
    }


# ── TAO generators (from real data) ─────────────────────────────────────────

def build_trust_profiles(rng: random.Random, data: dict) -> list[dict]:
    """Create trust profiles for each pipeline agent based on actual results."""
    now = datetime.utcnow()
    profiles = []

    # Derive trust from actual pipeline performance
    total_scores = len(data["scores"])
    total_cases = len(data["cases"])
    total_rules_fired = len(data["triggered_rules"])

    for agent_id, info in PIPELINE_AGENTS.items():
        # Base trust on how the pipeline performed
        initial = 0.75
        current = initial

        # Build history from actual pipeline runs
        history = []
        for run in data["runs"]:
            ts = run.started_at or now
            stats = run.stats or {}
            event = "action_success" if run.status == "completed" else "action_failure"
            delta = 0.02 if event == "action_success" else -0.08
            current = max(0.1, min(1.0, round(current + delta, 4)))
            history.append({
                "timestamp": ts.isoformat(),
                "score": current,
                "event": event,
                "batch_id": run.batch_id,
                "claims_processed": stats.get("total_claims", 0),
            })

        # Agents that handle high-risk cases get more variance
        if agent_id == "case-builder" and total_cases > 0:
            current = round(max(0.5, current - 0.05 * (total_cases / max(total_scores, 1))), 4)
        elif agent_id == "rule-engine" and total_rules_fired > 0:
            # More rules fired = engine is working well
            current = round(min(0.95, current + 0.03), 4)

        esc_level = 0
        esc_reason = None
        if current < 0.5:
            esc_level = 2
            esc_reason = f"Trust degraded after {len([r for r in data['runs'] if r.status == 'failed'])} failed pipeline runs"
        elif current < 0.6:
            esc_level = 1
            esc_reason = "Trust below warning threshold"

        last_run = data["runs"][0] if data["runs"] else None
        profiles.append({
            "agent_id": agent_id,
            "trust_score": current,
            "initial_trust": initial,
            "decay_model": "exponential",
            "decay_rate": 0.01,
            "escalation_level": esc_level,
            "escalation_reason": esc_reason,
            "last_successful_action": last_run.completed_at if last_run and last_run.status == "completed" else None,
            "last_trust_update": now,
            "trust_history": history,
            "created_at": data["runs"][-1].started_at if data["runs"] else now - timedelta(days=7),
        })
    return profiles


def build_capability_tokens(rng: random.Random, data: dict) -> list[dict]:
    """Create tokens reflecting actual pipeline operations."""
    tokens = []
    now = datetime.utcnow()

    # One token per pipeline run × agent
    for run in data["runs"]:
        batch = run.batch_id or "unknown"
        started = run.started_at or now
        stats = run.stats or {}

        agent_actions = [
            ("claims-ingestion", "read_claims", {"batch_id": batch, "claim_types": ["medical", "pharmacy"]}),
            ("data-quality", "validate_claims", {"batch_id": batch}),
            ("enrichment-engine", "enrich_claims", {"batch_id": batch, "sources": ["cpt", "icd", "ndc"]}),
            ("rule-engine", "evaluate_rules", {"batch_id": batch, "rule_count": len(data["rule_catalog"])}),
            ("risk-scorer", "score_claims", {"batch_id": batch, "claims": stats.get("total_claims", 0)}),
            ("case-builder", "create_cases", {"batch_id": batch, "high_risk": stats.get("high_risk", 0)}),
            ("audit-logger", "write_audit", {"batch_id": batch}),
        ]

        for agent_id, action, scope in agent_actions:
            tid = _uid()
            ttl = 4
            tokens.append({
                "token_id": tid,
                "issuer": "tao-authority",
                "subject_agent_id": agent_id,
                "action": action,
                "resource_scope": scope,
                "constraints": {"ttl_hours": ttl, "batch_id": batch},
                "issued_at": started,
                "expires_at": started + timedelta(hours=ttl),
                "max_uses": 1,
                "uses_remaining": 0 if run.status == "completed" else 1,
                "parent_token_id": None,
                "revoked": run.status == "failed",
                "signature": _sig(tid, agent_id, action, batch),
            })
    return tokens


def build_lineage_nodes(rng: random.Random, data: dict, tokens: list[dict]) -> list[dict]:
    """Create lineage nodes from actual pipeline activity."""
    nodes = []
    now = datetime.utcnow()
    token_by_agent = {}
    for t in tokens:
        token_by_agent.setdefault(t["subject_agent_id"], []).append(t["token_id"])

    for run in data["runs"]:
        started = run.started_at or now
        batch = run.batch_id or "unknown"
        stats = run.stats or {}

        # Node for claim ingestion
        nid = _uid()
        nodes.append({
            "node_id": nid,
            "node_type": "claim_ingest",
            "agent_id": "claims-ingestion",
            "action": f"Ingested {stats.get('medical_claims', 0)} medical + {stats.get('pharmacy_claims', 0)} pharmacy claims",
            "payload": {"batch_id": batch, "medical": stats.get("medical_claims", 0), "pharmacy": stats.get("pharmacy_claims", 0)},
            "trust_score_at_action": 0.78,
            "capability_token_id": (token_by_agent.get("claims-ingestion") or [None])[0],
            "duration_ms": int((run.duration_seconds or 5) * 100),
            "workspace_id": run.workspace_id,
            "created_at": started,
            "_step": 1,
        })

        # Node for rule evaluation
        nid2 = _uid()
        nodes.append({
            "node_id": nid2,
            "node_type": "rule_eval",
            "agent_id": "rule-engine",
            "action": f"Evaluated {stats.get('rules_evaluated', 0)} rule-claim combinations",
            "payload": {"batch_id": batch, "rules_evaluated": stats.get("rules_evaluated", 0)},
            "trust_score_at_action": 0.82,
            "capability_token_id": (token_by_agent.get("rule-engine") or [None])[0],
            "duration_ms": int((run.duration_seconds or 10) * 300),
            "workspace_id": run.workspace_id,
            "created_at": started + timedelta(seconds=2),
            "_step": 2,
        })

        # Node for scoring
        nid3 = _uid()
        nodes.append({
            "node_id": nid3,
            "node_type": "score_calc",
            "agent_id": "risk-scorer",
            "action": f"Generated {stats.get('scores_generated', 0)} risk scores",
            "payload": {"batch_id": batch, "scores": stats.get("scores_generated", 0), "high_risk": stats.get("high_risk", 0), "critical": stats.get("critical_risk", 0)},
            "trust_score_at_action": 0.80,
            "capability_token_id": (token_by_agent.get("risk-scorer") or [None])[0],
            "duration_ms": int((run.duration_seconds or 8) * 200),
            "workspace_id": run.workspace_id,
            "created_at": started + timedelta(seconds=5),
            "_step": 3,
        })

        # Node for case creation
        nid4 = _uid()
        cases_created = stats.get("cases_created", 0)
        nodes.append({
            "node_id": nid4,
            "node_type": "case_create",
            "agent_id": "case-builder",
            "action": f"Created {cases_created} investigation cases from high/critical scores",
            "payload": {"batch_id": batch, "cases_created": cases_created},
            "trust_score_at_action": 0.76,
            "capability_token_id": (token_by_agent.get("case-builder") or [None])[0],
            "duration_ms": int((run.duration_seconds or 3) * 50),
            "workspace_id": run.workspace_id,
            "created_at": started + timedelta(seconds=8),
            "_step": 4,
        })

    # Individual nodes for high-risk scored claims
    high_risk_scores = [s for s in data["scores"] if s.risk_level in ("high", "critical")]
    for score in high_risk_scores[:100]:
        nodes.append({
            "node_id": _uid(),
            "node_type": "score_calc",
            "agent_id": "risk-scorer",
            "action": f"Scored claim {score.claim_id} → {score.risk_level} ({float(score.total_score):.1f})",
            "payload": {
                "claim_id": score.claim_id,
                "claim_type": score.claim_type,
                "total_score": float(score.total_score),
                "risk_level": score.risk_level,
                "rules_triggered": score.rules_triggered,
            },
            "trust_score_at_action": 0.80,
            "capability_token_id": None,
            "duration_ms": rng.randint(20, 200),
            "workspace_id": score.workspace_id,
            "created_at": score.scored_at or now,
            "_step": 3,
        })

    # Nodes for triggered rules on high-risk claims
    high_risk_claim_ids = {s.claim_id for s in high_risk_scores[:50]}
    for rr in data["triggered_rules"]:
        if rr.claim_id in high_risk_claim_ids:
            rule_info = data["rule_catalog"].get(rr.rule_id)
            desc = rule_info.description if rule_info else rr.rule_id
            nodes.append({
                "node_id": _uid(),
                "node_type": "rule_eval",
                "agent_id": "rule-engine",
                "action": f"Rule {rr.rule_id} triggered on {rr.claim_id}: {desc[:80]}",
                "payload": {
                    "claim_id": rr.claim_id,
                    "rule_id": rr.rule_id,
                    "severity": float(rr.severity) if rr.severity else None,
                    "confidence": float(rr.confidence) if rr.confidence else None,
                    "evidence": rr.evidence,
                },
                "trust_score_at_action": 0.82,
                "capability_token_id": None,
                "duration_ms": rng.randint(5, 100),
                "workspace_id": rr.workspace_id,
                "created_at": rr.evaluated_at or now,
                "_step": 2,
            })

    # Nodes for investigation cases
    for case in data["cases"]:
        nodes.append({
            "node_id": _uid(),
            "node_type": "case_create",
            "agent_id": "case-builder",
            "action": f"Created case {case.case_id} for claim {case.claim_id} (priority {case.priority})",
            "payload": {
                "case_id": case.case_id,
                "claim_id": case.claim_id,
                "risk_score": float(case.risk_score),
                "risk_level": case.risk_level,
                "priority": case.priority,
            },
            "trust_score_at_action": 0.76,
            "capability_token_id": None,
            "duration_ms": rng.randint(30, 300),
            "workspace_id": case.workspace_id,
            "created_at": case.created_at or now,
            "_step": 4,
        })

    return nodes


def build_lineage_edges(nodes: list[dict]) -> list[dict]:
    """Create edges between lineage nodes that share the same batch/claim."""
    edges = []
    # Connect sequential pipeline steps within same batch
    by_payload_batch = {}
    for n in nodes:
        batch = (n.get("payload") or {}).get("batch_id")
        if batch:
            by_payload_batch.setdefault(batch, []).append(n)

    for batch, batch_nodes in by_payload_batch.items():
        sorted_nodes = sorted(batch_nodes, key=lambda n: n.get("_step", 99))
        for i in range(len(sorted_nodes) - 1):
            edges.append({
                "source_node_id": sorted_nodes[i]["node_id"],
                "target_node_id": sorted_nodes[i + 1]["node_id"],
                "relationship": "produced",
                "data_hash": _hash(sorted_nodes[i]["node_id"], sorted_nodes[i + 1]["node_id"]),
            })

    # Connect rule evals → score calcs for same claim
    by_claim = {}
    for n in nodes:
        cid = (n.get("payload") or {}).get("claim_id")
        if cid:
            by_claim.setdefault(cid, []).append(n)

    for cid, claim_nodes in by_claim.items():
        rule_nodes = [n for n in claim_nodes if n["node_type"] == "rule_eval"]
        score_nodes = [n for n in claim_nodes if n["node_type"] == "score_calc"]
        case_nodes = [n for n in claim_nodes if n["node_type"] == "case_create"]

        for rn in rule_nodes:
            for sn in score_nodes:
                edges.append({
                    "source_node_id": rn["node_id"],
                    "target_node_id": sn["node_id"],
                    "relationship": "consumed",
                    "data_hash": _hash(rn["node_id"], sn["node_id"]),
                })
        for sn in score_nodes:
            for cn in case_nodes:
                edges.append({
                    "source_node_id": sn["node_id"],
                    "target_node_id": cn["node_id"],
                    "relationship": "triggered",
                    "data_hash": _hash(sn["node_id"], cn["node_id"]),
                })

    return edges


def build_hitl_requests(rng: random.Random, data: dict) -> list[dict]:
    """Create HITL requests for high-value investigation cases."""
    requests = []
    now = datetime.utcnow()
    reviewers = ["dr.chen", "inv.martinez", "mgr.thompson", "auditor.williams"]

    # Critical cases need human approval
    critical_cases = [c for c in data["cases"] if c.risk_level == "critical" or c.priority == "P1"]
    high_cases = [c for c in data["cases"] if c.risk_level == "high" and c.priority == "P2"]

    for case in critical_cases:
        rid = _uid()
        created = case.created_at or now
        status = rng.choice(["pending", "approved", "approved"])
        resolved = None
        reviewer = None
        notes = None
        if status != "pending":
            resolved = created + timedelta(minutes=rng.randint(15, 240))
            reviewer = rng.choice(reviewers)
            notes = f"Reviewed case {case.case_id}. Risk score {float(case.risk_score):.1f} — action approved."

        requests.append({
            "request_id": rid,
            "agent_id": "case-builder",
            "requested_action": "escalate_investigation",
            "resource_scope": {"case_id": case.case_id, "claim_id": case.claim_id},
            "action_risk_score": min(1.0, float(case.risk_score) / 100),
            "risk_tier": "critical",
            "agent_trust_score": 0.76,
            "justification": f"Case {case.case_id}: claim {case.claim_id} scored {float(case.risk_score):.1f} ({case.risk_level}). Requires human review for escalation.",
            "contributing_factors": [
                {"factor": "risk_score", "value": float(case.risk_score)},
                {"factor": "priority", "value": case.priority},
            ],
            "context": {"case_id": case.case_id, "claim_type": case.claim_type},
            "status": status,
            "reviewer": reviewer,
            "reviewer_notes": notes,
            "created_at": created,
            "resolved_at": resolved,
            "expires_at": created + timedelta(hours=48),
        })

    # Sample of high-risk cases too
    for case in high_cases[:10]:
        rid = _uid()
        created = case.created_at or now
        status = rng.choice(["pending", "approved"])
        resolved = None
        reviewer = None
        notes = None
        if status == "approved":
            resolved = created + timedelta(minutes=rng.randint(30, 480))
            reviewer = rng.choice(reviewers)
            notes = f"High-risk case {case.case_id} approved for investigation."

        requests.append({
            "request_id": rid,
            "agent_id": "case-builder",
            "requested_action": "approve_case_creation",
            "resource_scope": {"case_id": case.case_id, "claim_id": case.claim_id},
            "action_risk_score": min(1.0, float(case.risk_score) / 100),
            "risk_tier": "high",
            "agent_trust_score": 0.76,
            "justification": f"Case {case.case_id}: high-risk claim {case.claim_id} with score {float(case.risk_score):.1f}.",
            "contributing_factors": [
                {"factor": "risk_score", "value": float(case.risk_score)},
                {"factor": "rules_triggered", "value": len([r for r in data["triggered_rules"] if r.claim_id == case.claim_id])},
            ],
            "context": {"case_id": case.case_id},
            "status": status,
            "reviewer": reviewer,
            "reviewer_notes": notes,
            "created_at": created,
            "resolved_at": resolved,
            "expires_at": created + timedelta(hours=48),
        })

    return requests


def build_audit_receipts(
    rng: random.Random, data: dict, nodes: list[dict], tokens: list[dict], hitls: list[dict],
) -> list[dict]:
    """Create audit receipts from actual pipeline events."""
    receipts = []
    now = datetime.utcnow()
    prev_hash = None

    node_ids = [n["node_id"] for n in nodes]
    token_ids = [t["token_id"] for t in tokens]
    hitl_ids = [h["request_id"] for h in hitls]

    # Receipt for each pipeline run
    for run in data["runs"]:
        rid = _uid()
        ts = run.completed_at or run.started_at or now
        stats = run.stats or {}
        in_hash = _hash("pipeline_run", run.run_id or "")
        out_hash = _hash("pipeline_result", str(stats.get("total_claims", 0)))
        r_hash = _hash(rid, in_hash, out_hash, str(prev_hash))
        receipts.append({
            "receipt_id": rid,
            "lineage_node_id": node_ids[0] if node_ids else None,
            "action_type": "pipeline_run_completed",
            "agent_id": "claims-ingestion",
            "timestamp": ts,
            "input_data_hash": in_hash,
            "output_data_hash": out_hash,
            "output_summary": {
                "batch_id": run.batch_id,
                "total_claims": stats.get("total_claims", 0),
                "cases_created": stats.get("cases_created", 0),
                "status": run.status,
            },
            "capability_token_id": token_ids[0] if token_ids else None,
            "token_scope_snapshot": {"action": "full_pipeline_run"},
            "hitl_request_id": None,
            "action_risk_score": 0.3,
            "agent_trust_score": 0.78,
            "evidence": {"run_id": run.run_id, "duration_s": run.duration_seconds},
            "previous_receipt_hash": prev_hash,
            "receipt_hash": r_hash,
            "signature": _sig(rid, r_hash),
        })
        prev_hash = r_hash

    # Receipt for each investigation case created
    for case in data["cases"]:
        rid = _uid()
        ts = case.created_at or now
        in_hash = _hash("case_input", case.claim_id)
        out_hash = _hash("case_output", case.case_id)
        r_hash = _hash(rid, in_hash, out_hash, str(prev_hash))
        receipts.append({
            "receipt_id": rid,
            "lineage_node_id": rng.choice(node_ids) if node_ids else None,
            "action_type": "case_created",
            "agent_id": "case-builder",
            "timestamp": ts,
            "input_data_hash": in_hash,
            "output_data_hash": out_hash,
            "output_summary": {
                "case_id": case.case_id,
                "claim_id": case.claim_id,
                "risk_score": float(case.risk_score),
                "risk_level": case.risk_level,
                "priority": case.priority,
            },
            "capability_token_id": rng.choice(token_ids) if token_ids else None,
            "token_scope_snapshot": {"action": "create_case"},
            "hitl_request_id": rng.choice(hitl_ids) if hitl_ids and rng.random() < 0.3 else None,
            "action_risk_score": min(1.0, float(case.risk_score) / 100),
            "agent_trust_score": 0.76,
            "evidence": {"claim_type": case.claim_type, "sla_deadline": case.sla_deadline.isoformat() if case.sla_deadline else None},
            "previous_receipt_hash": prev_hash,
            "receipt_hash": r_hash,
            "signature": _sig(rid, r_hash),
        })
        prev_hash = r_hash

    # Receipts for high-risk scores
    high_scores = [s for s in data["scores"] if s.risk_level in ("high", "critical")]
    for score in high_scores[:80]:
        rid = _uid()
        ts = score.scored_at or now
        in_hash = _hash("score_input", score.claim_id)
        out_hash = _hash("score_output", str(float(score.total_score)))
        r_hash = _hash(rid, in_hash, out_hash, str(prev_hash))
        receipts.append({
            "receipt_id": rid,
            "lineage_node_id": rng.choice(node_ids) if node_ids else None,
            "action_type": "claim_scored",
            "agent_id": "risk-scorer",
            "timestamp": ts,
            "input_data_hash": in_hash,
            "output_data_hash": out_hash,
            "output_summary": {
                "claim_id": score.claim_id,
                "total_score": float(score.total_score),
                "risk_level": score.risk_level,
                "rules_triggered": score.rules_triggered,
            },
            "capability_token_id": rng.choice(token_ids) if token_ids else None,
            "token_scope_snapshot": {"action": "score_claims"},
            "hitl_request_id": None,
            "action_risk_score": min(1.0, float(score.total_score) / 100),
            "agent_trust_score": 0.80,
            "evidence": {"claim_type": score.claim_type, "batch_id": score.batch_id},
            "previous_receipt_hash": prev_hash,
            "receipt_hash": r_hash,
            "signature": _sig(rid, r_hash),
        })
        prev_hash = r_hash

    return receipts


# ── CAPC generators (from real data) ─────────────────────────────────────────

def build_compliance_ir_records(rng: random.Random, data: dict) -> list[dict]:
    """Create compliance IR records from actual rule evaluations."""
    records = []
    now = datetime.utcnow()

    # One IR per rule in the catalog — represents the compiled compliance check
    for rule_id, rule in data["rule_catalog"].items():
        irid = _uid()
        hits = [r for r in data["triggered_rules"] if r.rule_id == rule_id]
        opcodes = [
            {"index": 0, "opcode": "FETCH_CLAIMS", "params": {"claim_type": rule.claim_type}},
            {"index": 1, "opcode": "APPLY_RULE", "params": {"rule_id": rule_id, "category": rule.category}},
            {"index": 2, "opcode": "COMPUTE_STATS", "params": {"metric": "trigger_rate"}},
            {"index": 3, "opcode": "CHECK_THRESHOLD", "params": {"thresholds": rule.thresholds}},
            {"index": 4, "opcode": "EMIT_RESULT", "params": {"total_hits": len(hits)}},
        ]
        records.append({
            "ir_id": irid,
            "original_request": f"Evaluate {rule.category} rule {rule_id}: {rule.description}",
            "parsed_intents": [{"intent": "fwa_detection", "rule_id": rule_id, "confidence": 0.95}],
            "parsed_entities": [
                {"type": "rule", "value": rule_id},
                {"type": "category", "value": rule.category},
                {"type": "fraud_type", "value": rule.fraud_type},
                {"type": "claim_type", "value": rule.claim_type},
            ],
            "sensitivity_level": "confidential",
            "opcodes": opcodes,
            "edges": [{"from": j, "to": j + 1} for j in range(4)],
            "validation_status": "passed",
            "validation_errors": [],
            "runtime_checks_attached": ["rate_limit", "data_access_audit", "phi_redaction"],
            "agent_id": "rule-engine",
            "workspace_id": 1,
            "created_at": now - timedelta(hours=rng.randint(0, 48)),
            "_rule_id": rule_id,
            "_hits": len(hits),
        })
    return records


def build_evidence_packets(rng: random.Random, data: dict, ir_records: list[dict]) -> list[dict]:
    """Create evidence packets from actual case investigations."""
    packets = []
    now = datetime.utcnow()
    prev_hash = None

    ir_by_rule = {ir.get("_rule_id"): ir for ir in ir_records}

    # One packet per investigation case — this is the compliance evidence bundle
    for case in data["cases"]:
        pid = _uid()
        # Find which rules triggered on this case's claim
        case_rules = [r for r in data["triggered_rules"] if r.claim_id == case.claim_id]
        ir = None
        if case_rules:
            ir = ir_by_rule.get(case_rules[0].rule_id)

        policy_decisions = []
        for cr in case_rules[:5]:
            rule_info = data["rule_catalog"].get(cr.rule_id)
            policy_decisions.append({
                "rule_id": cr.rule_id,
                "category": rule_info.category if rule_info else "unknown",
                "decision": "flag",
                "severity": float(cr.severity) if cr.severity else 0,
                "confidence": float(cr.confidence) if cr.confidence else 0,
            })

        is_exception = case.risk_level == "critical" or float(case.risk_score) > 90
        exc_action = "escalate" if is_exception else None

        p_hash = _hash(pid, case.case_id)
        packets.append({
            "packet_id": pid,
            "ir_id": ir["ir_id"] if ir else None,
            "original_request": f"Compliance audit for case {case.case_id} (claim {case.claim_id})",
            "compiled_ir": {"opcodes": ir["opcodes"][:3]} if ir else {},
            "policy_decisions": policy_decisions,
            "preconditions": [
                {"check": "agent_trust_above_threshold", "result": True},
                {"check": "capability_token_valid", "result": True},
                {"check": "claim_data_complete", "result": True},
            ],
            "approvals": [{"approver": "tao-authority", "timestamp": (case.created_at or now).isoformat()}],
            "lineage_hashes": [_hash(case.claim_id, cr.rule_id) for cr in case_rules[:5]],
            "model_tool_versions": {"scoring_engine": "2.1.0", "rule_engine": "3.4.2"},
            "results": {
                "compliant": not is_exception,
                "risk_score": float(case.risk_score),
                "rules_triggered": len(case_rules),
                "priority": case.priority,
            },
            "exception_action": exc_action,
            "previous_packet_hash": prev_hash,
            "packet_hash": p_hash,
            "signature": _sig(pid, p_hash),
            "created_at": case.created_at or now,
        })
        prev_hash = p_hash

    return packets


# ── ODA-RAG generators (from real pipeline metrics) ──────────────────────────

def build_rag_signals(rng: random.Random, data: dict) -> list[dict]:
    """Create RAG signals based on actual pipeline performance metrics."""
    signals = []
    now = datetime.utcnow()

    for run in data["runs"]:
        started = run.started_at or now
        stats = run.stats or {}
        dur = run.duration_seconds or 10

        # Latency signals from actual pipeline timing
        signals.append({
            "signal_id": _uid(), "signal_type": "latency",
            "metric_name": "pipeline_e2e_latency_ms",
            "metric_value": round(dur * 1000, 2),
            "context": {"batch_id": run.batch_id, "run_id": run.run_id},
            "workspace_id": run.workspace_id, "created_at": started,
        })
        signals.append({
            "signal_id": _uid(), "signal_type": "throughput",
            "metric_name": "claims_per_second",
            "metric_value": round(stats.get("total_claims", 0) / max(dur, 0.1), 2),
            "context": {"batch_id": run.batch_id},
            "workspace_id": run.workspace_id, "created_at": started,
        })
        # Quality signals from actual scores
        signals.append({
            "signal_id": _uid(), "signal_type": "quality",
            "metric_name": "high_risk_rate",
            "metric_value": round(stats.get("high_risk", 0) / max(stats.get("total_claims", 1), 1), 4),
            "context": {"batch_id": run.batch_id},
            "workspace_id": run.workspace_id, "created_at": started,
        })
        signals.append({
            "signal_id": _uid(), "signal_type": "quality",
            "metric_name": "case_creation_rate",
            "metric_value": round(stats.get("cases_created", 0) / max(stats.get("total_claims", 1), 1), 4),
            "context": {"batch_id": run.batch_id},
            "workspace_id": run.workspace_id, "created_at": started,
        })

    # Rule effectiveness signals
    for rule_id, rule in data["rule_catalog"].items():
        hits = len([r for r in data["triggered_rules"] if r.rule_id == rule_id])
        total_scores = len(data["scores"])
        signals.append({
            "signal_id": _uid(), "signal_type": "quality",
            "metric_name": f"rule_trigger_rate",
            "metric_value": round(hits / max(total_scores, 1), 4),
            "context": {"rule_id": rule_id, "category": rule.category, "hits": hits},
            "workspace_id": 1, "created_at": now - timedelta(minutes=rng.randint(0, 120)),
        })

    # Score distribution signals
    for level in ["low", "medium", "high", "critical"]:
        count = len([s for s in data["scores"] if s.risk_level == level])
        signals.append({
            "signal_id": _uid(), "signal_type": "quality",
            "metric_name": f"score_distribution_{level}",
            "metric_value": round(count / max(len(data["scores"]), 1), 4),
            "context": {"risk_level": level, "count": count},
            "workspace_id": 1, "created_at": now,
        })

    # Drift signals — compare rule trigger rates across batches
    batch_ids = list({s.batch_id for s in data["scores"] if s.batch_id})
    if len(batch_ids) >= 2:
        for rule_id in list(data["rule_catalog"].keys())[:10]:
            signals.append({
                "signal_id": _uid(), "signal_type": "drift",
                "metric_name": "rule_trigger_drift",
                "metric_value": round(rng.uniform(0.01, 0.15), 4),
                "context": {"rule_id": rule_id, "batches_compared": batch_ids[:2]},
                "workspace_id": 1, "created_at": now,
            })

    # Error rate signals
    failed_runs = [r for r in data["runs"] if r.status == "failed"]
    signals.append({
        "signal_id": _uid(), "signal_type": "error_rate",
        "metric_name": "pipeline_failure_rate",
        "metric_value": round(len(failed_runs) / max(len(data["runs"]), 1), 4),
        "context": {"total_runs": len(data["runs"]), "failed": len(failed_runs)},
        "workspace_id": 1, "created_at": now,
    })

    return signals


def build_adaptation_events(rng: random.Random, data: dict, signals: list[dict]) -> list[dict]:
    """Create adaptation events when metrics indicate drift or issues."""
    events = []
    now = datetime.utcnow()

    drift_signals = [s for s in signals if s["signal_type"] == "drift"]
    quality_signals = [s for s in signals if s["signal_type"] == "quality"]

    # Adaptation for each significant drift detected
    for sig in drift_signals:
        if sig["metric_value"] > 0.08:
            events.append({
                "event_id": _uid(),
                "trigger_signal_ids": [sig["signal_id"]],
                "drift_score": sig["metric_value"],
                "action_type": "recalibrate_rule_threshold",
                "parameters_before": {"threshold": 0.5, "weight": 1.0},
                "parameters_after": {"threshold": round(0.5 + sig["metric_value"], 3), "weight": 1.0},
                "reason": f"Rule trigger drift of {sig['metric_value']:.3f} detected — recalibrating threshold",
                "workspace_id": 1,
                "created_at": now - timedelta(minutes=rng.randint(0, 60)),
            })

    # Adaptation for high error rates
    error_signals = [s for s in signals if s["signal_type"] == "error_rate" and s["metric_value"] > 0]
    for sig in error_signals:
        events.append({
            "event_id": _uid(),
            "trigger_signal_ids": [sig["signal_id"]],
            "drift_score": sig["metric_value"],
            "action_type": "increase_retry_limit",
            "parameters_before": {"max_retries": 3},
            "parameters_after": {"max_retries": 5},
            "reason": f"Pipeline failure rate {sig['metric_value']:.3f} — increasing retry limit",
            "workspace_id": 1,
            "created_at": now,
        })

    # Adaptation if case creation rate is unusually high
    case_rate_sigs = [s for s in quality_signals if s["metric_name"] == "case_creation_rate"]
    for sig in case_rate_sigs:
        if sig["metric_value"] > 0.05:
            events.append({
                "event_id": _uid(),
                "trigger_signal_ids": [sig["signal_id"]],
                "drift_score": round(sig["metric_value"] * 2, 3),
                "action_type": "adjust_scoring_threshold",
                "parameters_before": {"high_risk_threshold": 61},
                "parameters_after": {"high_risk_threshold": 65},
                "reason": f"Case creation rate {sig['metric_value']:.3f} above normal — tightening threshold",
                "workspace_id": 1,
                "created_at": now,
            })

    return events


def build_rag_feedback(rng: random.Random, data: dict) -> list[dict]:
    """Create RAG feedback based on actual case/rule data."""
    feedback = []
    now = datetime.utcnow()

    queries_from_rules = []
    for rule_id, rule in data["rule_catalog"].items():
        queries_from_rules.append(f"What are the compliance guidelines for {rule.category} detection?")
        queries_from_rules.append(f"Explain the regulatory basis for rule {rule_id}: {rule.description[:60]}")

    queries_from_cases = []
    for case in data["cases"][:20]:
        queries_from_cases.append(f"What investigation steps are recommended for {case.risk_level}-risk {case.claim_type} cases?")

    all_queries = queries_from_rules + queries_from_cases
    for query in all_queries:
        quality = round(rng.uniform(0.5, 0.95), 3)
        feedback.append({
            "feedback_id": _uid(),
            "session_id": _uid()[:8],
            "query": query,
            "response_quality": quality,
            "relevance_score": round(min(1.0, quality + rng.uniform(-0.1, 0.1)), 3),
            "feedback_source": rng.choice(["explicit", "implicit", "implicit"]),
            "context": {"source_docs": rng.randint(3, 12)},
            "workspace_id": 1,
            "created_at": now - timedelta(minutes=rng.randint(0, 10080)),
        })

    return feedback


# ── Insert helper ────────────────────────────────────────────────────────────

async def insert_batch(session: AsyncSession, model_cls, records: list[dict], label: str):
    print(f"  Seeding {label}...", end=" ", flush=True)
    batch = []
    for rec in records:
        # Strip internal keys
        clean = {k: v for k, v in rec.items() if not k.startswith("_")}
        batch.append(model_cls(**clean))
        if len(batch) >= 200:
            session.add_all(batch)
            await session.flush()
            batch = []
    if batch:
        session.add_all(batch)
        await session.flush()
    print(f"{len(records)} rows")


# ── Main ─────────────────────────────────────────────────────────────────────

GOVERNANCE_TABLES = [
    "audit_receipt", "hitl_request", "lineage_edge", "lineage_node",
    "capability_token", "agent_trust_profile",
    "evidence_packet", "compliance_ir_record",
    "rag_feedback", "adaptation_event", "rag_signal",
]


async def seed_governance():
    start = time.time()
    engine = create_async_engine(settings.database_url, echo=False)
    async_sess = async_sessionmaker(engine, expire_on_commit=False)
    rng = random.Random(SEED)
    clean = "--clean" in sys.argv

    async with async_sess() as session:
        # Check prerequisites
        score_count = (await session.execute(
            select(func.count()).select_from(RiskScore)
        )).scalar() or 0
        if score_count == 0:
            print("No pipeline data found. Run the pipeline first, then seed governance.")
            await engine.dispose()
            return

        # Check if already seeded
        existing = (await session.execute(
            select(func.count()).select_from(AgentTrustProfile)
        )).scalar() or 0
        if existing > 0 and not clean:
            print(f"Governance already seeded ({existing} trust profiles). Use --clean to re-seed.")
            await engine.dispose()
            return

        if clean:
            print("Cleaning governance tables...")
            for t in GOVERNANCE_TABLES:
                await session.execute(text(f"TRUNCATE TABLE {t} CASCADE"))
            await session.commit()

        print("=" * 60)
        print("ArqAI FWA — Governance Seed (from pipeline data)")
        print("=" * 60)

        print("\n[0/7] Loading pipeline data...")
        data = await load_pipeline_data(session)

        print("\n[1/7] Agent Trust Profiles")
        profiles = build_trust_profiles(rng, data)
        await insert_batch(session, AgentTrustProfile, profiles, "trust profiles")

        print("\n[2/7] Capability Tokens")
        tokens = build_capability_tokens(rng, data)
        await insert_batch(session, CapabilityToken, tokens, "capability tokens")

        print("\n[3/7] Lineage Graph")
        nodes = build_lineage_nodes(rng, data, tokens)
        await insert_batch(session, LineageNode, nodes, "lineage nodes")
        edges = build_lineage_edges(nodes)
        await insert_batch(session, LineageEdge, edges, "lineage edges")

        print("\n[4/7] HITL Requests")
        hitls = build_hitl_requests(rng, data)
        await insert_batch(session, HITLRequest, hitls, "HITL requests")

        print("\n[5/7] Audit Receipts")
        receipts = build_audit_receipts(rng, data, nodes, tokens, hitls)
        await insert_batch(session, AuditReceipt, receipts, "audit receipts")

        print("\n[6/7] Compliance IR + Evidence Packets")
        ir_records = build_compliance_ir_records(rng, data)
        await insert_batch(session, ComplianceIRRecord, ir_records, "compliance IR records")
        packets = build_evidence_packets(rng, data, ir_records)
        await insert_batch(session, EvidencePacket, packets, "evidence packets")

        print("\n[7/7] RAG Signals, Adaptations & Feedback")
        signals = build_rag_signals(rng, data)
        await insert_batch(session, RAGSignal, signals, "RAG signals")
        adaptations = build_adaptation_events(rng, data, signals)
        await insert_batch(session, AdaptationEvent, adaptations, "adaptation events")
        fb = build_rag_feedback(rng, data)
        await insert_batch(session, RAGFeedback, fb, "RAG feedback")

        await session.commit()

    await engine.dispose()
    elapsed = time.time() - start
    print(f"\nGovernance seed completed in {elapsed:.1f}s")
    print(f"  TAO:     {len(profiles)} profiles, {len(tokens)} tokens, "
          f"{len(nodes)} nodes, {len(edges)} edges, {len(hitls)} HITL, {len(receipts)} receipts")
    print(f"  CAPC:    {len(ir_records)} IR records, {len(packets)} evidence packets")
    print(f"  ODA-RAG: {len(signals)} signals, {len(adaptations)} adaptations, {len(fb)} feedback")


if __name__ == "__main__":
    asyncio.run(seed_governance())
