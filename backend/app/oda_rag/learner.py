"""
Closed-Loop Learner — records adaptation events and their outcomes,
then refines detection thresholds and adaptation strategies over time.

The learner:
    1. Records each adaptation with context and resulting metrics
    2. After enough data, analyzes which adaptations improved outcomes
    3. Adjusts drift detection thresholds based on feedback
    4. Produces a feedback report for human review
"""

import logging
from dataclasses import dataclass, field
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.oda_rag.models import AdaptationEvent, RAGFeedback
from app.oda_rag.drift_detector import DriftDetector
from app.oda_rag.signals import SignalSnapshot

logger = logging.getLogger(__name__)


@dataclass
class AdaptationOutcome:
    """Tracks the outcome of an adaptation action."""
    event_id: str
    action_type: str
    drift_score_before: float
    metrics_before: dict
    metrics_after: dict | None = None
    feedback_score: float | None = None
    improvement: float | None = None  # positive = better


@dataclass
class LearnerReport:
    """Summary of what the learner has observed and adjusted."""
    total_adaptations: int
    successful_adaptations: int
    threshold_updates: dict
    recommendations: list[str] = field(default_factory=list)


class ClosedLoopLearner:
    """
    Persists adaptation outcomes and refines detection thresholds.

    The learner watches whether adaptations actually improved things:
    - If an adaptation improved metrics → lower the threshold to trigger it earlier
    - If an adaptation made things worse → raise the threshold or disable it
    - If feedback is consistently low → flag for human review
    """

    MIN_SAMPLES_FOR_LEARNING = 5

    def __init__(
        self,
        session: AsyncSession,
        drift_detector: DriftDetector,
        workspace_id: int | None = None,
    ):
        self.session = session
        self.drift_detector = drift_detector
        self.workspace_id = workspace_id
        self._outcomes: list[AdaptationOutcome] = []

    async def record_feedback(
        self,
        query: str,
        response_quality: float,
        relevance_score: float | None = None,
        session_id: str | None = None,
        feedback_source: str = "explicit",
    ) -> RAGFeedback:
        """Record user feedback on a RAG response."""
        fb = RAGFeedback(
            feedback_id=str(uuid4()),
            session_id=session_id,
            query=query,
            response_quality=response_quality,
            relevance_score=relevance_score,
            feedback_source=feedback_source,
            context={},
            workspace_id=self.workspace_id,
        )
        self.session.add(fb)
        await self.session.flush()
        return fb

    def record_outcome(
        self,
        event_id: str,
        action_type: str,
        drift_score_before: float,
        metrics_before: dict,
        metrics_after: dict | None = None,
        feedback_score: float | None = None,
    ) -> AdaptationOutcome:
        """Record the outcome of an adaptation action."""
        improvement = None
        if metrics_before and metrics_after:
            before_avg = sum(metrics_before.values()) / max(len(metrics_before), 1)
            after_avg = sum(metrics_after.values()) / max(len(metrics_after), 1)
            improvement = after_avg - before_avg

        outcome = AdaptationOutcome(
            event_id=event_id,
            action_type=action_type,
            drift_score_before=drift_score_before,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            feedback_score=feedback_score,
            improvement=improvement,
        )
        self._outcomes.append(outcome)
        return outcome

    def learn_and_adjust(self) -> LearnerReport:
        """
        Analyze accumulated outcomes and adjust drift detector thresholds.

        Called periodically or after a batch of interactions.
        """
        if len(self._outcomes) < self.MIN_SAMPLES_FOR_LEARNING:
            return LearnerReport(
                total_adaptations=len(self._outcomes),
                successful_adaptations=0,
                threshold_updates={},
                recommendations=["Insufficient data for learning "
                                  f"({len(self._outcomes)}/{self.MIN_SAMPLES_FOR_LEARNING})"],
            )

        # Count successes and failures by action type
        by_action: dict[str, list[AdaptationOutcome]] = {}
        for outcome in self._outcomes:
            by_action.setdefault(outcome.action_type, []).append(outcome)

        successful = 0
        threshold_updates = {}
        recommendations = []

        for action_type, outcomes in by_action.items():
            positive = [o for o in outcomes if o.improvement is not None and o.improvement > 0]
            negative = [o for o in outcomes if o.improvement is not None and o.improvement < 0]
            successful += len(positive)

            success_rate = len(positive) / max(len(outcomes), 1)

            if success_rate > 0.7:
                # This adaptation works well → lower threshold to trigger earlier
                self._adjust_threshold_for_action(action_type, direction="lower")
                threshold_updates[action_type] = "lowered (effective)"
                recommendations.append(
                    f"{action_type}: {success_rate:.0%} success rate — thresholds lowered"
                )
            elif success_rate < 0.3 and len(outcomes) >= 3:
                # This adaptation is counterproductive → raise threshold
                self._adjust_threshold_for_action(action_type, direction="raise")
                threshold_updates[action_type] = "raised (ineffective)"
                recommendations.append(
                    f"{action_type}: {success_rate:.0%} success rate — thresholds raised"
                )

        # Check average feedback
        feedback_outcomes = [o for o in self._outcomes if o.feedback_score is not None]
        if feedback_outcomes:
            avg_feedback = sum(o.feedback_score for o in feedback_outcomes) / len(feedback_outcomes)
            if avg_feedback < 0.4:
                recommendations.append(
                    f"Average feedback score {avg_feedback:.2f} — flag for human review"
                )

        return LearnerReport(
            total_adaptations=len(self._outcomes),
            successful_adaptations=successful,
            threshold_updates=threshold_updates,
            recommendations=recommendations,
        )

    def _adjust_threshold_for_action(self, action_type: str, direction: str) -> None:
        """
        Adjust drift detector thresholds based on action effectiveness.

        Maps action types to the relevant threshold and adjusts by a small delta.
        """
        action_to_threshold = {
            "re_weight_sources": "recall_drop_threshold",
            "adjust_chunk_size": "recall_drop_threshold",
            "refresh_embeddings": "drift_score_threshold",
            "switch_prompt_model": "confidence_drop_threshold",
        }

        threshold_key = action_to_threshold.get(action_type)
        if not threshold_key:
            return

        delta = -0.02 if direction == "lower" else 0.02
        current = self.drift_detector.thresholds.get(threshold_key, 0.1)
        new_value = max(0.02, min(current + delta, 0.5))

        self.drift_detector.update_thresholds({threshold_key: new_value})
        logger.info("Learner adjusted %s: %.3f → %.3f (%s)",
                     threshold_key, current, new_value, direction)

    async def get_feedback_stats(self) -> dict:
        """Get aggregate feedback statistics."""
        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.avg(RAGFeedback.response_quality).label("avg_quality"),
                func.avg(RAGFeedback.relevance_score).label("avg_relevance"),
            ).select_from(RAGFeedback)
        )
        row = result.first()
        return {
            "total_feedback": row.total if row else 0,
            "avg_quality": float(row.avg_quality) if row and row.avg_quality else None,
            "avg_relevance": float(row.avg_relevance) if row and row.avg_relevance else None,
        }
