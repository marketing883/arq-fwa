"""
RAG Signal Collector (ArqSight) — continuously ingests observability metrics
from the RAG pipeline.

Signal categories:
    - Retrieval: hit_rate, recall, precision, latency
    - Vector: embedding_drift, cluster_shift
    - LLM: response_latency, token_count, confidence
    - User: relevance_rating, satisfaction
    - Cost: query_cost, embedding_cost
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.oda_rag.models import RAGSignal

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    # Retrieval layer
    RETRIEVAL_HIT_RATE = "retrieval_hit_rate"
    RETRIEVAL_RECALL = "retrieval_recall"
    RETRIEVAL_LATENCY = "retrieval_latency"

    # Vector index
    EMBEDDING_DRIFT = "embedding_drift"
    CLUSTER_SHIFT = "cluster_shift"

    # LLM response
    LLM_LATENCY = "llm_latency"
    LLM_TOKEN_COUNT = "llm_token_count"
    LLM_CONFIDENCE = "llm_confidence"

    # User feedback (ArqPulse)
    USER_RELEVANCE = "user_relevance"
    USER_SATISFACTION = "user_satisfaction"

    # Cost
    QUERY_COST = "query_cost"
    EMBEDDING_COST = "embedding_cost"


@dataclass
class SignalSnapshot:
    """A point-in-time snapshot of all RAG signals."""
    retrieval_hit_rate: float = 0.0
    retrieval_recall: float = 0.0
    retrieval_latency_ms: float = 0.0
    embedding_drift: float = 0.0
    llm_latency_ms: float = 0.0
    llm_confidence: float = 0.0
    user_relevance: float = 0.0
    query_count: int = 0
    timestamp: float = field(default_factory=time.time)


class RAGSignalCollector:
    """
    Collects and stores RAG pipeline observability metrics.

    Maintains a rolling window of recent signals for drift detection.
    """

    def __init__(self, session: AsyncSession, workspace_id: int | None = None):
        self.session = session
        self.workspace_id = workspace_id
        self._recent_signals: list[dict] = []
        self._max_recent = 100

    async def record_signal(
        self,
        signal_type: SignalType,
        metric_name: str,
        value: float,
        context: dict | None = None,
    ) -> RAGSignal:
        """Record a single RAG signal metric."""
        signal = RAGSignal(
            signal_id=str(uuid4()),
            signal_type=signal_type.value,
            metric_name=metric_name,
            metric_value=value,
            context=context or {},
            workspace_id=self.workspace_id,
        )
        self.session.add(signal)
        await self.session.flush()

        # Track in rolling window
        self._recent_signals.append({
            "signal_id": signal.signal_id,
            "type": signal_type.value,
            "metric": metric_name,
            "value": value,
            "timestamp": time.time(),
        })
        if len(self._recent_signals) > self._max_recent:
            self._recent_signals = self._recent_signals[-self._max_recent:]

        return signal

    async def record_retrieval_metrics(
        self,
        hit_rate: float,
        recall: float,
        latency_ms: float,
        context: dict | None = None,
    ) -> list[RAGSignal]:
        """Record a batch of retrieval layer metrics."""
        signals = []
        for signal_type, metric, value in [
            (SignalType.RETRIEVAL_HIT_RATE, "hit_rate", hit_rate),
            (SignalType.RETRIEVAL_RECALL, "recall", recall),
            (SignalType.RETRIEVAL_LATENCY, "latency_ms", latency_ms),
        ]:
            s = await self.record_signal(signal_type, metric, value, context)
            signals.append(s)
        return signals

    async def record_llm_metrics(
        self,
        latency_ms: float,
        token_count: int,
        confidence: float,
        model: str = "",
    ) -> list[RAGSignal]:
        """Record LLM response metrics."""
        ctx = {"model": model}
        signals = []
        for signal_type, metric, value in [
            (SignalType.LLM_LATENCY, "latency_ms", latency_ms),
            (SignalType.LLM_TOKEN_COUNT, "token_count", float(token_count)),
            (SignalType.LLM_CONFIDENCE, "confidence", confidence),
        ]:
            s = await self.record_signal(signal_type, metric, value, ctx)
            signals.append(s)
        return signals

    async def record_user_feedback(
        self,
        relevance: float,
        satisfaction: float | None = None,
        session_id: str | None = None,
    ) -> list[RAGSignal]:
        """Record user feedback signals (ArqPulse)."""
        ctx = {"session_id": session_id} if session_id else {}
        signals = []
        s = await self.record_signal(SignalType.USER_RELEVANCE, "relevance", relevance, ctx)
        signals.append(s)
        if satisfaction is not None:
            s = await self.record_signal(SignalType.USER_SATISFACTION, "satisfaction", satisfaction, ctx)
            signals.append(s)
        return signals

    def get_recent_snapshot(self) -> SignalSnapshot:
        """Get a snapshot of recent signal averages."""
        if not self._recent_signals:
            return SignalSnapshot()

        by_metric: dict[str, list[float]] = {}
        for s in self._recent_signals:
            key = s["metric"]
            by_metric.setdefault(key, []).append(s["value"])

        def avg(key: str) -> float:
            vals = by_metric.get(key, [])
            return sum(vals) / len(vals) if vals else 0.0

        return SignalSnapshot(
            retrieval_hit_rate=avg("hit_rate"),
            retrieval_recall=avg("recall"),
            retrieval_latency_ms=avg("latency_ms"),
            llm_latency_ms=avg("latency_ms"),
            llm_confidence=avg("confidence"),
            user_relevance=avg("relevance"),
            query_count=len(self._recent_signals),
        )
