"""
Evidence Packet Generator — creates signed, hash-chained evidence bundles
for compliance audit (CMS, OIG, HIPAA).

Each evidence packet contains:
    - Original NL request
    - Compiled IR (full DAG)
    - Policy decisions (pass/fail per opcode)
    - Preconditions and approvals
    - Lineage hashes
    - Model/tool versions
    - Results
    - Hash chain link to previous packet
    - Cryptographic signature
"""

import hashlib
import hmac
import json
import logging
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capc.models import EvidencePacket
from app.capc.opcodes import ComplianceIR
from app.capc.validator import ValidationResult

logger = logging.getLogger(__name__)

_SIGNING_KEY = b"arqai-capc-evidence-packet-signing-key-v1"


class EvidencePacketGenerator:
    """Creates and verifies signed evidence packets."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _compute_hash(fields: dict) -> str:
        raw = json.dumps(fields, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def _sign(packet_hash: str) -> str:
        return hmac.new(_SIGNING_KEY, packet_hash.encode(), hashlib.sha256).hexdigest()

    async def _get_previous_hash(self) -> str | None:
        result = await self.session.execute(
            select(EvidencePacket.packet_hash)
            .order_by(EvidencePacket.id.desc())
            .limit(1)
        )
        return result.scalar()

    async def generate(
        self,
        ir: ComplianceIR,
        validation_result: ValidationResult,
        execution_results: dict | None = None,
        approvals: list[dict] | None = None,
        lineage_node_ids: list[str] | None = None,
        model_versions: dict | None = None,
        exception_action: str | None = None,
    ) -> EvidencePacket:
        """
        Generate a signed evidence packet after IR execution.

        Args:
            ir: The compiled ComplianceIR
            validation_result: Result of static validation
            execution_results: Output from execution
            approvals: Any HITL approvals obtained
            lineage_node_ids: Lineage node IDs created during execution
            model_versions: Versions of models/tools used
            exception_action: If an exception occurred (abort/rollback/review)
        """
        packet_id = str(uuid4())
        previous_hash = await self._get_previous_hash()

        # Build policy decisions
        policy_decisions = []
        for op_result in validation_result.opcode_results:
            policy_decisions.append({
                "opcode_id": op_result.opcode_id,
                "passed": op_result.passed,
                "errors": op_result.errors,
                "warnings": op_result.warnings,
                "runtime_checks": op_result.runtime_checks_added,
            })

        # Build preconditions
        preconditions = []
        for opcode in ir.opcodes:
            if opcode.runtime_checks:
                preconditions.append({
                    "opcode_id": opcode.opcode_id,
                    "checks": opcode.runtime_checks,
                    "met": opcode.status != "blocked",
                })

        # Lineage hashes
        lineage_hashes = []
        if lineage_node_ids:
            for node_id in lineage_node_ids:
                lineage_hashes.append({
                    "node_id": node_id,
                    "hash": hashlib.sha256(node_id.encode()).hexdigest(),
                })

        # Assemble fields for hashing
        fields = {
            "packet_id": packet_id,
            "ir_id": ir.ir_id,
            "original_request": ir.original_request,
            "compiled_ir": ir.to_dict(),
            "policy_decisions": policy_decisions,
            "preconditions": preconditions,
            "approvals": approvals or [],
            "lineage_hashes": lineage_hashes,
            "model_tool_versions": model_versions or {"slm": "ollama:local"},
            "results": execution_results or {},
            "exception_action": exception_action,
            "previous_packet_hash": previous_hash,
        }
        packet_hash = self._compute_hash(fields)
        signature = self._sign(packet_hash)

        packet = EvidencePacket(
            packet_id=packet_id,
            ir_id=ir.ir_id,
            original_request=ir.original_request,
            compiled_ir=ir.to_dict(),
            policy_decisions=policy_decisions,
            preconditions=preconditions,
            approvals=approvals or [],
            lineage_hashes=lineage_hashes,
            model_tool_versions=model_versions or {"slm": "ollama:local"},
            results=execution_results or {},
            exception_action=exception_action,
            previous_packet_hash=previous_hash,
            packet_hash=packet_hash,
            signature=signature,
        )
        self.session.add(packet)
        await self.session.flush()

        logger.info("Generated evidence packet %s for IR %s (exception=%s)",
                     packet_id, ir.ir_id, exception_action)
        return packet

    async def verify_chain_integrity(self, limit: int = 1000) -> dict:
        """Verify the evidence packet hash chain."""
        result = await self.session.execute(
            select(EvidencePacket).order_by(EvidencePacket.id.asc()).limit(limit)
        )
        packets = list(result.scalars())
        if not packets:
            return {"valid": True, "packets_checked": 0}

        for i, pkt in enumerate(packets):
            expected_prev = packets[i - 1].packet_hash if i > 0 else None
            if pkt.previous_packet_hash != expected_prev:
                return {
                    "valid": False,
                    "packets_checked": i + 1,
                    "first_invalid": pkt.packet_id,
                    "reason": "previous_packet_hash mismatch",
                }

            # Verify signature
            expected_sig = self._sign(pkt.packet_hash)
            if not hmac.compare_digest(pkt.signature, expected_sig):
                return {
                    "valid": False,
                    "packets_checked": i + 1,
                    "first_invalid": pkt.packet_id,
                    "reason": "signature_invalid",
                }

        return {"valid": True, "packets_checked": len(packets)}
