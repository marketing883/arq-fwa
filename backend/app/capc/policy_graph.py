"""
Policy Graph — the compliance knowledge base that encodes all policy rules.

This extends the existing auth layer (permissions, roles, data_classification)
into a structured graph that the Static IR Validator queries.

The policy graph encodes:
    - Role-based permissions per opcode type
    - Data sensitivity thresholds per role
    - Data transfer restrictions (jurisdictional rules)
    - Model/tool allowances per sensitivity level
"""

from app.auth.permissions import Permission
from app.auth.roles import Role, ROLE_PERMISSIONS
from app.auth.data_classification import Sensitivity
from app.capc.opcodes import OpcodeType


# ── Opcode → required permissions ────────────────────────────────────────────

OPCODE_REQUIRED_PERMISSIONS: dict[OpcodeType, set[Permission]] = {
    # Read-only queries
    OpcodeType.QUERY_DATA: {Permission.CASES_READ},
    OpcodeType.QUERY_AGGREGATE: {Permission.DASHBOARD_VIEW},
    OpcodeType.QUERY_DETAIL: {Permission.CASES_READ},

    # Financial queries
    OpcodeType.AGGREGATE_FINANCIAL: {Permission.FINANCIAL_VIEW},

    # Mutations
    OpcodeType.CREATE_RECORD: {Permission.CASES_MANAGE},
    OpcodeType.UPDATE_RECORD: {Permission.CASES_MANAGE},
    OpcodeType.DELETE_RECORD: {Permission.ADMIN_SYSTEM},

    # Rule / scoring operations
    OpcodeType.EVALUATE_RULE: {Permission.RULES_READ},
    OpcodeType.CALCULATE_SCORE: {Permission.SCORING_READ},

    # LLM operations
    OpcodeType.LLM_INFERENCE: {Permission.AGENT_CHAT},
    OpcodeType.LLM_INVESTIGATION: {Permission.AGENT_INVESTIGATE},
    OpcodeType.LLM_SUMMARIZE: {Permission.AGENT_CHAT},

    # Output
    OpcodeType.FORMAT_RESPONSE: set(),  # no gate
    OpcodeType.REDACT_FIELDS: set(),    # no gate (redaction is always allowed)

    # Control flow
    OpcodeType.BRANCH_ON_POLICY: set(),
    OpcodeType.REQUIRE_APPROVAL: set(),
}


# ── Sensitivity → minimum role ──────────────────────────────────────────────

SENSITIVITY_MINIMUM_ROLE: dict[str, Role] = {
    "PUBLIC": Role.VIEWER,
    "INTERNAL": Role.ANALYST,
    "SENSITIVE": Role.INVESTIGATOR,
    "RESTRICTED": Role.COMPLIANCE,
    "CLASSIFIED": Role.ADMIN,
}


# ── Model/tool class → allowed sensitivity levels ────────────────────────────

MODEL_TOOL_SENSITIVITY_LIMITS: dict[str, str] = {
    "db_query": "CLASSIFIED",       # DB queries can access any level (with permission)
    "slm": "RESTRICTED",            # Local SLM can process up to RESTRICTED
    "llm_large": "SENSITIVE",       # External LLM capped at SENSITIVE (no RESTRICTED/CLASSIFIED)
    "external_api": "INTERNAL",     # External APIs only see INTERNAL data
}


class PolicyGraph:
    """
    Structured compliance knowledge base.

    Encodes role-based permissions, sensitivity thresholds, and model/tool
    constraints.  Used by the IR Validator to gate operations.
    """

    def check_opcode_permission(
        self,
        opcode_type: OpcodeType,
        permissions: set[Permission],
    ) -> tuple[bool, str]:
        """Check if the caller's permissions allow this opcode type."""
        required = OPCODE_REQUIRED_PERMISSIONS.get(opcode_type, set())
        if not required:
            return True, "no_permission_required"
        if required.issubset(permissions):
            return True, "permitted"
        missing = required - permissions
        return False, f"missing_permissions: {', '.join(p.value for p in missing)}"

    def check_sensitivity_threshold(
        self,
        sensitivity_class: str,
        role: Role,
    ) -> tuple[bool, str]:
        """Check if the caller's role meets the sensitivity threshold."""
        min_role = SENSITIVITY_MINIMUM_ROLE.get(sensitivity_class, Role.ADMIN)
        role_hierarchy = {
            Role.VIEWER: 0, Role.ANALYST: 1, Role.INVESTIGATOR: 2,
            Role.COMPLIANCE: 3, Role.ADMIN: 4, Role.SYSTEM: 5,
        }
        caller_level = role_hierarchy.get(role, 0)
        required_level = role_hierarchy.get(min_role, 5)
        if caller_level >= required_level:
            return True, "sensitivity_ok"
        return False, f"role '{role.value}' insufficient for sensitivity '{sensitivity_class}' (requires '{min_role.value}')"

    def check_model_tool_constraint(
        self,
        model_tool_class: str | None,
        sensitivity_class: str,
    ) -> tuple[bool, str]:
        """Check if the model/tool class is allowed for this sensitivity level."""
        if not model_tool_class:
            return True, "no_tool_constraint"
        max_sensitivity = MODEL_TOOL_SENSITIVITY_LIMITS.get(model_tool_class)
        if not max_sensitivity:
            return True, "unknown_tool_class"
        levels = {"PUBLIC": 0, "INTERNAL": 1, "SENSITIVE": 2, "RESTRICTED": 3, "CLASSIFIED": 4}
        if levels.get(sensitivity_class, 0) <= levels.get(max_sensitivity, 0):
            return True, "tool_allowed"
        return False, (
            f"model/tool '{model_tool_class}' cannot process '{sensitivity_class}' data "
            f"(max: '{max_sensitivity}')"
        )
