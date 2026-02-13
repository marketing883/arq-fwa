"""Admin user management — CRUD operations for user accounts."""

import logging
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.auth.context import RequestContext
from app.auth.passwords import hash_password
from app.auth.permissions import Permission
from app.auth.roles import Role, ROLE_PERMISSIONS
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/users", tags=["admin"])

VALID_ROLES = {r.value for r in Role if r != Role.SYSTEM}


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "viewer"
    password: str | None = None  # auto-generated if omitted


class UpdateUserRequest(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


def _user_response(user: User) -> dict:
    role_enum = Role(user.role)
    perms = ROLE_PERMISSIONS.get(role_enum, set())
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "permissions": sorted(p.value for p in perms),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _generate_temp_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(16))


@router.get("")
async def list_users(ctx: RequestContext = Depends(require(Permission.ADMIN_USERS)),
                     db: AsyncSession = Depends(get_db)):
    """List all users."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [_user_response(u) for u in result.scalars()]


@router.post("")
async def create_user(body: CreateUserRequest,
                      ctx: RequestContext = Depends(require(Permission.ADMIN_USERS)),
                      db: AsyncSession = Depends(get_db)):
    """Create a new user account."""
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {sorted(VALID_ROLES)}")

    existing = (await db.execute(
        select(User).where(User.email == body.email)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    password = body.password or _generate_temp_password()
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = User(
        email=body.email,
        password_hash=hash_password(password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    await db.flush()

    logger.info("User created: %s (%s) by %s", user.email, user.role, ctx.actor)

    resp = _user_response(user)
    if not body.password:
        resp["temp_password"] = password  # only returned on creation, never stored
    return resp


@router.put("/{user_id}")
async def update_user(user_id: int,
                      body: UpdateUserRequest,
                      ctx: RequestContext = Depends(require(Permission.ADMIN_USERS)),
                      db: AsyncSession = Depends(get_db)):
    """Update a user's role, name, or active status."""
    user = (await db.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {sorted(VALID_ROLES)}")
        user.role = body.role
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.is_active is not None:
        user.is_active = body.is_active

    logger.info("User updated: %s by %s", user.email, ctx.actor)
    return _user_response(user)


@router.post("/{user_id}/reset-password")
async def reset_password(user_id: int,
                         ctx: RequestContext = Depends(require(Permission.ADMIN_USERS)),
                         db: AsyncSession = Depends(get_db)):
    """Admin-initiated password reset — generates a temp password."""
    user = (await db.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    temp_password = _generate_temp_password()
    user.password_hash = hash_password(temp_password)

    logger.info("Password reset for %s by %s", user.email, ctx.actor)
    return {"temp_password": temp_password}
