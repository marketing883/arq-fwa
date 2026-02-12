"""
Rule Engine (Phase 5 orchestrator)

Discovers all registered rules, loads their configs from the DB,
and evaluates claims against all enabled rules.
"""

import importlib
import pkgutil
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rule, RuleResult
from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim, EnrichedPharmacyClaim


class RuleEngine:
    """Orchestrates rule evaluation across all registered rules."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.rules: dict[str, BaseRule] = {}
        self.configs: dict[str, dict] = {}

    async def load_rules(self) -> None:
        """Discover and register all rule implementations from app.rules.medical and app.rules.pharmacy."""
        self.rules = {}
        for package_name in ["app.rules.medical", "app.rules.pharmacy"]:
            try:
                package = importlib.import_module(package_name)
            except ImportError:
                continue

            for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
                module = importlib.import_module(f"{package_name}.{modname}")
                # Find all BaseRule subclasses in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseRule)
                        and attr is not BaseRule
                        and hasattr(attr, "rule_id")
                    ):
                        instance = attr()
                        self.rules[instance.rule_id] = instance

    async def load_configs(self) -> None:
        """Load rule configs (weights, thresholds, enabled/disabled) from DB."""
        result = await self.session.execute(select(Rule))
        for row in result.scalars():
            self.configs[row.rule_id] = {
                "enabled": row.enabled,
                "weight": float(row.weight),
                "thresholds": row.thresholds or {},
            }

    async def evaluate_claim(
        self, claim: EnrichedMedicalClaim | EnrichedPharmacyClaim, batch_id: str | None = None,
    ) -> list[RuleResult]:
        """Run all enabled rules against a single enriched claim."""
        if not self.rules:
            await self.load_rules()
        if not self.configs:
            await self.load_configs()

        claim_type = "medical" if isinstance(claim, EnrichedMedicalClaim) else "pharmacy"
        results = []

        for rule_id, rule in self.rules.items():
            # Only run rules matching claim type
            if rule.claim_type != claim_type:
                continue

            config = self.configs.get(rule_id, {})
            if not config.get("enabled", True):
                continue

            thresholds = config.get("thresholds", rule.default_thresholds)

            try:
                evaluation: RuleEvaluation = await rule.evaluate(claim, thresholds)
            except Exception as e:
                # Log but don't crash the pipeline
                evaluation = RuleEvaluation(
                    rule_id=rule_id,
                    triggered=False,
                    details=f"Rule evaluation error: {str(e)[:200]}",
                )

            result = RuleResult(
                claim_id=claim.claim_id,
                claim_type=claim_type,
                rule_id=rule_id,
                triggered=evaluation.triggered,
                severity=evaluation.severity if evaluation.triggered else None,
                confidence=evaluation.confidence if evaluation.triggered else None,
                evidence=evaluation.evidence if evaluation.triggered else {},
                details=evaluation.details,
                batch_id=batch_id,
            )
            results.append(result)

        return results

    async def evaluate_batch(
        self,
        claims: list[EnrichedMedicalClaim] | list[EnrichedPharmacyClaim],
        batch_id: str | None = None,
    ) -> dict[str, list[RuleResult]]:
        """Run all rules against a batch of claims. Returns {claim_id: [results]}."""
        all_results: dict[str, list[RuleResult]] = {}

        for claim in claims:
            results = await self.evaluate_claim(claim, batch_id)
            all_results[claim.claim_id] = results

        return all_results

    async def save_results(self, results: dict[str, list[RuleResult]]) -> int:
        """Persist rule results to DB. Returns count saved."""
        count = 0
        batch = []
        for claim_id, rule_results in results.items():
            for rr in rule_results:
                batch.append(rr)
                count += 1
                if len(batch) >= 500:
                    self.session.add_all(batch)
                    await self.session.flush()
                    batch = []

        if batch:
            self.session.add_all(batch)
            await self.session.flush()

        return count

    def get_triggered_rules(self, results: list[RuleResult]) -> list[RuleResult]:
        """Filter to only triggered rules."""
        return [r for r in results if r.triggered]

    def get_rule_count(self) -> int:
        """Return count of loaded rules."""
        return len(self.rules)
