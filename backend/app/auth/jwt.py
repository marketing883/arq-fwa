"""JWT token creation and validation."""

import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"


def create_access_token(user_id: int, email: str, role: str) -> str:
    """Create a short-lived access token (30 min)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_refresh_token() -> str:
    """Create an opaque refresh token (stored in Redis)."""
    return secrets.token_urlsafe(48)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token. Raises JWTError on failure."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload
