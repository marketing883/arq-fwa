"""
ODA-RAG — Observability-Driven Adaptive Retrieval and Prompt Reconfiguration
(ArqSight).

Patent-pending methodology for monitoring RAG pipeline signals, detecting
drift and anomalies, and dynamically adapting retrieval parameters.

Closed-loop architecture:
    1. Monitor  — continuously ingest observability metrics and user feedback
    2. Detect   — statistical tests / ML for drift and anomaly detection
    3. Decide   — rule engine selects adaptation actions
    4. Adapt    — apply parameter updates (re-weight, chunk, embed, prompt/model)
    5. Generate — run RAG pipeline with updated parameters
    6. Feedback — collect user ratings / implicit signals
    7. Iterate  — feedback refines future thresholds

Components:
    models              — SQLAlchemy models (signals, adaptation events)
    signals             — Signal collection and monitoring (ArqSight)
    drift_detector      — Drift and anomaly detection
    adaptive_controller — Decision engine for parameter updates
    parameter_updaters  — Source re-weighting, chunk size, embedding refresh,
                          prompt/model selection
    learner             — Closed-loop learner (evidence store + threshold refinement)
"""

from app.oda_rag.signals import RAGSignalCollector, SignalType
from app.oda_rag.drift_detector import DriftDetector, DriftResult
from app.oda_rag.adaptive_controller import AdaptiveController, AdaptationAction
from app.oda_rag.parameter_updaters import ParameterUpdaters, RAGParameters
from app.oda_rag.learner import ClosedLoopLearner

__all__ = [
    "RAGSignalCollector", "SignalType",
    "DriftDetector", "DriftResult",
    "AdaptiveController", "AdaptationAction",
    "ParameterUpdaters", "RAGParameters",
    "ClosedLoopLearner",
]
