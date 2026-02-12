"""
API Dependencies — DB session, auth context, permission guards.

The `get_request_context` function is the single integration point for
authentication. Right now it returns admin-level access for every request.

When JWT auth is added later, this ONE function changes to:
  1. Extract token from Authorization header
  2. Validate and decode JWT
  3. Load user role + workspace from token claims
  4. Return a properly scoped RequestContext

Every endpoint already declares what permissions it needs via `require()`,
so flipping auth on is a single-function change — no endpoint rewrites.
"""

from typing import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.auth.permissions import Permission
from app.auth.roles import Role, ROLE_PERMISSIONS
from app.auth.context import RequestContext


# ── Database session ─────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a DB session per request, commit on success, rollback on error."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Request context (auth integration point) ─────────────────────────────────

async def get_request_context(request: Request) -> RequestContext:
    """
    Build a RequestContext for the current request.

    Currently: returns admin access (no auth enforcement).

    When auth is implemented, this will:
      1. Read Authorization header → decode JWT
      2. Look up user_id, role, workspace_id from claims
      3. Resolve role → permissions via ROLE_PERMISSIONS
      4. Return scoped RequestContext

    Workspace can also come from:
      - JWT claim (primary workspace)
      - X-Workspace-Id header (override within allowed workspaces)
      - Query parameter (fallback)
    """
    # TODO: Replace with JWT extraction
    workspace_id = _extract_workspace_id(request)

    return RequestContext(
        user_id="system",
        role=Role.ADMIN,
        permissions=ROLE_PERMISSIONS[Role.ADMIN],
        workspace_id=workspace_id,
    )


def _extract_workspace_id(request: Request) -> int | None:
    """
    Pull workspace_id from the request. Checks in order:
    1. X-Workspace-Id header
    2. workspace_id query parameter

    When auth is added, this will also validate that the user
    has access to the requested workspace.
    """
    # Header takes priority
    header_val = request.headers.get("X-Workspace-Id")
    if header_val:
        try:
            return int(header_val)
        except (ValueError, TypeError):
            pass

    # Fall back to query param
    param_val = request.query_params.get("workspace_id")
    if param_val:
        try:
            return int(param_val)
        except (ValueError, TypeError):
            pass

    return None


# ── Permission guards ────────────────────────────────────────────────────────

def require(*perms: Permission):
    """
    FastAPI dependency that checks the caller has ALL listed permissions.

    Usage:
        @router.get("/claims")
        async def list_claims(ctx: RequestContext = Depends(require(Permission.CLAIMS_READ))):
            ...

    This is the "door frame" — it declares what permission each endpoint
    needs. The actual enforcement happens in get_request_context once
    auth is wired in. Right now all requests pass because everyone is admin.
    """
    async def _check(ctx: RequestContext = Depends(get_request_context)) -> RequestContext:
        for p in perms:
            ctx.require_permission(p)
        return ctx
    return _check


def require_any(*perms: Permission):
    """
    FastAPI dependency that checks the caller has AT LEAST ONE of the listed permissions.

    Usage:
        @router.get("/cases/{id}")
        async def get_case(ctx: RequestContext = Depends(require_any(
            Permission.CASES_READ, Permission.CASES_MANAGE
        ))):
            ...
    """
    async def _check(ctx: RequestContext = Depends(get_request_context)) -> RequestContext:
        ctx.require_any(*perms)
        return ctx
    return _check
