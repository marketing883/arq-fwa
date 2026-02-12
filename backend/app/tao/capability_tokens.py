"""
Capability Token Service — ephemeral, scoped authorization tokens for
agent actions.  Implements the principle of least privilege.

Each token permits exactly one action type, is scoped to specific resources,
has a short TTL, and is signed with HMAC-SHA256.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.tao.models import CapabilityToken

logger = logging.getLogger(__name__)

# In production, load from HSM / secrets manager
_SIGNING_KEY = b"arqai-tao-capability-token-signing-key-v1"


def _sign_token(fields: dict) -> str:
    """HMAC-SHA256 signature of canonical token fields."""
    raw = json.dumps(fields, sort_keys=True, default=str)
    return hmac.new(_SIGNING_KEY, raw.encode(), hashlib.sha256).hexdigest()


class CapabilityTokenService:
    """Manages issuance, validation, and revocation of capability tokens."""

    # Default TTL by action category
    TTL_DEFAULTS: dict[str, int] = {
        "query": 60,              # read-only queries: 60s
        "evaluate": 60,           # rule evaluation: 60s
        "calculate": 60,          # score calculation: 60s
        "create": 120,            # case creation: 120s
        "update": 120,            # status changes: 120s
        "investigate": 300,       # LLM investigation: 5min
        "chat": 300,              # chat session: 5min
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def issue(
        self,
        agent_id: str,
        action: str,
        resource_scope: dict | None = None,
        constraints: dict | None = None,
        ttl_seconds: int | None = None,
        max_uses: int = 1,
        issuer: str = "orchestration_controller",
        parent_token_id: str | None = None,
    ) -> CapabilityToken:
        """
        Issue a new capability token for an agent action.

        Args:
            agent_id: The agent being authorized
            action: Specific action permitted (e.g., "query_cases", "create_case")
            resource_scope: {resource_type, resource_ids, workspace_id}
            constraints: {max_records, max_cost_usd, allowed_fields, read_only}
            ttl_seconds: Token lifetime (defaults by action category)
            max_uses: Maximum uses before invalidation
            issuer: Who issued the token
            parent_token_id: If delegated from a broader token
        """
        if ttl_seconds is None:
            action_category = action.split("_")[0] if "_" in action else action
            ttl_seconds = self.TTL_DEFAULTS.get(action_category, 60)

        now = datetime.utcnow()
        token_id = str(uuid4())
        scope = resource_scope or {}
        cons = constraints or {}

        # Enforce delegation: child scope must be <= parent scope
        if parent_token_id:
            parent = await self._get_token(parent_token_id)
            if parent and not parent.revoked:
                # Child inherits parent constraints if not specified
                if not cons.get("read_only") and parent.constraints.get("read_only"):
                    cons["read_only"] = True
                if parent.constraints.get("max_records"):
                    child_max = cons.get("max_records", float("inf"))
                    cons["max_records"] = min(child_max, parent.constraints["max_records"])

        sign_fields = {
            "token_id": token_id,
            "issuer": issuer,
            "agent_id": agent_id,
            "action": action,
            "resource_scope": scope,
            "constraints": cons,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
            "max_uses": max_uses,
        }
        signature = _sign_token(sign_fields)

        token = CapabilityToken(
            token_id=token_id,
            issuer=issuer,
            subject_agent_id=agent_id,
            action=action,
            resource_scope=scope,
            constraints=cons,
            issued_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            max_uses=max_uses,
            uses_remaining=max_uses,
            parent_token_id=parent_token_id,
            revoked=False,
            signature=signature,
        )
        self.session.add(token)
        await self.session.flush()
        logger.info("Issued token %s for %s:%s (ttl=%ds)", token_id, agent_id, action, ttl_seconds)
        return token

    async def validate(self, token_id: str, action: str | None = None) -> tuple[bool, str]:
        """
        Validate a token. Returns (is_valid, reason).
        Decrements uses_remaining on successful validation.
        """
        token = await self._get_token(token_id)
        if not token:
            return False, "token_not_found"
        if token.revoked:
            return False, "token_revoked"
        if datetime.utcnow() > token.expires_at:
            return False, "token_expired"
        if token.uses_remaining <= 0:
            return False, "token_exhausted"
        if action and token.action != action:
            return False, f"action_mismatch: token permits '{token.action}', got '{action}'"

        # Verify signature
        sign_fields = {
            "token_id": token.token_id,
            "issuer": token.issuer,
            "agent_id": token.subject_agent_id,
            "action": token.action,
            "resource_scope": token.resource_scope,
            "constraints": token.constraints,
            "issued_at": token.issued_at.isoformat(),
            "expires_at": token.expires_at.isoformat(),
            "max_uses": token.max_uses,
        }
        expected_sig = _sign_token(sign_fields)
        if not hmac.compare_digest(token.signature, expected_sig):
            return False, "signature_invalid"

        # Decrement uses
        token.uses_remaining -= 1
        await self.session.flush()
        return True, "valid"

    async def revoke(self, token_id: str, reason: str = "manual") -> bool:
        """Revoke a token before its natural expiry."""
        token = await self._get_token(token_id)
        if not token:
            return False
        token.revoked = True
        await self.session.flush()
        logger.info("Revoked token %s: %s", token_id, reason)
        return True

    async def revoke_all_for_agent(self, agent_id: str, reason: str = "trust_suspension") -> int:
        """Revoke all active tokens for an agent (used during trust suspension)."""
        result = await self.session.execute(
            update(CapabilityToken)
            .where(
                CapabilityToken.subject_agent_id == agent_id,
                CapabilityToken.revoked == False,
                CapabilityToken.expires_at > datetime.utcnow(),
            )
            .values(revoked=True)
        )
        await self.session.flush()
        count = result.rowcount
        if count:
            logger.info("Revoked %d tokens for agent %s: %s", count, agent_id, reason)
        return count

    async def _get_token(self, token_id: str) -> CapabilityToken | None:
        result = await self.session.execute(
            select(CapabilityToken).where(CapabilityToken.token_id == token_id)
        )
        return result.scalar_one_or_none()
