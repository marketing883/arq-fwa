"""
Adaptive Controller — the decision-making brain of the ODA-RAG system.

Receives drift/anomaly detection results and selects which adaptation
actions to apply.  Can operate as a rule engine or ML model.

Actions:
    - re_weight_sources     → adjust source weights in retrieval
    - adjust_chunk_size     → change document segmentation granularity
    - refresh_embeddings    → trigger re-indexing of vector store
    - switch_prompt_model   → change prompt template or LLM model
"""

import logging
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.oda_rag.drift_detector import DriftResult
from app.oda_rag.models import AdaptationEvent
from app.oda_rag.parameter_updaters import RAGParameters

logger = logging.getLogger(__name__)


class AdaptationAction(str, Enum):
    RE_WEIGHT_SOURCES = "re_weight_sources"
    ADJUST_CHUNK_SIZE = "adjust_chunk_size"
    REFRESH_EMBEDDINGS = "refresh_embeddings"
    SWITCH_PROMPT_MODEL = "switch_prompt_model"
    NO_ACTION = "no_action"


@dataclass
class AdaptationDecision:
    """The controller's decision on what to adapt."""
    actions: list[AdaptationAction]
    reason: str
    drift_score: float
    trigger_signals: list[dict]


class AdaptiveController:
    """
    Policy-driven decision engine for RAG parameter adaptation.

    Uses a rule engine (upgradeable to ML model) to select which
    corrective actions to apply based on detected drift/anomalies.
    """

    # Cost ordering: cheapest adaptations first
    ACTION_COST = {
        AdaptationAction.RE_WEIGHT_SOURCES: 1,      # instant, in-memory
        AdaptationAction.ADJUST_CHUNK_SIZE: 2,       # affects future queries
        AdaptationAction.SWITCH_PROMPT_MODEL: 3,     # may need model load
        AdaptationAction.REFRESH_EMBEDDINGS: 10,     # expensive: re-index
    }

    def __init__(
        self,
        session: AsyncSession,
        workspace_id: int | None = None,
        cost_sensitive: bool = True,
    ):
        self.session = session
        self.workspace_id = workspace_id
        self.cost_sensitive = cost_sensitive

    def decide(self, drift_result: DriftResult) -> AdaptationDecision:
        """
        Decide which adaptation actions to take based on drift detection.

        Rules:
            1. If no drift → no action
            2. Map drift recommendations to actions
            3. If cost_sensitive, filter out expensive actions for minor drift
            4. Order by cost (cheapest first)
        """
        if not drift_result.drift_detected and not drift_result.anomaly_detected:
            return AdaptationDecision(
                actions=[AdaptationAction.NO_ACTION],
                reason="No drift or anomaly detected",
                drift_score=drift_result.drift_score,
                trigger_signals=drift_result.signals,
            )

        # Map recommendations to actions
        action_map = {
            "re_weight_sources": AdaptationAction.RE_WEIGHT_SOURCES,
            "adjust_chunk_size": AdaptationAction.ADJUST_CHUNK_SIZE,
            "refresh_embeddings": AdaptationAction.REFRESH_EMBEDDINGS,
            "switch_model": AdaptationAction.SWITCH_PROMPT_MODEL,
            "adjust_prompt_template": AdaptationAction.SWITCH_PROMPT_MODEL,
        }

        actions = []
        for rec in drift_result.recommendations:
            action = action_map.get(rec)
            if action and action not in actions:
                actions.append(action)

        # Cost-sensitive filtering: skip expensive actions for minor drift
        if self.cost_sensitive and drift_result.drift_score < 0.4:
            actions = [a for a in actions
                       if self.ACTION_COST.get(a, 0) <= 3]

        # Sort by cost
        actions.sort(key=lambda a: self.ACTION_COST.get(a, 99))

        if not actions:
            actions = [AdaptationAction.RE_WEIGHT_SOURCES]

        reasons = []
        for signal in drift_result.signals:
            reasons.append(f"{signal['type']}: {signal.get('current', 'N/A')}")

        return AdaptationDecision(
            actions=actions,
            reason=f"Drift score {drift_result.drift_score:.3f}: {'; '.join(reasons)}",
            drift_score=drift_result.drift_score,
            trigger_signals=drift_result.signals,
        )

    async def apply_and_record(
        self,
        decision: AdaptationDecision,
        current_params: RAGParameters,
        new_params: RAGParameters,
    ) -> list[AdaptationEvent]:
        """Record the adaptation actions in the database."""
        events = []
        for action in decision.actions:
            if action == AdaptationAction.NO_ACTION:
                continue
            event = AdaptationEvent(
                event_id=str(uuid4()),
                trigger_signal_ids=[s.get("type", "") for s in decision.trigger_signals],
                drift_score=decision.drift_score,
                action_type=action.value,
                parameters_before=current_params.to_dict(),
                parameters_after=new_params.to_dict(),
                reason=decision.reason,
                workspace_id=self.workspace_id,
            )
            self.session.add(event)
            events.append(event)

        if events:
            await self.session.flush()
            logger.info("Recorded %d adaptation events (drift=%.3f)",
                        len(events), decision.drift_score)
        return events
