"""
Role definitions — which bundles of permissions make up each role.

Roles are hierarchical: each higher role includes all permissions
of the roles below it, plus additional ones.

    VIEWER < ANALYST < INVESTIGATOR < COMPLIANCE < ADMIN

There is also a SYSTEM role for internal services (worker, pipeline)
that has specific operational permissions without user-management.
"""

from enum import Enum
from app.auth.permissions import Permission


class Role(str, Enum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    INVESTIGATOR = "investigator"
    COMPLIANCE = "compliance"
    ADMIN = "admin"
    SYSTEM = "system"


# ── Viewer: read-only dashboard, claims list, case list ──
_VIEWER_PERMS: set[Permission] = {
    Permission.DASHBOARD_VIEW,
    Permission.CLAIMS_READ,
    Permission.CASES_READ,
    Permission.RULES_READ,
    Permission.PIPELINE_STATUS,
    Permission.WORKSPACE_READ,
    Permission.SCORING_READ,
    Permission.PROVIDERS_READ,
    Permission.AGENT_CHAT,
}

# ── Analyst: viewer + can run pipeline, process claims ──
_ANALYST_PERMS: set[Permission] = {
    *_VIEWER_PERMS,
    Permission.CLAIMS_PROCESS,
    Permission.PIPELINE_RUN,
    Permission.AGENT_INVESTIGATE,
}

# ── Investigator: analyst + case management, financial view ──
_INVESTIGATOR_PERMS: set[Permission] = {
    *_ANALYST_PERMS,
    Permission.CASES_MANAGE,
    Permission.CASES_INVESTIGATE,
    Permission.FINANCIAL_VIEW,
}

# ── Compliance: investigator + audit, financial export ──
_COMPLIANCE_PERMS: set[Permission] = {
    *_INVESTIGATOR_PERMS,
    Permission.AUDIT_READ,
    Permission.FINANCIAL_EXPORT,
}

# ── Admin: everything ──
_ADMIN_PERMS: set[Permission] = {p for p in Permission}

# ── System: operational permissions for internal services ──
_SYSTEM_PERMS: set[Permission] = {
    Permission.CLAIMS_READ,
    Permission.CLAIMS_PROCESS,
    Permission.CASES_READ,
    Permission.CASES_MANAGE,
    Permission.RULES_READ,
    Permission.PIPELINE_RUN,
    Permission.PIPELINE_STATUS,
    Permission.WORKSPACE_READ,
    Permission.SCORING_READ,
    Permission.PROVIDERS_READ,
    Permission.FINANCIAL_VIEW,
    Permission.AUDIT_READ,
}


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.VIEWER: _VIEWER_PERMS,
    Role.ANALYST: _ANALYST_PERMS,
    Role.INVESTIGATOR: _INVESTIGATOR_PERMS,
    Role.COMPLIANCE: _COMPLIANCE_PERMS,
    Role.ADMIN: _ADMIN_PERMS,
    Role.SYSTEM: _SYSTEM_PERMS,
}
