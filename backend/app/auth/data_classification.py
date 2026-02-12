"""
Data sensitivity classification — the CAPC policy graph foundation.

Classifies every data field and tool in the system by sensitivity level.
This feeds into the agent's permission-aware tool execution: before the
agent returns financial data, PII, or investigation details, it checks
whether the caller's permissions cover that sensitivity tier.

Sensitivity Tiers:
    PUBLIC      → aggregate counts, risk levels, status (visible to all roles)
    INTERNAL    → case details, rule triggers, provider info (analyst+)
    SENSITIVE   → dollar amounts on individual claims, PII fields (investigator+)
    RESTRICTED  → aggregate financial summaries, fraud estimates, recovery (compliance+)
    CLASSIFIED  → raw audit trail, system config, encryption keys (admin only)

This maps directly to CAPC Section 3.2 (Policy Graph) — each data element
carries a sensitivity tag that the runtime checks before disclosure.
"""

from enum import IntEnum

from app.auth.permissions import Permission


class Sensitivity(IntEnum):
    """Data sensitivity tiers, ordered from least to most sensitive."""
    PUBLIC = 0       # Counts, statuses, risk levels
    INTERNAL = 1     # Case details, rule info, provider names
    SENSITIVE = 2    # Dollar amounts on claims, member IDs
    RESTRICTED = 3   # Aggregate financial summaries, fraud estimates
    CLASSIFIED = 4   # Audit trail, system configuration


# Which permissions gate each sensitivity tier
TIER_REQUIRED_PERMISSIONS: dict[Sensitivity, set[Permission]] = {
    Sensitivity.PUBLIC: set(),                                  # no gate
    Sensitivity.INTERNAL: {Permission.CASES_READ},              # analyst+
    Sensitivity.SENSITIVE: {Permission.FINANCIAL_VIEW},         # investigator+
    Sensitivity.RESTRICTED: {Permission.FINANCIAL_VIEW},        # investigator+
    Sensitivity.CLASSIFIED: {Permission.AUDIT_READ},            # compliance+
}


# Classification of agent tools by sensitivity tier
TOOL_SENSITIVITY: dict[str, Sensitivity] = {
    "query_pipeline_stats": Sensitivity.PUBLIC,
    "query_cases": Sensitivity.INTERNAL,
    "query_case_detail": Sensitivity.INTERNAL,
    "query_rules": Sensitivity.INTERNAL,
    "query_provider": Sensitivity.INTERNAL,
    "query_financial_summary": Sensitivity.RESTRICTED,
}


# Classification of data context sections by sensitivity
CONTEXT_SENSITIVITY: dict[str, Sensitivity] = {
    "pipeline-stats": Sensitivity.PUBLIC,          # counts only
    "top-cases": Sensitivity.INTERNAL,             # case IDs + risk levels
    "rule-stats": Sensitivity.INTERNAL,            # rule trigger counts
    "financial-summary": Sensitivity.RESTRICTED,   # dollar amounts
    "case-detail": Sensitivity.INTERNAL,           # case context
    "claim-amounts": Sensitivity.SENSITIVE,        # individual claim $
    "member-pii": Sensitivity.SENSITIVE,           # member names, DOB
    "audit-trail": Sensitivity.CLASSIFIED,         # full audit log
}


def max_sensitivity_for_permissions(permissions: set[Permission]) -> Sensitivity:
    """Return the highest sensitivity tier the given permissions can access."""
    max_tier = Sensitivity.PUBLIC
    for tier, required in TIER_REQUIRED_PERMISSIONS.items():
        if not required or required.issubset(permissions):
            if tier > max_tier:
                max_tier = tier
    return max_tier


def can_access_tool(permissions: set[Permission], tool_name: str) -> bool:
    """Check if the given permissions allow access to a specific agent tool."""
    tier = TOOL_SENSITIVITY.get(tool_name, Sensitivity.CLASSIFIED)
    required = TIER_REQUIRED_PERMISSIONS.get(tier, set())
    if not required:
        return True
    return required.issubset(permissions)


def redact_financial_for_tier(data: dict, max_tier: Sensitivity) -> dict:
    """
    Redact financial fields from a data dict based on the caller's max tier.

    - PUBLIC: strip all dollar amounts, show only counts
    - INTERNAL: strip aggregate financial summaries, show case counts
    - SENSITIVE: show individual claim amounts, strip aggregate fraud estimates
    - RESTRICTED+: full access
    """
    if max_tier >= Sensitivity.RESTRICTED:
        return data  # full access

    redacted = dict(data)

    if max_tier < Sensitivity.SENSITIVE:
        # Strip all dollar amounts
        for key in list(redacted.keys()):
            if any(term in key.lower() for term in ["amount", "billed", "paid", "fraud", "recover", "prevent"]):
                redacted[key] = "[RESTRICTED]"
        # Strip breakdowns that contain financial data
        for key in ("by_risk_level", "by_status"):
            if key in redacted:
                for sub_key, sub_val in redacted[key].items():
                    if isinstance(sub_val, dict):
                        for field in list(sub_val.keys()):
                            if field != "cases":
                                sub_val[field] = "[RESTRICTED]"
    elif max_tier < Sensitivity.RESTRICTED:
        # Show individual amounts but strip aggregate fraud estimates
        for key in ("total_estimated_fraud", "total_recovered", "amount_prevented_billed_minus_paid"):
            if key in redacted:
                redacted[key] = "[REQUIRES COMPLIANCE ACCESS]"
        for key in ("by_risk_level", "by_status"):
            if key in redacted:
                for sub_key, sub_val in redacted[key].items():
                    if isinstance(sub_val, dict):
                        for field in ("estimated_fraud", "recovered"):
                            if field in sub_val:
                                sub_val[field] = "[REQUIRES COMPLIANCE ACCESS]"

    return redacted
