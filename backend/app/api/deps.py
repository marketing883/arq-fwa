"""
API Dependencies — DB session, auth context, permission guards.

Authentication is now live via JWT. The `get_request_context` function:
  1. Extracts the Bearer token from the Authorization header
  2. Decodes and validates the JWT
  3. Resolves role → permissions via ROLE_PERMISSIONS
  4. Returns a properly scoped RequestContext

Auth-exempt paths (no token required):
  /api/auth/login, /api/auth/refresh, /api/health, /metrics
"""

import logging
from typing import AsyncGenerator

from fastapi import Depends, Request, HTTPException
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.auth.permissions import Permission
from app.auth.roles import Role, ROLE_PERMISSIONS
from app.auth.context import RequestContext
from app.auth.jwt import decode_access_token

logger = logging.getLogger(__name__)

# Paths that do not require authentication
AUTH_EXEMPT_PATHS = {
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/health",
    "/metrics",
}


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


# ── Request context (JWT authentication) ──────────────────────────────────────

async def get_request_context(request: Request) -> RequestContext:
    """
    Build a RequestContext for the current request by decoding the JWT.

    Auth-exempt paths get anonymous viewer context (but permission guards
    on those endpoints are already absent, so this is just a safety net).
    """
    workspace_id = _extract_workspace_id(request)
    path = request.url.path.rstrip("/")

    # Auth-exempt paths
    if path in AUTH_EXEMPT_PATHS:
        return RequestContext(
            user_id="anonymous",
            role=Role.VIEWER,
            permissions=ROLE_PERMISSIONS[Role.VIEWER],
            workspace_id=workspace_id,
        )

    # Extract Bearer token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[7:]  # strip "Bearer "
    try:
        claims = decode_access_token(token)
    except JWTError as e:
        logger.debug("JWT decode failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = claims.get("sub", "anonymous")
    role_str = claims.get("role", "viewer")

    try:
        role = Role(role_str)
    except ValueError:
        role = Role.VIEWER

    return RequestContext(
        user_id=user_id,
        role=role,
        permissions=ROLE_PERMISSIONS.get(role, set()),
        workspace_id=workspace_id,
    )


def _extract_workspace_id(request: Request) -> int | None:
    """
    Pull workspace_id from the request. Checks in order:
    1. X-Workspace-Id header
    2. workspace_id query parameter
    """
    header_val = request.headers.get("X-Workspace-Id")
    if header_val:
        try:
            return int(header_val)
        except (ValueError, TypeError):
            pass

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
    """
    async def _check(ctx: RequestContext = Depends(get_request_context)) -> RequestContext:
        for p in perms:
            ctx.require_permission(p)
        return ctx
    return _check


def require_any(*perms: Permission):
    """
    FastAPI dependency that checks the caller has AT LEAST ONE of the listed permissions.
    """
    async def _check(ctx: RequestContext = Depends(get_request_context)) -> RequestContext:
        ctx.require_any(*perms)
        return ctx
    return _check
