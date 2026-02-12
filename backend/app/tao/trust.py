"""
Trust Manager — manages agent trust profiles, decay, and escalation.

Every agent has a dynamic trust score in [0.0, 1.0] that influences
the Orchestration Controller's decisions.  Trust decays with inactivity,
decreases on errors/overrides, and increases on successful actions.

Escalation Levels:
    0 (Normal)          — trust 0.7-1.0, autonomous operation
    1 (Enhanced Logging) — trust 0.5-0.7, full evidence logging
    2 (HITL Required)    — trust 0.3-0.5, every action needs human approval
    3 (Suspended)        — trust 0.0-0.3, all token requests denied
"""

import logging
import math
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tao.models import AgentTrustProfile

logger = logging.getLogger(__name__)

# Escalation thresholds
NORMAL_THRESHOLD = 0.7
ENHANCED_THRESHOLD = 0.5
HITL_THRESHOLD = 0.3

# Trust adjustment deltas
TRUST_ADJUSTMENTS = {
    "successful_action": 0.02,
    "action_error": -0.05,
    "hitl_override": -0.15,
    "policy_violation": -0.25,
    "human_endorsement": 0.15,
    "hitl_approved_success": 0.03,
}


class TrustManager:
    """Manages agent trust profiles, decay, and escalation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_profile(self, agent_id: str) -> AgentTrustProfile:
        """Get an agent's trust profile, creating one if it doesn't exist."""
        result = await self.session.execute(
            select(AgentTrustProfile).where(AgentTrustProfile.agent_id == agent_id)
        )
        profile = result.scalar_one_or_none()
        if profile:
            return profile

        profile = AgentTrustProfile(
            agent_id=agent_id,
            trust_score=0.7,
            initial_trust=0.7,
            decay_model="exponential",
            decay_rate=0.01,
            escalation_level=0,
            trust_history=[],
        )
        self.session.add(profile)
        await self.session.flush()
        logger.info("Created trust profile for agent %s (initial=0.7)", agent_id)
        return profile

    async def get_trust_score(self, agent_id: str) -> float:
        """Get the current trust score with decay applied."""
        profile = await self.get_or_create_profile(agent_id)
        return self._apply_decay(profile)

    def _apply_decay(self, profile: AgentTrustProfile) -> float:
        """Apply time-based decay to the trust score."""
        if not profile.last_successful_action:
            return profile.trust_score

        now = datetime.utcnow()
        hours_since = (now - profile.last_successful_action).total_seconds() / 3600

        if hours_since < 1.0:
            return profile.trust_score

        if profile.decay_model == "exponential":
            decayed = profile.trust_score * math.exp(-profile.decay_rate * hours_since)
        elif profile.decay_model == "linear":
            decayed = max(profile.trust_score - (profile.decay_rate * hours_since), 0.3)
        elif profile.decay_model == "step":
            decayed = profile.trust_score
            if hours_since > 168:
                decayed -= 0.30
            elif hours_since > 72:
                decayed -= 0.15
            elif hours_since > 24:
                decayed -= 0.05
        else:
            decayed = profile.trust_score

        return max(0.0, min(decayed, 1.0))

    async def record_event(
        self, agent_id: str, event_type: str, reason: str = "",
    ) -> AgentTrustProfile:
        """
        Record a trust-affecting event and update the agent's profile.

        Event types: successful_action, action_error, hitl_override,
                     policy_violation, human_endorsement, hitl_approved_success
        """
        profile = await self.get_or_create_profile(agent_id)
        delta = TRUST_ADJUSTMENTS.get(event_type, 0.0)
        old_score = profile.trust_score
        new_score = max(0.0, min(old_score + delta, 1.0))

        profile.trust_score = new_score
        profile.last_trust_update = datetime.utcnow()

        if event_type in ("successful_action", "hitl_approved_success"):
            profile.last_successful_action = datetime.utcnow()

        # Append to history
        history = list(profile.trust_history or [])
        history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "old_score": round(old_score, 4),
            "new_score": round(new_score, 4),
            "event": event_type,
            "reason": reason,
        })
        # Keep last 100 entries
        profile.trust_history = history[-100:]

        # Update escalation level
        old_level = profile.escalation_level
        new_level = self._compute_escalation_level(new_score)
        if new_level != old_level:
            profile.escalation_level = new_level
            profile.escalation_reason = (
                f"Trust {old_score:.3f} → {new_score:.3f} after {event_type}"
            )
            logger.warning(
                "Agent %s escalation: level %d → %d (trust=%.3f, event=%s)",
                agent_id, old_level, new_level, new_score, event_type,
            )

        await self.session.flush()
        return profile

    @staticmethod
    def _compute_escalation_level(trust_score: float) -> int:
        """Map trust score to escalation level."""
        if trust_score >= NORMAL_THRESHOLD:
            return 0
        elif trust_score >= ENHANCED_THRESHOLD:
            return 1
        elif trust_score >= HITL_THRESHOLD:
            return 2
        else:
            return 3

    async def reinstate(self, agent_id: str, reviewer: str) -> AgentTrustProfile:
        """
        Reinstate a suspended agent at Level 2 (HITL-required) with trust 0.4.
        Only callable by a human supervisor.
        """
        profile = await self.get_or_create_profile(agent_id)
        if profile.escalation_level < 3:
            logger.info("Agent %s not suspended (level=%d), skipping reinstate",
                        agent_id, profile.escalation_level)
            return profile

        old_score = profile.trust_score
        profile.trust_score = 0.4
        profile.escalation_level = 2
        profile.escalation_reason = f"Reinstated by {reviewer}"
        profile.last_trust_update = datetime.utcnow()

        history = list(profile.trust_history or [])
        history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "old_score": round(old_score, 4),
            "new_score": 0.4,
            "event": "human_reinstatement",
            "reason": f"Reinstated by {reviewer}",
        })
        profile.trust_history = history[-100:]

        await self.session.flush()
        logger.info("Agent %s reinstated by %s (trust=0.4, level=2)", agent_id, reviewer)
        return profile

    async def get_escalation_level(self, agent_id: str) -> int:
        """Get the current escalation level for an agent."""
        profile = await self.get_or_create_profile(agent_id)
        decayed_trust = self._apply_decay(profile)
        return self._compute_escalation_level(decayed_trust)
