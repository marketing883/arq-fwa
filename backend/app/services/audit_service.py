"""
Audit Service — ArqMesh (Phase 7)

Immutable, hash-chained audit trail for all system actions.
Every state change in the system creates an audit log entry.
"""

import hashlib
import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


class AuditService:
    """Immutable, hash-chained audit trail."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _calculate_hash(self, content: dict, previous_hash: str | None) -> str:
        """SHA-256 hash of entry contents + previous hash."""
        payload = {
            "content": content,
            "previous_hash": previous_hash or "",
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _get_latest_hash(self) -> str | None:
        """Get the hash of the most recent audit entry."""
        result = await self.session.execute(
            select(AuditLog.current_hash)
            .order_by(AuditLog.id.desc())
            .limit(1)
        )
        row = result.scalar()
        return row

    async def log_event(
        self,
        event_type: str,
        actor: str,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict | None = None,
    ) -> AuditLog:
        """
        Write an immutable audit entry.

        Args:
            event_type: e.g. "claim_ingested", "rule_evaluated", "case_created"
            actor: e.g. "system", "admin@example.com", "agent:investigator"
            action: Human-readable description
            resource_type: "claim", "rule", "case", etc.
            resource_id: The ID of the affected resource
            details: Full event details as dict
        """
        previous_hash = await self._get_latest_hash()

        entry_details = details or {}
        content_for_hash = {
            "event_type": event_type,
            "actor": actor,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": entry_details,
        }
        current_hash = self._calculate_hash(content_for_hash, previous_hash)

        entry = AuditLog(
            event_id=str(uuid4()),
            event_type=event_type,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=entry_details,
            previous_hash=previous_hash,
            current_hash=current_hash,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def log_claim_ingested(self, batch_id: str, count: int, source: str) -> AuditLog:
        return await self.log_event(
            event_type="claim_ingested",
            actor="system",
            action=f"Ingested {count} claims from {source}",
            resource_type="batch",
            resource_id=batch_id,
            details={"batch_id": batch_id, "count": count, "source": source},
        )

    async def log_rule_evaluated(self, claim_id: str, rule_id: str, triggered: bool, severity: float | None) -> AuditLog:
        return await self.log_event(
            event_type="rule_evaluated",
            actor="system",
            action=f"Rule {rule_id} {'triggered' if triggered else 'passed'} on {claim_id}",
            resource_type="claim",
            resource_id=claim_id,
            details={"rule_id": rule_id, "triggered": triggered, "severity": severity},
        )

    async def log_score_calculated(self, claim_id: str, score: float, risk_level: str) -> AuditLog:
        return await self.log_event(
            event_type="score_calculated",
            actor="system",
            action=f"Risk score {score:.1f} ({risk_level}) for {claim_id}",
            resource_type="claim",
            resource_id=claim_id,
            details={"score": score, "risk_level": risk_level},
        )

    async def log_case_created(self, case_id: str, claim_id: str, risk_level: str) -> AuditLog:
        return await self.log_event(
            event_type="case_created",
            actor="system",
            action=f"Investigation case {case_id} created for {claim_id} ({risk_level})",
            resource_type="case",
            resource_id=case_id,
            details={"claim_id": claim_id, "risk_level": risk_level},
        )

    async def log_case_updated(self, case_id: str, old_status: str, new_status: str, actor: str) -> AuditLog:
        return await self.log_event(
            event_type="case_updated",
            actor=actor,
            action=f"Case {case_id} status: {old_status} → {new_status}",
            resource_type="case",
            resource_id=case_id,
            details={"old_status": old_status, "new_status": new_status},
        )

    async def log_rule_config_changed(self, rule_id: str, changes: dict, admin: str) -> AuditLog:
        return await self.log_event(
            event_type="rule_config_changed",
            actor=admin,
            action=f"Rule {rule_id} configuration updated",
            resource_type="rule",
            resource_id=rule_id,
            details=changes,
        )

    async def verify_chain_integrity(self) -> dict:
        """Walk the full chain and verify each entry's hash."""
        result = await self.session.execute(
            select(AuditLog).order_by(AuditLog.id.asc())
        )
        entries = list(result.scalars())

        if not entries:
            return {"valid": True, "entries_checked": 0, "first_invalid": None}

        for i, entry in enumerate(entries):
            expected_prev = entries[i - 1].current_hash if i > 0 else None
            if entry.previous_hash != expected_prev:
                return {
                    "valid": False,
                    "entries_checked": i + 1,
                    "first_invalid": entry.event_id,
                    "reason": "previous_hash mismatch",
                }

            # Re-compute hash
            content = {
                "event_type": entry.event_type,
                "actor": entry.actor,
                "action": entry.action,
                "resource_type": entry.resource_type,
                "resource_id": entry.resource_id,
                "details": entry.details,
            }
            expected_hash = self._calculate_hash(content, entry.previous_hash)
            if entry.current_hash != expected_hash:
                return {
                    "valid": False,
                    "entries_checked": i + 1,
                    "first_invalid": entry.event_id,
                    "reason": "current_hash mismatch (data tampered)",
                }

        return {"valid": True, "entries_checked": len(entries), "first_invalid": None}

    async def get_entries(
        self,
        event_type: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        """Query audit entries with optional filters."""
        query = select(AuditLog).order_by(AuditLog.created_at.desc())

        if event_type:
            query = query.where(AuditLog.event_type == event_type)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)

        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars())

    async def get_entry_count(self, event_type: str | None = None) -> int:
        """Get total count of audit entries."""
        query = select(func.count()).select_from(AuditLog)
        if event_type:
            query = query.where(AuditLog.event_type == event_type)
        result = await self.session.execute(query)
        return result.scalar() or 0
