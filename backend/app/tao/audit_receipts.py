"""
Attested Audit Receipts — cryptographically attested, tamper-evident
receipts for every completed agent action.

Extends the existing AuditLog with:
- Input/output data hash attestation
- Capability token linkage
- Risk and trust score snapshots
- Full evidence payloads (LLM prompts/responses, data accessed/modified)
- Digital signatures (HMAC-SHA256, upgradeable to RSA/Ed25519)
- Hash chain (each receipt links to the previous)
"""

import hashlib
import hmac
import json
import logging
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tao.models import AuditReceipt

logger = logging.getLogger(__name__)

_SIGNING_KEY = b"arqai-tao-audit-receipt-signing-key-v1"


class AuditReceiptService:
    """Creates and verifies cryptographically attested audit receipts."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _hash_data(data: dict | str | None) -> str:
        if data is None:
            return hashlib.sha256(b"null").hexdigest()
        if isinstance(data, str):
            return hashlib.sha256(data.encode()).hexdigest()
        raw = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _compute_receipt_hash(fields: dict) -> str:
        raw = json.dumps(fields, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _sign(receipt_hash: str) -> str:
        return hmac.new(_SIGNING_KEY, receipt_hash.encode(), hashlib.sha256).hexdigest()

    async def _get_latest_receipt_hash(self) -> str | None:
        result = await self.session.execute(
            select(AuditReceipt.receipt_hash)
            .order_by(AuditReceipt.id.desc())
            .limit(1)
        )
        return result.scalar()

    async def create_receipt(
        self,
        action_type: str,
        agent_id: str,
        lineage_node_id: str | None = None,
        input_data: dict | None = None,
        output_data: dict | None = None,
        output_summary: dict | None = None,
        capability_token_id: str | None = None,
        token_scope_snapshot: dict | None = None,
        hitl_request_id: str | None = None,
        action_risk_score: float | None = None,
        agent_trust_score: float | None = None,
        evidence: dict | None = None,
    ) -> AuditReceipt:
        """
        Create a new attested audit receipt.

        The receipt is hash-chained to the previous receipt and digitally signed.
        """
        receipt_id = str(uuid4())
        previous_hash = await self._get_latest_receipt_hash()

        input_hash = self._hash_data(input_data)
        output_hash = self._hash_data(output_data)

        # Assemble fields for hashing (everything except receipt_hash and signature)
        fields = {
            "receipt_id": receipt_id,
            "lineage_node_id": lineage_node_id,
            "action_type": action_type,
            "agent_id": agent_id,
            "input_data_hash": input_hash,
            "output_data_hash": output_hash,
            "output_summary": output_summary or {},
            "capability_token_id": capability_token_id,
            "token_scope_snapshot": token_scope_snapshot or {},
            "hitl_request_id": hitl_request_id,
            "action_risk_score": action_risk_score,
            "agent_trust_score": agent_trust_score,
            "evidence": evidence or {},
            "previous_receipt_hash": previous_hash,
        }
        receipt_hash = self._compute_receipt_hash(fields)
        signature = self._sign(receipt_hash)

        receipt = AuditReceipt(
            receipt_id=receipt_id,
            lineage_node_id=lineage_node_id,
            action_type=action_type,
            agent_id=agent_id,
            input_data_hash=input_hash,
            output_data_hash=output_hash,
            output_summary=output_summary or {},
            capability_token_id=capability_token_id,
            token_scope_snapshot=token_scope_snapshot or {},
            hitl_request_id=hitl_request_id,
            action_risk_score=action_risk_score,
            agent_trust_score=agent_trust_score,
            evidence=evidence or {},
            previous_receipt_hash=previous_hash,
            receipt_hash=receipt_hash,
            signature=signature,
        )
        self.session.add(receipt)
        await self.session.flush()
        return receipt

    async def verify_chain_integrity(self, limit: int = 1000) -> dict:
        """Verify the receipt hash chain integrity."""
        result = await self.session.execute(
            select(AuditReceipt).order_by(AuditReceipt.id.asc()).limit(limit)
        )
        receipts = list(result.scalars())
        if not receipts:
            return {"valid": True, "receipts_checked": 0}

        for i, receipt in enumerate(receipts):
            # Verify chain linkage
            expected_prev = receipts[i - 1].receipt_hash if i > 0 else None
            if receipt.previous_receipt_hash != expected_prev:
                return {
                    "valid": False,
                    "receipts_checked": i + 1,
                    "first_invalid": receipt.receipt_id,
                    "reason": "previous_receipt_hash mismatch",
                }

            # Re-compute receipt hash
            fields = {
                "receipt_id": receipt.receipt_id,
                "lineage_node_id": receipt.lineage_node_id,
                "action_type": receipt.action_type,
                "agent_id": receipt.agent_id,
                "input_data_hash": receipt.input_data_hash,
                "output_data_hash": receipt.output_data_hash,
                "output_summary": receipt.output_summary,
                "capability_token_id": receipt.capability_token_id,
                "token_scope_snapshot": receipt.token_scope_snapshot,
                "hitl_request_id": receipt.hitl_request_id,
                "action_risk_score": receipt.action_risk_score,
                "agent_trust_score": receipt.agent_trust_score,
                "evidence": receipt.evidence,
                "previous_receipt_hash": receipt.previous_receipt_hash,
            }
            expected_hash = self._compute_receipt_hash(fields)
            if receipt.receipt_hash != expected_hash:
                return {
                    "valid": False,
                    "receipts_checked": i + 1,
                    "first_invalid": receipt.receipt_id,
                    "reason": "receipt_hash mismatch (data tampered)",
                }

            # Verify signature
            expected_sig = self._sign(receipt.receipt_hash)
            if not hmac.compare_digest(receipt.signature, expected_sig):
                return {
                    "valid": False,
                    "receipts_checked": i + 1,
                    "first_invalid": receipt.receipt_id,
                    "reason": "signature_invalid",
                }

        return {"valid": True, "receipts_checked": len(receipts)}

    async def get_receipts_for_agent(
        self, agent_id: str, limit: int = 50,
    ) -> list[AuditReceipt]:
        """Get recent receipts for an agent."""
        result = await self.session.execute(
            select(AuditReceipt)
            .where(AuditReceipt.agent_id == agent_id)
            .order_by(AuditReceipt.id.desc())
            .limit(limit)
        )
        return list(result.scalars())
