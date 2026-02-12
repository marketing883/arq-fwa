"""
M2: Unbundling Detection

Detects providers billing individual component CPT codes separately when
they should be billed as a single bundled code, inflating reimbursement.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class UnbundlingRule(BaseRule):
    """
    Detects unbundling by checking two patterns:

    1. Panel code with components: If the claim's CPT code has bundled_codes
       defined, it's a panel. Check if the provider also billed component
       codes on the same date (which means they're double-billing).

    2. Component code without panel: If the claim's CPT code is a known
       component of a panel, and other component codes from the same panel
       are also billed on the same date by the same provider, this indicates
       the provider is billing components separately instead of the panel.
    """

    rule_id = "M2"
    category = "Unbundling"
    fraud_type = "Fraud"
    claim_type = "medical"
    default_weight = 7.5
    default_thresholds = {
        "min_component_count": 2,
    }

    # Known panel → component mappings (from reference data)
    PANEL_COMPONENTS = {
        "80048": ["82310", "82374", "82435", "82565", "82947", "84132", "84295", "84520"],
        "80053": ["82310", "82374", "82435", "82565", "82947", "84132", "84295", "84520",
                  "82247", "82248", "84075", "84155", "84450", "84460"],
    }

    # Reverse lookup: component → list of panels it belongs to
    _component_to_panels: dict[str, list[str]] = {}

    def __init__(self):
        super().__init__()
        if not self._component_to_panels:
            for panel, components in self.PANEL_COMPONENTS.items():
                for comp in components:
                    self._component_to_panels.setdefault(comp, []).append(panel)

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        min_components = thresholds.get(
            "min_component_count",
            self.default_thresholds["min_component_count"],
        )

        same_visit_codes = set(claim.same_visit_other_cpt_codes)

        # Pattern 1: This claim IS the panel code, check if components also billed
        if claim.cpt_code in self.PANEL_COMPONENTS:
            panel_components = self.PANEL_COMPONENTS[claim.cpt_code]
            billed_components = same_visit_codes.intersection(panel_components)
            if len(billed_components) >= min_components:
                severity = self._component_severity(len(billed_components))
                return self._triggered(
                    severity=severity,
                    confidence=0.90,
                    evidence={
                        "panel_code": claim.cpt_code,
                        "billed_components": sorted(billed_components),
                        "component_count": len(billed_components),
                        "service_date": str(claim.service_date),
                        "provider_id": claim.provider_id,
                    },
                    details=(
                        f"Panel CPT {claim.cpt_code} billed along with "
                        f"{len(billed_components)} component codes "
                        f"({', '.join(sorted(billed_components)[:5])}) on same date"
                    ),
                )

        # Pattern 2: This claim is a component code, check for sibling components
        panels_for_code = self._component_to_panels.get(claim.cpt_code, [])
        for panel_code in panels_for_code:
            panel_components = set(self.PANEL_COMPONENTS[panel_code])
            # Count how many sibling components are also billed
            sibling_codes = same_visit_codes.intersection(panel_components)
            # Include this claim's CPT in the count
            total_components = len(sibling_codes) + 1  # +1 for current claim

            if total_components >= min_components:
                severity = self._component_severity(total_components)
                return self._triggered(
                    severity=severity,
                    confidence=0.85,
                    evidence={
                        "panel_code": panel_code,
                        "this_component": claim.cpt_code,
                        "sibling_components": sorted(sibling_codes),
                        "total_components_billed": total_components,
                        "service_date": str(claim.service_date),
                        "provider_id": claim.provider_id,
                    },
                    details=(
                        f"Component CPT {claim.cpt_code} billed with "
                        f"{len(sibling_codes)} sibling components of panel {panel_code} "
                        f"({', '.join(sorted(sibling_codes)[:5])}) - should use bundled code"
                    ),
                )

        # Also check enrichment bundled_codes for any other panels
        if claim.cpt_bundled_codes:
            bundled = claim.cpt_bundled_codes.get("components", []) or claim.cpt_bundled_codes.get("codes", [])
            billed_components = same_visit_codes.intersection(bundled)
            if len(billed_components) >= min_components:
                severity = self._component_severity(len(billed_components))
                return self._triggered(
                    severity=severity,
                    confidence=0.85,
                    evidence={
                        "panel_code": claim.cpt_code,
                        "billed_components": sorted(billed_components),
                        "component_count": len(billed_components),
                    },
                    details=(
                        f"CPT {claim.cpt_code} billed with {len(billed_components)} "
                        f"of its bundled component codes on the same date"
                    ),
                )

        return self._not_triggered()

    @staticmethod
    def _component_severity(count: int) -> float:
        if count >= 5:
            return 2.5
        elif count >= 4:
            return 2.0
        elif count >= 3:
            return 1.5
        else:
            return 1.0
