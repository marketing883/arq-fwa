"""
CAPC — Compliance-Aware Prompt Compiler & Evidence Generator (ArqGuard).

Patent-pending methodology for transforming natural-language agent requests
into compliance-annotated intermediate representations, validating them
against a policy graph, and generating signed evidence packets.

Pipeline:
    1. Receive NL request
    2. Parse & extract (intents, entities, sensitivity, jurisdiction)
    3. Compile to Compliance IR (DAG of opcodes)
    4. Static validation against Policy Graph
    5. Runtime checks during execution
    6. Generate signed evidence packet
    7. Exception routing (abort / rollback / manual review)

Components:
    models          — SQLAlchemy models (IR records, evidence packets)
    opcodes         — Opcode definitions and IR DAG data structures
    compiler        — NL → Compliance IR compiler
    validator       — Static IR validator
    evidence        — Signed evidence packet generator
    exception_router — Exception routing logic
    policy_graph    — Policy graph (extends auth layer)
"""

from app.capc.opcodes import Opcode, OpcodeType, ComplianceIR
from app.capc.compiler import ComplianceIRCompiler
from app.capc.validator import IRValidator, ValidationResult
from app.capc.evidence import EvidencePacketGenerator
from app.capc.exception_router import ExceptionRouter, ExceptionAction
from app.capc.policy_graph import PolicyGraph

__all__ = [
    "Opcode", "OpcodeType", "ComplianceIR",
    "ComplianceIRCompiler", "IRValidator", "ValidationResult",
    "EvidencePacketGenerator", "ExceptionRouter", "ExceptionAction",
    "PolicyGraph",
]
