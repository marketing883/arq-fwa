"""
RequestContext — the "who is asking, what can they do, where are they scoped" abstraction.

Every API request gets a RequestContext. It carries:
- user_id: who is making the request
- role: their role in the current workspace
- permissions: the resolved set of permissions for that role
- workspace_id: the workspace they're operating in (None = global)

Currently returns full admin access (the building has no locks yet).
When authentication is added, `get_request_context()` in deps.py will
extract this from a JWT, and all the permission checks + workspace
scoping will activate without changing any endpoint code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import HTTPException

from app.auth.permissions import Permission
from app.auth.roles import Role, ROLE_PERMISSIONS


@dataclass
class RequestContext:
    user_id: str = "anonymous"
    role: Role = Role.VIEWER
    permissions: set[Permission] = field(default_factory=set)
    workspace_id: int | None = None

    def has_permission(self, perm: Permission) -> bool:
        return perm in self.permissions

    def require_permission(self, perm: Permission) -> None:
        """Raise 403 if the caller lacks the given permission."""
        if not self.has_permission(perm):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions: requires {perm.value}",
            )

    def require_any(self, *perms: Permission) -> None:
        """Raise 403 if the caller lacks ALL of the given permissions."""
        if not any(self.has_permission(p) for p in perms):
            needed = ", ".join(p.value for p in perms)
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions: requires one of [{needed}]",
            )

    @property
    def actor(self) -> str:
        """Identity string for audit logging."""
        return f"{self.role.value}:{self.user_id}"
