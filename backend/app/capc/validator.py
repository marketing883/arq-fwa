"""
Static IR Validator — validates compiled IR against the Policy Graph
before any execution occurs.

Checks:
    1. Role-based permission per opcode
    2. Sensitivity threshold per opcode
    3. Model/tool class constraints
    4. Attaches runtime check hooks for dynamic validation
"""

import logging
from dataclasses import dataclass, field

from app.auth.context import RequestContext
from app.capc.opcodes import ComplianceIR, Opcode
from app.capc.policy_graph import PolicyGraph

logger = logging.getLogger(__name__)


@dataclass
class OpcodeValidation:
    """Validation result for a single opcode."""
    opcode_id: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    runtime_checks_added: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Aggregate validation result for the entire IR."""
    passed: bool
    opcode_results: list[OpcodeValidation] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    runtime_checks_needed: bool = False


class IRValidator:
    """
    Validates a ComplianceIR DAG against the PolicyGraph.

    If validation passes, the IR can proceed to execution.
    If validation fails, the IR is routed to the Exception Router.
    """

    def __init__(self, policy_graph: PolicyGraph | None = None):
        self.policy_graph = policy_graph or PolicyGraph()

    def validate(self, ir: ComplianceIR, ctx: RequestContext) -> ValidationResult:
        """
        Validate every opcode in the IR against the policy graph.

        Args:
            ir: The compiled ComplianceIR DAG
            ctx: The caller's request context (role, permissions)

        Returns:
            ValidationResult with per-opcode details
        """
        opcode_results: list[OpcodeValidation] = []
        all_errors: list[str] = []
        all_warnings: list[str] = []
        has_runtime_checks = False

        for opcode in ir.opcodes:
            result = self._validate_opcode(opcode, ctx)
            opcode_results.append(result)

            if not result.passed:
                all_errors.extend(result.errors)
            all_warnings.extend(result.warnings)

            if result.runtime_checks_added:
                has_runtime_checks = True
                # Attach runtime checks to the opcode
                opcode.runtime_checks.extend(result.runtime_checks_added)

        passed = len(all_errors) == 0

        # Update IR validation state
        ir.validated = passed
        ir.validation_errors = all_errors

        if passed:
            logger.info("IR %s validated: %d opcodes passed", ir.ir_id, len(ir.opcodes))
        else:
            logger.warning("IR %s validation failed: %d errors", ir.ir_id, len(all_errors))

        return ValidationResult(
            passed=passed,
            opcode_results=opcode_results,
            errors=all_errors,
            warnings=all_warnings,
            runtime_checks_needed=has_runtime_checks,
        )

    def _validate_opcode(self, opcode: Opcode, ctx: RequestContext) -> OpcodeValidation:
        """Validate a single opcode against the policy graph."""
        errors: list[str] = []
        warnings: list[str] = []
        runtime_checks: list[str] = []

        # Check 1: Role-based permissions
        perm_ok, perm_reason = self.policy_graph.check_opcode_permission(
            opcode.opcode_type, ctx.permissions,
        )
        if not perm_ok:
            errors.append(f"[{opcode.opcode_id}] Permission denied: {perm_reason}")

        # Check 2: Sensitivity threshold
        sens_ok, sens_reason = self.policy_graph.check_sensitivity_threshold(
            opcode.sensitivity_class, ctx.role,
        )
        if not sens_ok:
            errors.append(f"[{opcode.opcode_id}] Sensitivity violation: {sens_reason}")

        # Check 3: Model/tool class constraints
        tool_ok, tool_reason = self.policy_graph.check_model_tool_constraint(
            opcode.model_tool_class, opcode.sensitivity_class,
        )
        if not tool_ok:
            errors.append(f"[{opcode.opcode_id}] Tool constraint: {tool_reason}")

        # Check 4: Attach runtime checks for dynamic conditions
        if opcode.sensitivity_class in ("SENSITIVE", "RESTRICTED", "CLASSIFIED"):
            runtime_checks.append("runtime_verify_data_lineage")
            warnings.append(
                f"[{opcode.opcode_id}] Runtime lineage verification attached "
                f"(sensitivity: {opcode.sensitivity_class})"
            )

        if opcode.fields_modified:
            runtime_checks.append("runtime_verify_mutation_scope")

        return OpcodeValidation(
            opcode_id=opcode.opcode_id,
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            runtime_checks_added=runtime_checks,
        )
