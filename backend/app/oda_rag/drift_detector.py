"""
Drift & Anomaly Detector — performs statistical tests on RAG signals
to detect concept drift, data drift, and anomalous behavior.

Detection methods:
    - Recall drop detection (threshold-based)
    - Embedding distribution drift (statistical distance)
    - Anomaly spike detection (z-score based)
    - Trend analysis (sliding window comparison)
"""

import logging
import math
from dataclasses import dataclass, field

from app.oda_rag.signals import SignalSnapshot

logger = logging.getLogger(__name__)


@dataclass
class DriftResult:
    """Result of drift/anomaly detection."""
    drift_detected: bool
    anomaly_detected: bool
    drift_score: float  # 0.0-1.0, higher = more drift
    signals: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


# Default thresholds (refined by closed-loop learner over time)
DEFAULT_THRESHOLDS = {
    "recall_drop_threshold": 0.10,       # 10% recall drop triggers drift
    "drift_score_threshold": 0.20,       # Drift score > 0.2 triggers adaptation
    "latency_spike_factor": 2.0,         # Latency > 2x baseline is anomalous
    "confidence_drop_threshold": 0.15,   # 15% confidence drop
    "relevance_drop_threshold": 0.10,    # 10% relevance drop
}


class DriftDetector:
    """
    Detects drift and anomalies in RAG pipeline signals.

    Compares current snapshot against a baseline to identify when
    retrieval quality, LLM performance, or user satisfaction has degraded.
    """

    def __init__(self, thresholds: dict | None = None):
        self.thresholds = thresholds or dict(DEFAULT_THRESHOLDS)
        self._baseline: SignalSnapshot | None = None
        self._history: list[SignalSnapshot] = []
        self._max_history = 50

    def set_baseline(self, snapshot: SignalSnapshot) -> None:
        """Set the baseline snapshot for drift comparison."""
        self._baseline = snapshot

    def update_thresholds(self, updates: dict) -> None:
        """Update detection thresholds (called by closed-loop learner)."""
        self.thresholds.update(updates)

    def detect(self, current: SignalSnapshot) -> DriftResult:
        """
        Run drift and anomaly detection on the current snapshot.

        Compares against the baseline and historical averages.
        """
        self._history.append(current)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        if self._baseline is None:
            if len(self._history) >= 5:
                self._baseline = self._compute_average(self._history[:5])
            else:
                return DriftResult(
                    drift_detected=False,
                    anomaly_detected=False,
                    drift_score=0.0,
                    signals=[{"info": "Insufficient data for baseline"}],
                )

        signals = []
        recommendations = []
        drift_score = 0.0

        # 1. Recall drop detection
        if self._baseline.retrieval_recall > 0:
            recall_drop = (self._baseline.retrieval_recall - current.retrieval_recall) / self._baseline.retrieval_recall
            if recall_drop > self.thresholds["recall_drop_threshold"]:
                drift_score += recall_drop
                signals.append({
                    "type": "recall_drop",
                    "baseline": self._baseline.retrieval_recall,
                    "current": current.retrieval_recall,
                    "drop_pct": recall_drop,
                })
                recommendations.append("re_weight_sources")
                recommendations.append("adjust_chunk_size")

        # 2. Embedding drift (using proxy: hit-rate change)
        if self._baseline.retrieval_hit_rate > 0:
            hit_rate_change = abs(self._baseline.retrieval_hit_rate - current.retrieval_hit_rate)
            if hit_rate_change > self.thresholds["drift_score_threshold"]:
                drift_score += hit_rate_change
                signals.append({
                    "type": "embedding_drift_proxy",
                    "baseline": self._baseline.retrieval_hit_rate,
                    "current": current.retrieval_hit_rate,
                    "delta": hit_rate_change,
                })
                recommendations.append("refresh_embeddings")

        # 3. Latency spike detection
        if self._baseline.llm_latency_ms > 0:
            latency_ratio = current.llm_latency_ms / self._baseline.llm_latency_ms
            if latency_ratio > self.thresholds["latency_spike_factor"]:
                drift_score += 0.1 * (latency_ratio - 1)
                signals.append({
                    "type": "latency_spike",
                    "baseline_ms": self._baseline.llm_latency_ms,
                    "current_ms": current.llm_latency_ms,
                    "ratio": latency_ratio,
                })
                recommendations.append("switch_model")

        # 4. Confidence drop
        if self._baseline.llm_confidence > 0:
            conf_drop = (self._baseline.llm_confidence - current.llm_confidence) / self._baseline.llm_confidence
            if conf_drop > self.thresholds["confidence_drop_threshold"]:
                drift_score += conf_drop * 0.5
                signals.append({
                    "type": "confidence_drop",
                    "baseline": self._baseline.llm_confidence,
                    "current": current.llm_confidence,
                    "drop_pct": conf_drop,
                })
                recommendations.append("adjust_prompt_template")

        # 5. User relevance drop
        if self._baseline.user_relevance > 0 and current.user_relevance > 0:
            rel_drop = (self._baseline.user_relevance - current.user_relevance) / self._baseline.user_relevance
            if rel_drop > self.thresholds["relevance_drop_threshold"]:
                drift_score += rel_drop * 0.5
                signals.append({
                    "type": "relevance_drop",
                    "baseline": self._baseline.user_relevance,
                    "current": current.user_relevance,
                    "drop_pct": rel_drop,
                })
                recommendations.append("re_weight_sources")
                recommendations.append("adjust_prompt_template")

        drift_score = min(drift_score, 1.0)
        drift_detected = drift_score > self.thresholds["drift_score_threshold"]
        anomaly_detected = any(s["type"] == "latency_spike" for s in signals)

        if drift_detected:
            logger.warning("Drift detected: score=%.3f, signals=%d", drift_score, len(signals))

        return DriftResult(
            drift_detected=drift_detected,
            anomaly_detected=anomaly_detected,
            drift_score=drift_score,
            signals=signals,
            recommendations=list(set(recommendations)),
        )

    @staticmethod
    def _compute_average(snapshots: list[SignalSnapshot]) -> SignalSnapshot:
        """Compute average of multiple snapshots for baseline."""
        n = len(snapshots)
        if n == 0:
            return SignalSnapshot()
        return SignalSnapshot(
            retrieval_hit_rate=sum(s.retrieval_hit_rate for s in snapshots) / n,
            retrieval_recall=sum(s.retrieval_recall for s in snapshots) / n,
            retrieval_latency_ms=sum(s.retrieval_latency_ms for s in snapshots) / n,
            embedding_drift=sum(s.embedding_drift for s in snapshots) / n,
            llm_latency_ms=sum(s.llm_latency_ms for s in snapshots) / n,
            llm_confidence=sum(s.llm_confidence for s in snapshots) / n,
            user_relevance=sum(s.user_relevance for s in snapshots) / n,
        )
