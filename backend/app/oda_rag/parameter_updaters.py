"""
Parameter Updaters — four adaptation modules that modify RAG pipeline
parameters based on the Adaptive Controller's decisions.

Modules:
    1. Source Re-weighting    — adjust source weights (capped by policy)
    2. Chunk Size Adjustment  — change document segmentation granularity
    3. Embedding Refresh      — trigger re-indexing of vector store
    4. Prompt & Model Selector — switch prompt templates or LLM models
"""

import logging
from dataclasses import dataclass, field
from enum import Enum

from app.oda_rag.drift_detector import DriftResult

logger = logging.getLogger(__name__)


@dataclass
class RAGParameters:
    """Current RAG pipeline parameters that can be adapted."""

    # Source weights (keyed by source name)
    source_weights: dict[str, float] = field(default_factory=lambda: {
        "claims_db": 0.4,
        "rules_db": 0.3,
        "cases_db": 0.2,
        "knowledge_base": 0.1,
    })

    # Chunk configuration
    chunk_size: int = 512                   # tokens per chunk
    chunk_overlap: int = 50                 # overlap between chunks

    # Embedding configuration
    embedding_model: str = "local"          # embedding model identifier
    embedding_refresh_pending: bool = False  # flag for async re-indexing

    # Retrieval parameters
    top_k: int = 5                          # number of chunks to retrieve
    rerank_threshold: float = 0.5           # minimum relevance for re-ranking

    # Prompt / model selection
    prompt_template: str = "default"        # active prompt template
    llm_model: str = "qwen3:8b"            # active LLM model
    temperature: float = 0.3               # LLM temperature

    # Policy constraints (from ArqGuard)
    max_source_weight: float = 0.6          # no single source > 60%
    min_chunk_size: int = 128
    max_chunk_size: int = 2048

    def to_dict(self) -> dict:
        return {
            "source_weights": self.source_weights,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "embedding_model": self.embedding_model,
            "top_k": self.top_k,
            "rerank_threshold": self.rerank_threshold,
            "prompt_template": self.prompt_template,
            "llm_model": self.llm_model,
            "temperature": self.temperature,
        }

    def copy(self) -> "RAGParameters":
        """Create a deep copy of the parameters."""
        return RAGParameters(
            source_weights=dict(self.source_weights),
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            embedding_model=self.embedding_model,
            embedding_refresh_pending=self.embedding_refresh_pending,
            top_k=self.top_k,
            rerank_threshold=self.rerank_threshold,
            prompt_template=self.prompt_template,
            llm_model=self.llm_model,
            temperature=self.temperature,
            max_source_weight=self.max_source_weight,
            min_chunk_size=self.min_chunk_size,
            max_chunk_size=self.max_chunk_size,
        )


# Available prompt templates
PROMPT_TEMPLATES = {
    "default": (
        "You are an AI assistant for the ArqAI FWA detection platform. "
        "Use provided data to answer accurately."
    ),
    "detailed": (
        "You are a senior healthcare fraud investigator AI. "
        "Provide thorough, evidence-based analysis with specific data points. "
        "Always cite case IDs and rule IDs."
    ),
    "concise": (
        "You are an ArqAI FWA assistant. Be brief and precise. "
        "Lead with the key number or finding. Use bullet points."
    ),
    "financial": (
        "You are a financial analysis AI for healthcare FWA. "
        "Focus on dollar amounts, savings calculations, and ROI. "
        "Show your calculations step by step."
    ),
}


class ParameterUpdaters:
    """
    Applies adaptation actions by modifying RAG parameters.
    Each update method enforces policy constraints.
    """

    def re_weight_sources(
        self,
        params: RAGParameters,
        drift_result: DriftResult,
    ) -> RAGParameters:
        """
        Adjust source weights based on which sources contribute to drift.

        Strategy: boost sources with better recent relevance,
        reduce sources correlated with recall drops.
        """
        new_params = params.copy()
        weights = dict(new_params.source_weights)

        # If recall dropped, reduce the heaviest source and boost the lightest
        recall_signals = [s for s in drift_result.signals if s["type"] == "recall_drop"]
        if recall_signals:
            heaviest = max(weights, key=weights.get)
            lightest = min(weights, key=weights.get)
            weights[heaviest] = max(weights[heaviest] - 0.05, 0.1)
            weights[lightest] = min(weights[lightest] + 0.05, new_params.max_source_weight)

        # If relevance dropped, boost knowledge_base
        relevance_signals = [s for s in drift_result.signals if s["type"] == "relevance_drop"]
        if relevance_signals:
            if "knowledge_base" in weights:
                weights["knowledge_base"] = min(
                    weights["knowledge_base"] + 0.05,
                    new_params.max_source_weight,
                )

        # Normalize to sum to 1.0
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        # Enforce max_source_weight cap
        for k in weights:
            if weights[k] > new_params.max_source_weight:
                excess = weights[k] - new_params.max_source_weight
                weights[k] = new_params.max_source_weight
                # Distribute excess to others
                others = [key for key in weights if key != k]
                if others:
                    for o in others:
                        weights[o] += excess / len(others)

        new_params.source_weights = weights
        logger.info("Re-weighted sources: %s", weights)
        return new_params

    def adjust_chunk_size(
        self,
        params: RAGParameters,
        drift_result: DriftResult,
    ) -> RAGParameters:
        """
        Adjust chunk size based on retrieval quality signals.

        Strategy: if recall drops, try larger chunks (more context per chunk).
        If precision drops (low hit rate), try smaller chunks (more specific).
        """
        new_params = params.copy()

        recall_signals = [s for s in drift_result.signals if s["type"] == "recall_drop"]
        hit_rate_signals = [s for s in drift_result.signals if s["type"] == "embedding_drift_proxy"]

        if recall_signals:
            # Increase chunk size for better recall
            new_params.chunk_size = min(
                new_params.chunk_size + 128,
                new_params.max_chunk_size,
            )
            new_params.chunk_overlap = min(new_params.chunk_overlap + 25, 100)
            new_params.top_k = min(new_params.top_k + 1, 10)

        elif hit_rate_signals:
            # Decrease chunk size for better precision
            new_params.chunk_size = max(
                new_params.chunk_size - 128,
                new_params.min_chunk_size,
            )

        logger.info("Adjusted chunk_size=%d, top_k=%d", new_params.chunk_size, new_params.top_k)
        return new_params

    def refresh_embeddings(self, params: RAGParameters) -> RAGParameters:
        """
        Flag embeddings for refresh (async re-indexing).

        In production, this triggers a background job to re-compute
        embeddings for the vector store.
        """
        new_params = params.copy()
        new_params.embedding_refresh_pending = True
        logger.info("Flagged embedding refresh (will re-index on next batch)")
        return new_params

    def switch_prompt_model(
        self,
        params: RAGParameters,
        drift_result: DriftResult,
    ) -> RAGParameters:
        """
        Switch prompt template and/or LLM model based on signals.

        Strategy:
        - Latency spike → switch to concise template (fewer tokens)
        - Confidence drop → switch to detailed template (more guidance)
        - Financial queries → switch to financial template
        """
        new_params = params.copy()

        latency_signals = [s for s in drift_result.signals if s["type"] == "latency_spike"]
        confidence_signals = [s for s in drift_result.signals if s["type"] == "confidence_drop"]

        if latency_signals:
            new_params.prompt_template = "concise"
            new_params.temperature = 0.2  # lower temperature for faster generation
            logger.info("Switched to concise template (latency optimization)")

        elif confidence_signals:
            new_params.prompt_template = "detailed"
            new_params.temperature = 0.3
            logger.info("Switched to detailed template (confidence improvement)")

        return new_params

    def apply_all(
        self,
        params: RAGParameters,
        actions: list,
        drift_result: DriftResult,
    ) -> RAGParameters:
        """Apply all selected adaptation actions in sequence."""
        from app.oda_rag.adaptive_controller import AdaptationAction

        current = params
        for action in actions:
            if action == AdaptationAction.RE_WEIGHT_SOURCES:
                current = self.re_weight_sources(current, drift_result)
            elif action == AdaptationAction.ADJUST_CHUNK_SIZE:
                current = self.adjust_chunk_size(current, drift_result)
            elif action == AdaptationAction.REFRESH_EMBEDDINGS:
                current = self.refresh_embeddings(current)
            elif action == AdaptationAction.SWITCH_PROMPT_MODEL:
                current = self.switch_prompt_model(current, drift_result)
        return current
