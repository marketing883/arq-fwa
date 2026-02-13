"""Authentication API — login, refresh, logout, profile."""

import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.api.deps import get_db, get_request_context
from app.auth.context import RequestContext
from app.auth.jwt import create_access_token, create_refresh_token
from app.auth.passwords import verify_password, hash_password
from app.auth.roles import Role, ROLE_PERMISSIONS
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_TOKEN_TTL = settings.refresh_token_expire_days * 86400  # seconds


# ── Request / Response schemas ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = settings.access_token_expire_minutes * 60
    user: dict


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


def _user_to_dict(user: User) -> dict:
    role_enum = Role(user.role)
    perms = ROLE_PERMISSIONS.get(role_enum, set())
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "permissions": sorted(p.value for p in perms),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate with email + password, receive JWT access token + refresh token."""
    user = (await db.execute(
        select(User).where(User.email == body.email)
    )).scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = create_refresh_token()

    # Store refresh token in Redis
    r = await _get_redis()
    await r.setex(f"refresh:{refresh_token}", REFRESH_TOKEN_TTL, str(user.id))
    await r.aclose()

    logger.info("Login: %s (%s)", user.email, user.role)

    return TokenResponse(
        access_token=access_token,
        user=_user_to_dict(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    r = await _get_redis()
    user_id_str = await r.get(f"refresh:{refresh_token}")
    if not user_id_str:
        await r.aclose()
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = (await db.execute(
        select(User).where(User.id == int(user_id_str))
    )).scalar_one_or_none()
    if not user or not user.is_active:
        await r.aclose()
        raise HTTPException(status_code=401, detail="User not found or disabled")

    # Rotate: delete old, issue new
    await r.delete(f"refresh:{refresh_token}")
    new_refresh = create_refresh_token()
    await r.setex(f"refresh:{new_refresh}", REFRESH_TOKEN_TTL, str(user.id))
    await r.aclose()

    access_token = create_access_token(user.id, user.email, user.role)

    return TokenResponse(
        access_token=access_token,
        user=_user_to_dict(user),
    )


@router.post("/logout")
async def logout(refresh_token: str | None = None):
    """Revoke refresh token."""
    if refresh_token:
        r = await _get_redis()
        await r.delete(f"refresh:{refresh_token}")
        await r.aclose()
    return {"ok": True}


@router.get("/me")
async def me(ctx: RequestContext = Depends(get_request_context),
             db: AsyncSession = Depends(get_db)):
    """Return current authenticated user profile."""
    if ctx.user_id == "anonymous":
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = (await db.execute(
        select(User).where(User.id == int(ctx.user_id))
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return _user_to_dict(user)


@router.put("/me/password")
async def change_password(body: ChangePasswordRequest,
                          ctx: RequestContext = Depends(get_request_context),
                          db: AsyncSession = Depends(get_db)):
    """Change own password (requires current password)."""
    if ctx.user_id == "anonymous":
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = (await db.execute(
        select(User).where(User.id == int(ctx.user_id))
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user.password_hash = hash_password(body.new_password)
    return {"ok": True}
