"""
Exception Router — handles compliance violations detected at compile-time
(IR validation) or runtime (execution checks).

Three possible actions:
    1. ABORT    — terminate the operation entirely
    2. ROLLBACK — undo partial execution (restore pre-execution state)
    3. REVIEW   — forward to manual human review for a compliance decision
"""

import logging
from dataclasses import dataclass
from enum import Enum

from app.capc.opcodes import ComplianceIR
from app.capc.validator import ValidationResult

logger = logging.getLogger(__name__)


class ExceptionAction(str, Enum):
    ABORT = "abort"
    ROLLBACK = "rollback"
    REVIEW = "forward_to_review"


@dataclass
class ExceptionDecision:
    """The routing decision for a compliance exception."""
    action: ExceptionAction
    reason: str
    affected_opcodes: list[str]
    severity: str  # low, medium, high, critical


# Hard policy violations → always abort
HARD_VIOLATION_PATTERNS = [
    "Permission denied",
    "role 'viewer' insufficient",
    "missing_permissions: admin",
]

# Sensitivity violations → route to review (ambiguous, human judgment needed)
SENSITIVITY_VIOLATION_PATTERNS = [
    "Sensitivity violation",
    "insufficient for sensitivity 'RESTRICTED'",
    "insufficient for sensitivity 'CLASSIFIED'",
]


class ExceptionRouter:
    """
    Routes compliance exceptions to the appropriate handling action.

    Called when:
    - Static IR validation fails
    - Runtime checks detect a violation during execution
    """

    def route_validation_failure(
        self,
        ir: ComplianceIR,
        validation_result: ValidationResult,
    ) -> ExceptionDecision:
        """
        Route a compile-time validation failure.

        Analyzes the validation errors to determine whether to abort,
        rollback (N/A at compile time), or forward to manual review.
        """
        errors = validation_result.errors
        affected = [r.opcode_id for r in validation_result.opcode_results if not r.passed]

        # Check for hard violations → ABORT
        for error in errors:
            if any(pattern in error for pattern in HARD_VIOLATION_PATTERNS):
                logger.warning("Hard policy violation in IR %s: %s", ir.ir_id, error)
                return ExceptionDecision(
                    action=ExceptionAction.ABORT,
                    reason=f"Hard policy violation: {error}",
                    affected_opcodes=affected,
                    severity="critical",
                )

        # Check for sensitivity violations → REVIEW
        for error in errors:
            if any(pattern in error for pattern in SENSITIVITY_VIOLATION_PATTERNS):
                logger.info("Sensitivity violation in IR %s → routing to review", ir.ir_id)
                return ExceptionDecision(
                    action=ExceptionAction.REVIEW,
                    reason=f"Sensitivity threshold exceeded: {error}",
                    affected_opcodes=affected,
                    severity="high",
                )

        # Default: abort for unknown violations
        return ExceptionDecision(
            action=ExceptionAction.ABORT,
            reason=f"Validation failed with {len(errors)} error(s): {'; '.join(errors[:3])}",
            affected_opcodes=affected,
            severity="high",
        )

    def route_runtime_violation(
        self,
        ir: ComplianceIR,
        opcode_id: str,
        violation_type: str,
        details: str = "",
    ) -> ExceptionDecision:
        """
        Route a runtime violation detected during execution.

        Args:
            ir: The IR being executed
            opcode_id: The opcode where the violation occurred
            violation_type: Type of violation (lineage, drift, anomaly, permission)
            details: Additional context
        """
        if violation_type in ("permission", "unauthorized"):
            return ExceptionDecision(
                action=ExceptionAction.ABORT,
                reason=f"Runtime permission violation at {opcode_id}: {details}",
                affected_opcodes=[opcode_id],
                severity="critical",
            )

        if violation_type == "drift":
            # Drift detection from ODA-RAG signals → rollback and retry with updated params
            return ExceptionDecision(
                action=ExceptionAction.ROLLBACK,
                reason=f"Data drift detected at {opcode_id}: {details}",
                affected_opcodes=[opcode_id],
                severity="medium",
            )

        if violation_type in ("anomaly", "lineage"):
            # Anomalous behavior or lineage mismatch → human review
            return ExceptionDecision(
                action=ExceptionAction.REVIEW,
                reason=f"Runtime {violation_type} at {opcode_id}: {details}",
                affected_opcodes=[opcode_id],
                severity="high",
            )

        return ExceptionDecision(
            action=ExceptionAction.ABORT,
            reason=f"Unknown runtime violation ({violation_type}) at {opcode_id}: {details}",
            affected_opcodes=[opcode_id],
            severity="high",
        )
