"""
Case Manager Service (Phase 11)

Manages the full investigation case lifecycle:
- Auto-creation from risk scores
- Evidence bundle generation
- Status transitions with validation
- Resolution path handling
- SLA management
"""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    InvestigationCase,
    CaseNote,
    CaseEvidence,
    RiskScore,
    RuleResult,
    MedicalClaim,
    PharmacyClaim,
)
from app.services.audit_service import AuditService


# Priority → SLA hours mapping
_SLA_HOURS = {
    "P1": 48,
    "P2": 120,   # 5 business days
    "P3": 240,   # 10 business days
    "P4": 480,   # 20 business days
}

# Valid status transitions
VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"under_review", "escalated"},
    "under_review": {"resolved", "escalated", "open"},
    "escalated": {"under_review", "resolved"},
    "resolved": {"closed", "under_review"},
    "closed": set(),  # terminal
}

# Resolution paths from the POC spec
RESOLUTION_PATHS = {
    "provider_accepts",
    "provider_disputes",
    "plan_benefit_issue",
    "no_response",
    "complex_case",
    "false_positive",
}


class CaseManager:
    """Manages the full investigation case lifecycle."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    # ── Auto-creation from scores ────────────────────────────────────────

    async def create_cases_from_scores(
        self,
        scores: list[RiskScore],
        *,
        generate_evidence: bool = True,
        workspace_id: int | None = None,
        claim_ws_map: dict[str, int | None] | None = None,
    ) -> list[InvestigationCase]:
        """
        For each score with risk_level in [high, critical]:
          - Create InvestigationCase
          - Set priority: critical→P1, high→P2
          - Set SLA deadline based on priority
          - Optionally generate initial evidence bundle
          - Create audit log entry
        """
        cases_created: list[InvestigationCase] = []

        for score in scores:
            if score.risk_level not in ("high", "critical"):
                continue

            # Check if case already exists for this claim
            existing = await self.session.execute(
                select(InvestigationCase.id).where(
                    InvestigationCase.claim_id == score.claim_id
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            priority = "P1" if score.risk_level == "critical" else "P2"
            sla_hours = _SLA_HOURS[priority]

            # Resolve workspace_id: per-claim map takes precedence, then fallback
            case_ws_id = workspace_id
            if claim_ws_map and score.claim_id in claim_ws_map:
                case_ws_id = claim_ws_map[score.claim_id]

            case = InvestigationCase(
                case_id=f"CASE-{uuid4().hex[:8].upper()}",
                claim_id=score.claim_id,
                claim_type=score.claim_type,
                risk_score=score.total_score,
                risk_level=score.risk_level,
                status="open",
                priority=priority,
                sla_deadline=datetime.utcnow() + timedelta(hours=sla_hours),
                workspace_id=case_ws_id,
            )
            self.session.add(case)
            cases_created.append(case)

        # Flush to get IDs
        if cases_created:
            await self.session.flush()

        # Generate evidence bundles and audit entries
        for case in cases_created:
            await self.audit.log_case_created(
                case_id=case.case_id,
                claim_id=case.claim_id,
                risk_level=case.risk_level,
            )

            if generate_evidence:
                await self._generate_evidence_bundle(case)

        if cases_created:
            await self.session.flush()

        return cases_created

    # ── Evidence bundle generation ───────────────────────────────────────

    async def _generate_evidence_bundle(self, case: InvestigationCase) -> None:
        """Generate initial evidence items for a new case."""

        # 1. Claim data evidence
        claim_data = await self._get_claim_data(case.claim_id, case.claim_type)
        if claim_data:
            self.session.add(CaseEvidence(
                case_id=case.id,
                evidence_type="claim_data",
                title="Original Claim Record",
                content=claim_data,
            ))

        # 2. Risk score breakdown
        score_q = await self.session.execute(
            select(RiskScore).where(RiskScore.claim_id == case.claim_id)
        )
        score = score_q.scalar_one_or_none()
        if score:
            self.session.add(CaseEvidence(
                case_id=case.id,
                evidence_type="risk_assessment",
                title="Risk Score Breakdown",
                content={
                    "total_score": float(score.total_score),
                    "risk_level": score.risk_level,
                    "rules_triggered": score.rules_triggered,
                    "rule_contributions": score.rule_contributions or {},
                    "confidence_factor": float(score.confidence_factor),
                },
            ))

        # 3. Triggered rule details
        rr_q = await self.session.execute(
            select(RuleResult).where(
                and_(
                    RuleResult.claim_id == case.claim_id,
                    RuleResult.triggered == True,
                )
            ).order_by(RuleResult.rule_id)
        )
        triggered_rules = list(rr_q.scalars())

        if triggered_rules:
            rules_evidence = []
            for rr in triggered_rules:
                rules_evidence.append({
                    "rule_id": rr.rule_id,
                    "severity": float(rr.severity) if rr.severity else None,
                    "confidence": float(rr.confidence) if rr.confidence else None,
                    "evidence": rr.evidence or {},
                    "details": rr.details,
                })

            self.session.add(CaseEvidence(
                case_id=case.id,
                evidence_type="rule_findings",
                title=f"{len(triggered_rules)} Rules Triggered",
                content={"triggered_rules": rules_evidence},
            ))

        # 4. Provider history (if medical claim with provider)
        if claim_data and claim_data.get("provider_id"):
            provider_id = claim_data["provider_id"]
            provider_history = await self._get_provider_history(provider_id)
            if provider_history:
                self.session.add(CaseEvidence(
                    case_id=case.id,
                    evidence_type="provider_history",
                    title="Provider Flag History",
                    content=provider_history,
                ))

    async def _get_claim_data(self, claim_id: str, claim_type: str) -> dict | None:
        """Load claim data as a dict."""
        if claim_type == "medical":
            q = await self.session.execute(
                select(MedicalClaim).where(MedicalClaim.claim_id == claim_id)
            )
            c = q.scalar_one_or_none()
            if not c:
                return None
            return {
                "claim_id": c.claim_id,
                "claim_type": "medical",
                "member_id": c.member_id,
                "provider_id": c.provider_id,
                "service_date": str(c.service_date),
                "cpt_code": c.cpt_code,
                "cpt_modifier": c.cpt_modifier,
                "diagnosis_code_primary": c.diagnosis_code_primary,
                "place_of_service": c.place_of_service,
                "amount_billed": float(c.amount_billed),
                "amount_allowed": float(c.amount_allowed) if c.amount_allowed else None,
                "amount_paid": float(c.amount_paid) if c.amount_paid else None,
                "units": c.units,
            }
        else:
            q = await self.session.execute(
                select(PharmacyClaim).where(PharmacyClaim.claim_id == claim_id)
            )
            c = q.scalar_one_or_none()
            if not c:
                return None
            return {
                "claim_id": c.claim_id,
                "claim_type": "pharmacy",
                "member_id": c.member_id,
                "pharmacy_id": c.pharmacy_id,
                "prescriber_id": c.prescriber_id,
                "fill_date": str(c.fill_date),
                "ndc_code": c.ndc_code,
                "drug_name": c.drug_name,
                "drug_class": c.drug_class,
                "is_controlled": c.is_controlled,
                "dea_schedule": c.dea_schedule,
                "quantity_dispensed": float(c.quantity_dispensed),
                "days_supply": c.days_supply,
                "amount_billed": float(c.amount_billed),
                "amount_allowed": float(c.amount_allowed) if c.amount_allowed else None,
                "amount_paid": float(c.amount_paid) if c.amount_paid else None,
            }

    async def _get_provider_history(self, provider_id: int) -> dict | None:
        """Get provider flagging history summary."""
        # Count total flagged claims for this provider
        med_flagged_q = await self.session.execute(
            select(func.count()).select_from(MedicalClaim).where(
                and_(
                    MedicalClaim.provider_id == provider_id,
                    MedicalClaim.claim_id.in_(
                        select(RiskScore.claim_id).where(
                            RiskScore.risk_level.in_(["high", "critical"])
                        )
                    ),
                )
            )
        )
        flagged_count = med_flagged_q.scalar() or 0

        # Count total claims
        total_q = await self.session.execute(
            select(func.count()).select_from(MedicalClaim).where(
                MedicalClaim.provider_id == provider_id
            )
        )
        total_count = total_q.scalar() or 0

        # Count existing investigation cases
        case_count_q = await self.session.execute(
            select(func.count()).select_from(InvestigationCase).where(
                InvestigationCase.claim_id.in_(
                    select(MedicalClaim.claim_id).where(
                        MedicalClaim.provider_id == provider_id
                    )
                )
            )
        )
        case_count = case_count_q.scalar() or 0

        if total_count == 0:
            return None

        return {
            "provider_id": provider_id,
            "total_claims": total_count,
            "flagged_claims": flagged_count,
            "flag_rate": round(flagged_count / total_count * 100, 1) if total_count > 0 else 0,
            "existing_cases": case_count,
        }

    # ── Status transitions ───────────────────────────────────────────────

    async def update_status(
        self,
        case_id: str,
        new_status: str,
        *,
        actor: str = "system",
        resolution_path: str | None = None,
        resolution_notes: str | None = None,
    ) -> InvestigationCase:
        """
        Update case status with validated transitions.

        Allowed transitions:
            open -> under_review | escalated
            under_review -> resolved | escalated | open
            escalated -> under_review | resolved
            resolved -> closed | under_review
            closed -> (terminal)
        """
        q = await self.session.execute(
            select(InvestigationCase).where(InvestigationCase.case_id == case_id)
        )
        case = q.scalar_one_or_none()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        allowed = VALID_TRANSITIONS.get(case.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {case.status} -> {new_status}. "
                f"Allowed: {sorted(allowed) if allowed else 'none (terminal)'}"
            )

        old_status = case.status
        case.status = new_status

        if resolution_path is not None:
            if resolution_path not in RESOLUTION_PATHS:
                raise ValueError(
                    f"Invalid resolution path: {resolution_path}. "
                    f"Valid: {sorted(RESOLUTION_PATHS)}"
                )
            case.resolution_path = resolution_path

        if resolution_notes is not None:
            case.resolution_notes = resolution_notes

        now = datetime.utcnow()
        if new_status == "resolved":
            case.resolved_at = now
        elif new_status == "closed":
            case.closed_at = now

        await self.audit.log_case_updated(
            case_id=case.case_id,
            old_status=old_status,
            new_status=new_status,
            actor=actor,
        )

        await self.session.flush()
        return case

    # ── Resolution handling ──────────────────────────────────────────────

    async def resolve_case(
        self,
        case_id: str,
        resolution_path: str,
        resolution_notes: str,
        *,
        actor: str = "system",
        recovery_amount: float | None = None,
    ) -> InvestigationCase:
        """Resolve a case with a specific resolution path."""
        q = await self.session.execute(
            select(InvestigationCase).where(InvestigationCase.case_id == case_id)
        )
        case = q.scalar_one_or_none()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        if case.status not in ("under_review", "escalated"):
            raise ValueError(
                f"Cannot resolve case in '{case.status}' status. "
                f"Must be 'under_review' or 'escalated'."
            )

        case.status = "resolved"
        case.resolution_path = resolution_path
        case.resolution_notes = resolution_notes
        case.resolved_at = datetime.utcnow()

        if recovery_amount is not None:
            case.recovery_amount = Decimal(str(recovery_amount))

        # Add resolution note
        note = CaseNote(
            case_id=case.id,
            author=actor,
            content=f"Case resolved via '{resolution_path}': {resolution_notes}",
        )
        self.session.add(note)

        await self.audit.log_case_updated(
            case_id=case.case_id,
            old_status="under_review",
            new_status="resolved",
            actor=actor,
        )

        await self.session.flush()
        return case

    # ── Escalation ───────────────────────────────────────────────────────

    async def escalate_case(
        self,
        case_id: str,
        reason: str,
        *,
        actor: str = "system",
        new_priority: str | None = None,
    ) -> InvestigationCase:
        """Escalate a case, optionally upgrading priority."""
        q = await self.session.execute(
            select(InvestigationCase).where(InvestigationCase.case_id == case_id)
        )
        case = q.scalar_one_or_none()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        old_status = case.status
        case.status = "escalated"

        if new_priority and new_priority in ("P1", "P2", "P3", "P4"):
            case.priority = new_priority
            # Update SLA based on new priority
            case.sla_deadline = datetime.utcnow() + timedelta(
                hours=_SLA_HOURS[new_priority]
            )

        # Add escalation note
        note = CaseNote(
            case_id=case.id,
            author=actor,
            content=f"Case escalated: {reason}",
        )
        self.session.add(note)

        await self.audit.log_event(
            event_type="case_escalated",
            actor=actor,
            action=f"Case {case.case_id} escalated: {reason}",
            resource_type="case",
            resource_id=case.case_id,
            details={
                "old_status": old_status,
                "reason": reason,
                "new_priority": new_priority,
            },
        )

        await self.session.flush()
        return case

    # ── SLA checking ─────────────────────────────────────────────────────

    async def get_sla_breached_cases(self) -> list[InvestigationCase]:
        """Return all open/in-review cases past their SLA deadline."""
        now = datetime.utcnow()
        q = await self.session.execute(
            select(InvestigationCase).where(
                and_(
                    InvestigationCase.status.in_(["open", "under_review", "escalated"]),
                    InvestigationCase.sla_deadline < now,
                )
            ).order_by(InvestigationCase.priority.asc())
        )
        return list(q.scalars())

    # ── Statistics ───────────────────────────────────────────────────────

    async def get_case_stats(self) -> dict:
        """Get case statistics for dashboard."""
        # By status
        status_q = await self.session.execute(
            select(
                InvestigationCase.status,
                func.count().label("count"),
            ).group_by(InvestigationCase.status)
        )
        by_status = {row[0]: row[1] for row in status_q}

        # By priority
        priority_q = await self.session.execute(
            select(
                InvestigationCase.priority,
                func.count().label("count"),
            ).where(
                InvestigationCase.status.in_(["open", "under_review", "escalated"])
            ).group_by(InvestigationCase.priority)
        )
        by_priority = {row[0]: row[1] for row in priority_q}

        # Average resolution time (for resolved/closed cases)
        resolved_q = await self.session.execute(
            select(InvestigationCase).where(
                InvestigationCase.resolved_at.isnot(None)
            )
        )
        resolved_cases = list(resolved_q.scalars())
        avg_resolution_hours = None
        if resolved_cases:
            total_hours = sum(
                (c.resolved_at - c.created_at).total_seconds() / 3600
                for c in resolved_cases
                if c.resolved_at and c.created_at
            )
            avg_resolution_hours = round(total_hours / len(resolved_cases), 1)

        # SLA breach count
        now = datetime.utcnow()
        breach_q = await self.session.execute(
            select(func.count()).select_from(InvestigationCase).where(
                and_(
                    InvestigationCase.status.in_(["open", "under_review", "escalated"]),
                    InvestigationCase.sla_deadline < now,
                )
            )
        )
        sla_breached = breach_q.scalar() or 0

        return {
            "by_status": by_status,
            "by_priority": by_priority,
            "total_active": sum(
                by_status.get(s, 0)
                for s in ["open", "under_review", "escalated"]
            ),
            "total_resolved": by_status.get("resolved", 0) + by_status.get("closed", 0),
            "avg_resolution_hours": avg_resolution_hours,
            "sla_breached_count": sla_breached,
        }
