"""
Opcode definitions and Compliance IR DAG data structures.

Each opcode represents a single atomic operation in the compliance-annotated
execution plan.  Opcodes carry sensitivity class, required approval level,
and model/tool constraints as metadata.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OpcodeType(str, Enum):
    """Types of operations in the compliance IR."""
    # Data retrieval
    QUERY_DATA = "query_data"
    QUERY_AGGREGATE = "query_aggregate"
    QUERY_DETAIL = "query_detail"

    # Data mutation
    CREATE_RECORD = "create_record"
    UPDATE_RECORD = "update_record"
    DELETE_RECORD = "delete_record"

    # Analysis / computation
    EVALUATE_RULE = "evaluate_rule"
    CALCULATE_SCORE = "calculate_score"
    AGGREGATE_FINANCIAL = "aggregate_financial"

    # LLM / AI operations
    LLM_INFERENCE = "llm_inference"
    LLM_INVESTIGATION = "llm_investigation"
    LLM_SUMMARIZE = "llm_summarize"

    # Output / presentation
    FORMAT_RESPONSE = "format_response"
    REDACT_FIELDS = "redact_fields"

    # Control flow
    BRANCH_ON_POLICY = "branch_on_policy"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class Opcode:
    """A single operation node in the compliance IR DAG."""
    opcode_id: str
    opcode_type: OpcodeType
    description: str

    # Compliance annotations
    sensitivity_class: str = "INTERNAL"         # PUBLIC, INTERNAL, SENSITIVE, RESTRICTED, CLASSIFIED
    required_approval: str = "auto"             # auto, enhanced_logging, hitl, deny
    jurisdiction: str = "US"                    # Geographic restriction
    model_tool_class: str | None = None         # e.g., "slm", "llm_large", "db_query"

    # Execution metadata
    resource_type: str | None = None            # claim, case, rule, provider, member
    resource_ids: list[str] = field(default_factory=list)
    fields_accessed: list[str] = field(default_factory=list)
    fields_modified: list[str] = field(default_factory=list)

    # DAG edges (dependencies)
    depends_on: list[str] = field(default_factory=list)

    # Runtime check hooks
    runtime_checks: list[str] = field(default_factory=list)

    # Execution state
    status: str = "pending"                     # pending, executing, completed, failed, blocked
    result: Any = None
    error: str | None = None


@dataclass
class ComplianceIR:
    """
    The complete Compliance Intermediate Representation — a DAG of opcodes
    compiled from a natural language request.
    """
    ir_id: str
    original_request: str
    agent_id: str
    workspace_id: int | None = None

    # Parsed NL artifacts
    intents: list[str] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    overall_sensitivity: str = "INTERNAL"

    # The DAG
    opcodes: list[Opcode] = field(default_factory=list)

    # Validation state
    validated: bool = False
    validation_errors: list[str] = field(default_factory=list)

    def get_opcode(self, opcode_id: str) -> Opcode | None:
        for op in self.opcodes:
            if op.opcode_id == opcode_id:
                return op
        return None

    def topological_order(self) -> list[Opcode]:
        """Return opcodes in dependency-respecting execution order."""
        visited: set[str] = set()
        order: list[Opcode] = []
        op_map = {op.opcode_id: op for op in self.opcodes}

        def visit(op_id: str):
            if op_id in visited:
                return
            visited.add(op_id)
            op = op_map.get(op_id)
            if op:
                for dep_id in op.depends_on:
                    visit(dep_id)
                order.append(op)

        for op in self.opcodes:
            visit(op.opcode_id)
        return order

    def max_sensitivity(self) -> str:
        """Return the highest sensitivity class across all opcodes."""
        levels = {"PUBLIC": 0, "INTERNAL": 1, "SENSITIVE": 2, "RESTRICTED": 3, "CLASSIFIED": 4}
        max_level = 0
        for op in self.opcodes:
            max_level = max(max_level, levels.get(op.sensitivity_class, 0))
        reverse = {v: k for k, v in levels.items()}
        return reverse.get(max_level, "INTERNAL")

    def to_dict(self) -> dict:
        """Serialize for persistence and evidence packets."""
        return {
            "ir_id": self.ir_id,
            "original_request": self.original_request,
            "agent_id": self.agent_id,
            "intents": self.intents,
            "entities": self.entities,
            "overall_sensitivity": self.overall_sensitivity,
            "validated": self.validated,
            "opcodes": [
                {
                    "opcode_id": op.opcode_id,
                    "opcode_type": op.opcode_type.value,
                    "description": op.description,
                    "sensitivity_class": op.sensitivity_class,
                    "required_approval": op.required_approval,
                    "resource_type": op.resource_type,
                    "depends_on": op.depends_on,
                    "runtime_checks": op.runtime_checks,
                    "status": op.status,
                }
                for op in self.opcodes
            ],
        }
