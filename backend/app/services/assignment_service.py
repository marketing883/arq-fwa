"""
Assignment Service — auto-assign investigation cases to investigators.

Supports three assignment strategies:
  - round_robin: least recently assigned investigator
  - workload_balanced: lowest active caseload
  - skill_matched: specialty match, then lowest caseload as tiebreaker
"""

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.investigator import Investigator
from app.models.assignment_rule import AssignmentRule
from app.models.case import InvestigationCase


class AssignmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def auto_assign(self, case: InvestigationCase) -> str | None:
        """Find the best investigator for a case using configured rules.
        Returns the investigator name or None if no match."""
        # Load enabled assignment rules ordered by priority ASC (lower = higher priority)
        result = await self.db.execute(
            select(AssignmentRule)
            .where(AssignmentRule.is_enabled == True)
            .order_by(AssignmentRule.priority.asc())
        )
        rules = list(result.scalars())

        if not rules:
            return None

        for rule in rules:
            if not self._match_conditions(case, rule.conditions):
                continue

            candidates = await self._find_candidates(
                rule.target_filter, case.workspace_id
            )
            if not candidates:
                continue

            investigator = None
            if rule.strategy == "round_robin":
                investigator = await self._round_robin(candidates)
            elif rule.strategy == "workload_balanced":
                investigator = await self._workload_balanced(candidates)
            elif rule.strategy == "skill_matched":
                investigator = await self._skill_matched(candidates, case)
            else:
                investigator = await self._round_robin(candidates)

            if investigator:
                return investigator.name

        return None

    def _match_conditions(
        self, case: InvestigationCase, conditions: dict
    ) -> bool:
        """Check if a case matches rule conditions."""
        if not conditions:
            return True  # Empty conditions = catch-all rule

        if "case_priority" in conditions:
            if case.priority not in conditions["case_priority"]:
                return False
        if "claim_type" in conditions:
            if case.claim_type not in conditions["claim_type"]:
                return False
        if "risk_level" in conditions:
            if case.risk_level not in conditions["risk_level"]:
                return False
        return True

    async def _find_candidates(
        self, target_filter: dict, workspace_id: int | None
    ) -> list[Investigator]:
        """Find available investigators matching the target filter."""
        conditions = [Investigator.is_available == True]

        if workspace_id is not None:
            conditions.append(
                or_(
                    Investigator.workspace_id == workspace_id,
                    Investigator.workspace_id.is_(None),
                )
            )

        if target_filter.get("seniority"):
            conditions.append(
                Investigator.seniority.in_(target_filter["seniority"])
            )
        if target_filter.get("specialty"):
            conditions.append(
                or_(
                    Investigator.specialty.in_(target_filter["specialty"]),
                    Investigator.specialty == "both",
                )
            )

        result = await self.db.execute(
            select(Investigator).where(and_(*conditions))
        )
        investigators = list(result.scalars())

        # Filter out investigators at max caseload
        eligible = []
        for inv in investigators:
            caseload = await self._get_active_caseload(inv)
            if caseload < inv.max_caseload:
                eligible.append(inv)

        return eligible

    async def _get_active_caseload(self, investigator: Investigator) -> int:
        """Count active (non-resolved, non-closed) cases assigned to this investigator."""
        result = await self.db.execute(
            select(func.count())
            .select_from(InvestigationCase)
            .where(
                and_(
                    InvestigationCase.assigned_to == investigator.name,
                    InvestigationCase.status.in_(
                        ["open", "under_review", "escalated"]
                    ),
                )
            )
        )
        return result.scalar() or 0

    async def _round_robin(
        self, candidates: list[Investigator]
    ) -> Investigator | None:
        """Pick the investigator who was least recently assigned a case."""
        if not candidates:
            return None

        best = candidates[0]
        best_time = None

        for inv in candidates:
            # Find most recent assignment
            result = await self.db.execute(
                select(InvestigationCase.created_at)
                .where(InvestigationCase.assigned_to == inv.name)
                .order_by(InvestigationCase.created_at.desc())
                .limit(1)
            )
            last_assigned = result.scalar_one_or_none()
            if last_assigned is None:
                return inv  # Never assigned, pick immediately
            if best_time is None or last_assigned < best_time:
                best_time = last_assigned
                best = inv

        return best

    async def _workload_balanced(
        self, candidates: list[Investigator]
    ) -> Investigator | None:
        """Pick the investigator with the lowest active caseload."""
        if not candidates:
            return None

        best = None
        best_load = float("inf")

        for inv in candidates:
            load = await self._get_active_caseload(inv)
            if load < best_load:
                best_load = load
                best = inv

        return best

    async def _skill_matched(
        self, candidates: list[Investigator], case: InvestigationCase
    ) -> Investigator | None:
        """Pick based on specialty match, then lowest workload as tiebreaker."""
        if not candidates:
            return None

        # Prefer exact specialty match over "both"
        exact_match = [
            inv for inv in candidates if inv.specialty == case.claim_type
        ]
        pool = exact_match if exact_match else candidates

        return await self._workload_balanced(pool)

    async def get_workload_summary(
        self, workspace_id: int | None = None
    ) -> list[dict]:
        """Return workload stats per investigator for dashboard."""
        conditions = []
        if workspace_id is not None:
            conditions.append(
                or_(
                    Investigator.workspace_id == workspace_id,
                    Investigator.workspace_id.is_(None),
                )
            )

        where_clause = and_(*conditions) if conditions else True
        result = await self.db.execute(
            select(Investigator).where(where_clause)
        )
        investigators = list(result.scalars())

        summary = []
        for inv in investigators:
            active = await self._get_active_caseload(inv)
            summary.append(
                {
                    "investigator_id": inv.investigator_id,
                    "name": inv.name,
                    "email": inv.email,
                    "specialty": inv.specialty,
                    "seniority": inv.seniority,
                    "active_cases": active,
                    "max_caseload": inv.max_caseload,
                    "utilization": round(active / inv.max_caseload * 100, 1)
                    if inv.max_caseload > 0
                    else 0,
                    "is_available": inv.is_available,
                }
            )

        return summary
