"""
Lineage Graph Engine — tracks the complete causal chain of every decision
and data transformation in the system.

Implements forward trace, backward trace, impact analysis, and agent
accountability queries as specified in the TAO whitepaper.
"""

import hashlib
import json
import logging
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tao.models import LineageNode, LineageEdge

logger = logging.getLogger(__name__)


class LineageService:
    """DAG-based lineage engine for data provenance and decision tracking."""

    def __init__(self, session: AsyncSession, workspace_id: int | None = None):
        self.session = session
        self.workspace_id = workspace_id

    @staticmethod
    def _hash_payload(payload: dict) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def record_node(
        self,
        node_type: str,
        agent_id: str,
        action: str,
        payload: dict | None = None,
        trust_score: float | None = None,
        capability_token_id: str | None = None,
        duration_ms: int | None = None,
        parent_node_ids: list[str] | None = None,
    ) -> LineageNode:
        """
        Record a processing event as a node in the lineage graph.

        Args:
            node_type: One of data_ingestion, enrichment, rule_evaluation,
                       score_calculation, case_creation, agent_action,
                       human_decision, policy_enforcement
            agent_id: Who performed this action
            action: Human-readable description
            payload: Full input/output snapshot
            trust_score: Agent's trust score at time of action
            capability_token_id: Token that authorized this action
            duration_ms: Execution time
            parent_node_ids: Upstream dependency node IDs
        """
        node_id = str(uuid4())
        node = LineageNode(
            node_id=node_id,
            node_type=node_type,
            agent_id=agent_id,
            action=action,
            payload=payload or {},
            trust_score_at_action=trust_score,
            capability_token_id=capability_token_id,
            duration_ms=duration_ms,
            workspace_id=self.workspace_id,
        )
        self.session.add(node)
        await self.session.flush()

        # Create edges from parent nodes
        if parent_node_ids:
            for parent_id in parent_node_ids:
                data_hash = self._hash_payload(payload or {})
                edge = LineageEdge(
                    source_node_id=parent_id,
                    target_node_id=node_id,
                    relationship="produced",
                    data_hash=data_hash,
                )
                self.session.add(edge)
            await self.session.flush()

        return node

    async def add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        relationship: str,
        data: dict | None = None,
    ) -> LineageEdge:
        """Add a causal edge between two existing nodes."""
        edge = LineageEdge(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relationship=relationship,
            data_hash=self._hash_payload(data) if data else None,
        )
        self.session.add(edge)
        await self.session.flush()
        return edge

    async def forward_trace(self, node_id: str, max_depth: int = 50) -> list[dict]:
        """
        Forward trace: given a node, find all downstream decisions and actions.
        Returns nodes in topological order.
        """
        visited: set[str] = set()
        result: list[dict] = []
        queue = [node_id]

        while queue and len(visited) < max_depth:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            node = (await self.session.execute(
                select(LineageNode).where(LineageNode.node_id == current)
            )).scalar_one_or_none()
            if node:
                result.append({
                    "node_id": node.node_id,
                    "node_type": node.node_type,
                    "agent_id": node.agent_id,
                    "action": node.action,
                    "trust_score": node.trust_score_at_action,
                    "created_at": node.created_at.isoformat() if node.created_at else None,
                })

            # Find outgoing edges
            edges = (await self.session.execute(
                select(LineageEdge).where(LineageEdge.source_node_id == current)
            )).scalars()
            for edge in edges:
                if edge.target_node_id not in visited:
                    queue.append(edge.target_node_id)

        return result

    async def backward_trace(self, node_id: str, max_depth: int = 50) -> list[dict]:
        """
        Backward trace: given a node, trace back to all upstream inputs
        and contributing decisions.
        """
        visited: set[str] = set()
        result: list[dict] = []
        queue = [node_id]

        while queue and len(visited) < max_depth:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)

            node = (await self.session.execute(
                select(LineageNode).where(LineageNode.node_id == current)
            )).scalar_one_or_none()
            if node:
                result.append({
                    "node_id": node.node_id,
                    "node_type": node.node_type,
                    "agent_id": node.agent_id,
                    "action": node.action,
                    "trust_score": node.trust_score_at_action,
                    "created_at": node.created_at.isoformat() if node.created_at else None,
                })

            # Find incoming edges
            edges = (await self.session.execute(
                select(LineageEdge).where(LineageEdge.target_node_id == current)
            )).scalars()
            for edge in edges:
                if edge.source_node_id not in visited:
                    queue.append(edge.source_node_id)

        return result

    async def agent_accountability(
        self, agent_id: str, limit: int = 100,
    ) -> list[dict]:
        """Retrieve all nodes attributed to an agent, most recent first."""
        result = await self.session.execute(
            select(LineageNode)
            .where(LineageNode.agent_id == agent_id)
            .order_by(LineageNode.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "node_id": n.node_id,
                "node_type": n.node_type,
                "action": n.action,
                "trust_score": n.trust_score_at_action,
                "duration_ms": n.duration_ms,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in result.scalars()
        ]

    async def impact_analysis(self, node_id: str) -> dict:
        """
        Given a node (e.g., a rule configuration change), identify all
        downstream scores and cases that would be affected.
        """
        downstream = await self.forward_trace(node_id)
        affected_scores = [n for n in downstream if n["node_type"] == "score_calculation"]
        affected_cases = [n for n in downstream if n["node_type"] == "case_creation"]
        return {
            "source_node": node_id,
            "total_downstream": len(downstream),
            "affected_scores": len(affected_scores),
            "affected_cases": len(affected_cases),
            "nodes": downstream,
        }
