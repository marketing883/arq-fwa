"""
Permission constants — the exhaustive list of actions in the system.

Each permission follows the pattern `resource:action`. This is the
canonical definition of "what doors exist in the building."

When authentication is added later, JWTs will carry a role claim,
which maps to a set of these permissions via ROLE_PERMISSIONS.
"""

from enum import Enum


class Permission(str, Enum):
    # ── Claims ──
    CLAIMS_READ = "claims:read"
    CLAIMS_PROCESS = "claims:process"           # batch processing, scoring

    # ── Cases ──
    CASES_READ = "cases:read"
    CASES_MANAGE = "cases:manage"               # status changes, assignments, notes
    CASES_INVESTIGATE = "cases:investigate"      # AI-powered investigation

    # ── Rules ──
    RULES_READ = "rules:read"
    RULES_CONFIGURE = "rules:configure"         # change weights, thresholds, enable/disable

    # ── Financial ──
    FINANCIAL_VIEW = "financial:view"            # see amounts, savings, fraud estimates
    FINANCIAL_EXPORT = "financial:export"        # export financial reports

    # ── Pipeline ──
    PIPELINE_RUN = "pipeline:run"               # trigger pipeline execution
    PIPELINE_STATUS = "pipeline:status"          # view pipeline status and history

    # ── Dashboard ──
    DASHBOARD_VIEW = "dashboard:view"            # overview, trends, top providers

    # ── Workspaces ──
    WORKSPACE_READ = "workspace:read"
    WORKSPACE_MANAGE = "workspace:manage"        # create, archive
    WORKSPACE_UPLOAD = "workspace:upload"         # CSV data ingestion

    # ── Audit ──
    AUDIT_READ = "audit:read"

    # ── Agent / Chat ──
    AGENT_CHAT = "agent:chat"
    AGENT_INVESTIGATE = "agent:investigate"

    # ── Providers ──
    PROVIDERS_READ = "providers:read"

    # ── Scoring ──
    SCORING_READ = "scoring:read"

    # ── Admin ──
    ADMIN_USERS = "admin:users"                  # manage users and role assignments
    ADMIN_SYSTEM = "admin:system"                # system-level operations
