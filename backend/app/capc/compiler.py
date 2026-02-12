"""
Compliance IR Compiler — transforms parsed natural language requests into
a DAG of compliance-annotated opcodes.

Pipeline:
    1. Parse NL request → extract intents, entities, sensitivity
    2. Map intents to opcode sequences
    3. Annotate each opcode with sensitivity, approval level, constraints
    4. Build dependency edges
    5. Return ComplianceIR DAG
"""

import logging
import re
from uuid import uuid4

from app.capc.opcodes import Opcode, OpcodeType, ComplianceIR
from app.auth.data_classification import Sensitivity, TOOL_SENSITIVITY

logger = logging.getLogger(__name__)

# Intent patterns → tool/action mapping
INTENT_PATTERNS: list[tuple[list[str], str, OpcodeType]] = [
    # Financial queries
    (["amount", "save", "saved", "saving", "cost", "dollar", "money", "financial",
      "prevent", "prevention", "recover", "fraud amount", "billed", "paid",
      "loss", "revenue", "impact", "worth", "expense"],
     "query_financial_summary", OpcodeType.AGGREGATE_FINANCIAL),

    # Case queries
    (["case", "cases", "investigation", "investigate"],
     "query_cases", OpcodeType.QUERY_DATA),

    # Specific case detail
    (["detail", "explain", "analyze", "describe"],
     "query_case_detail", OpcodeType.QUERY_DETAIL),

    # Pipeline / stats
    (["stats", "statistics", "overview", "summary", "dashboard", "count", "how many", "total"],
     "query_pipeline_stats", OpcodeType.QUERY_AGGREGATE),

    # Rules
    (["rule", "rules", "trigger", "detection", "pattern", "flag"],
     "query_rules", OpcodeType.QUERY_DATA),

    # Provider
    (["provider", "doctor", "npi"],
     "query_provider", OpcodeType.QUERY_DATA),
]

# Entity extraction patterns
CASE_ID_RE = re.compile(r'(CASE-[A-Z0-9]{6,})')
NPI_RE = re.compile(r'\b(\d{10})\b')
RISK_LEVEL_RE = re.compile(r'\b(critical|high|medium|low)\b', re.IGNORECASE)

# Sensitivity mapping for detected entities
ENTITY_SENSITIVITY: dict[str, str] = {
    "case_id": "INTERNAL",
    "npi": "INTERNAL",
    "risk_level": "PUBLIC",
    "financial_amount": "RESTRICTED",
    "member_id": "SENSITIVE",
    "claim_id": "INTERNAL",
}

# Tool name → sensitivity class
TOOL_SENSITIVITY_CLASS: dict[str, str] = {
    "query_pipeline_stats": "PUBLIC",
    "query_cases": "INTERNAL",
    "query_case_detail": "INTERNAL",
    "query_rules": "INTERNAL",
    "query_provider": "INTERNAL",
    "query_financial_summary": "RESTRICTED",
}


class ComplianceIRCompiler:
    """
    Compiles natural language agent requests into compliance-annotated
    intermediate representations (DAG of opcodes).
    """

    def compile(self, request: str, agent_id: str, workspace_id: int | None = None) -> ComplianceIR:
        """
        Full compilation pipeline: parse → map → annotate → build DAG.

        Args:
            request: The natural language request from the user
            agent_id: The agent processing this request
            workspace_id: Workspace scope

        Returns:
            ComplianceIR DAG ready for validation and execution
        """
        ir_id = str(uuid4())

        # Step 1: Parse NL request
        intents = self._extract_intents(request)
        entities = self._extract_entities(request)
        overall_sensitivity = self._determine_sensitivity(intents, entities)

        # Step 2: Map intents to opcodes
        opcodes = self._build_opcodes(ir_id, request, intents, entities, overall_sensitivity)

        # Step 3: Add response formatting opcode
        if opcodes:
            format_op = Opcode(
                opcode_id=f"{ir_id}-format",
                opcode_type=OpcodeType.FORMAT_RESPONSE,
                description="Format and present results to user",
                sensitivity_class=overall_sensitivity,
                required_approval="auto",
                model_tool_class="slm",
                depends_on=[op.opcode_id for op in opcodes],
            )

            # Add redaction opcode if sensitivity requires it
            if overall_sensitivity in ("RESTRICTED", "CLASSIFIED"):
                redact_op = Opcode(
                    opcode_id=f"{ir_id}-redact",
                    opcode_type=OpcodeType.REDACT_FIELDS,
                    description="Apply tier-based field redaction before presentation",
                    sensitivity_class=overall_sensitivity,
                    required_approval="auto",
                    depends_on=[op.opcode_id for op in opcodes],
                    runtime_checks=["check_caller_tier", "verify_field_access"],
                )
                format_op.depends_on = [redact_op.opcode_id]
                opcodes.append(redact_op)

            opcodes.append(format_op)

        ir = ComplianceIR(
            ir_id=ir_id,
            original_request=request,
            agent_id=agent_id,
            workspace_id=workspace_id,
            intents=intents,
            entities=entities,
            overall_sensitivity=overall_sensitivity,
            opcodes=opcodes,
        )

        logger.info("Compiled IR %s: %d intents, %d entities, %d opcodes, sensitivity=%s",
                     ir_id, len(intents), len(entities), len(opcodes), overall_sensitivity)
        return ir

    def _extract_intents(self, request: str) -> list[str]:
        """Extract intents from the natural language request."""
        msg = request.lower()
        intents = []
        for patterns, tool_name, _ in INTENT_PATTERNS:
            if any(p in msg for p in patterns):
                intents.append(tool_name)
        # Default: general chat if no specific intent detected
        if not intents:
            intents.append("general_chat")
        return intents

    def _extract_entities(self, request: str) -> list[dict]:
        """Extract structured entities from the request."""
        entities = []

        for m in CASE_ID_RE.finditer(request):
            entities.append({"type": "case_id", "value": m.group(1),
                             "sensitivity": "INTERNAL"})

        for m in NPI_RE.finditer(request):
            entities.append({"type": "npi", "value": m.group(1),
                             "sensitivity": "INTERNAL"})

        for m in RISK_LEVEL_RE.finditer(request):
            entities.append({"type": "risk_level", "value": m.group(1).lower(),
                             "sensitivity": "PUBLIC"})

        # Detect financial intent entities
        msg = request.lower()
        if any(kw in msg for kw in ["amount", "dollar", "cost", "billed", "paid", "fraud"]):
            entities.append({"type": "financial_amount", "value": "requested",
                             "sensitivity": "RESTRICTED"})

        return entities

    def _determine_sensitivity(self, intents: list[str], entities: list[dict]) -> str:
        """Determine the overall sensitivity level for the request."""
        levels = {"PUBLIC": 0, "INTERNAL": 1, "SENSITIVE": 2, "RESTRICTED": 3, "CLASSIFIED": 4}
        max_level = 0

        # From intents (tool sensitivity)
        for intent in intents:
            tool_class = TOOL_SENSITIVITY_CLASS.get(intent, "INTERNAL")
            max_level = max(max_level, levels.get(tool_class, 1))

        # From entities
        for entity in entities:
            max_level = max(max_level, levels.get(entity.get("sensitivity", "INTERNAL"), 1))

        reverse = {v: k for k, v in levels.items()}
        return reverse.get(max_level, "INTERNAL")

    def _build_opcodes(
        self,
        ir_id: str,
        request: str,
        intents: list[str],
        entities: list[dict],
        overall_sensitivity: str,
    ) -> list[Opcode]:
        """Map intents and entities to a sequence of opcodes with dependencies."""
        opcodes: list[Opcode] = []
        previous_id: str | None = None

        for i, intent in enumerate(intents):
            # Find the matching opcode type
            opcode_type = OpcodeType.QUERY_DATA
            for patterns, tool_name, otype in INTENT_PATTERNS:
                if tool_name == intent:
                    opcode_type = otype
                    break

            sensitivity = TOOL_SENSITIVITY_CLASS.get(intent, "INTERNAL")

            # Determine required approval based on sensitivity
            if sensitivity in ("RESTRICTED", "CLASSIFIED"):
                required_approval = "enhanced_logging"
            else:
                required_approval = "auto"

            # Build resource scope from entities
            resource_ids = [e["value"] for e in entities
                           if e["type"] in ("case_id", "npi")]

            op = Opcode(
                opcode_id=f"{ir_id}-op{i}",
                opcode_type=opcode_type,
                description=f"Execute {intent}",
                sensitivity_class=sensitivity,
                required_approval=required_approval,
                model_tool_class="db_query" if "query" in intent else "slm",
                resource_type=self._intent_to_resource_type(intent),
                resource_ids=resource_ids,
                depends_on=[previous_id] if previous_id else [],
            )

            # Attach runtime checks for sensitive operations
            if sensitivity in ("SENSITIVE", "RESTRICTED", "CLASSIFIED"):
                op.runtime_checks.append("verify_caller_permissions")
                op.runtime_checks.append("check_data_sensitivity")
            if "financial" in intent:
                op.runtime_checks.append("apply_financial_redaction")

            opcodes.append(op)
            previous_id = op.opcode_id

        # If the request implies LLM reasoning, add an inference opcode
        msg = request.lower()
        if any(kw in msg for kw in ["explain", "analyze", "investigate", "why", "recommend"]):
            llm_op = Opcode(
                opcode_id=f"{ir_id}-llm",
                opcode_type=OpcodeType.LLM_INFERENCE,
                description="LLM analysis and reasoning",
                sensitivity_class=overall_sensitivity,
                required_approval="enhanced_logging" if overall_sensitivity != "PUBLIC" else "auto",
                model_tool_class="slm",
                depends_on=[previous_id] if previous_id else [],
                runtime_checks=["monitor_llm_output", "check_response_sensitivity"],
            )
            opcodes.append(llm_op)

        return opcodes

    @staticmethod
    def _intent_to_resource_type(intent: str) -> str | None:
        mapping = {
            "query_cases": "case",
            "query_case_detail": "case",
            "query_pipeline_stats": "pipeline",
            "query_rules": "rule",
            "query_provider": "provider",
            "query_financial_summary": "financial",
        }
        return mapping.get(intent)
