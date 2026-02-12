"""
Agent API — AI-powered investigation and chat endpoints.
"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import settings
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


class InvestigateRequest(BaseModel):
    case_id: str
    question: str | None = None


class InvestigateResponse(BaseModel):
    case_id: str
    summary: str
    findings: list[str]
    risk_assessment: str
    recommended_actions: list[str]
    confidence: float
    model_used: str
    generated_at: str


class ChatRequest(BaseModel):
    message: str
    case_id: str | None = None


class ChatResponseSchema(BaseModel):
    response: str
    sources_cited: list[str]
    model_used: str


@router.get("/status")
async def agent_status():
    """Check if the AI model is available."""
    model = settings.llm_model
    base_url = settings.ollama_url
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Method 1: Direct model check via /api/show (most reliable)
            try:
                show_resp = await client.post(
                    f"{base_url}/api/show",
                    json={"name": model},
                )
                if show_resp.status_code == 200:
                    logger.info("Ollama model %s is ready (via /api/show)", model)
                    return {"status": "ready", "model": model, "mode": "slm"}
            except Exception:
                pass

            # Method 2: Fallback to /api/tags list
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                tags = resp.json()
                models = [m.get("name", "") for m in tags.get("models", [])]
                logger.info("Ollama available models: %s", models)

                # Normalize: strip :latest tag for comparison
                model_base = model.split(":")[0]  # e.g. "qwen3"
                model_tag = model.split(":")[-1] if ":" in model else ""  # e.g. "8b"

                for m in models:
                    # Exact match
                    if m == model:
                        return {"status": "ready", "model": model, "mode": "slm"}
                    # Substring match (qwen3:8b in qwen3:8b-q4_0)
                    if model in m:
                        return {"status": "ready", "model": model, "mode": "slm"}
                    # Base match with tag (qwen3 matches qwen3:latest)
                    m_base = m.split(":")[0]
                    m_tag = m.split(":")[-1] if ":" in m else ""
                    if m_base == model_base and (m_tag == model_tag or model_tag in m_tag):
                        return {"status": "ready", "model": model, "mode": "slm"}

                logger.warning(
                    "Model %s not found in Ollama. Available: %s", model, models
                )
                return {
                    "status": "loading", "model": model, "mode": "data-engine",
                    "detail": f"Model {model} not found. Available: {', '.join(models) or 'none'}",
                }
    except Exception as exc:
        logger.warning("Cannot reach Ollama at %s: %s", base_url, exc)
    return {"status": "ready", "model": "data-engine", "mode": "data-engine"}


@router.post("/investigate", response_model=InvestigateResponse)
async def investigate_case(
    body: InvestigateRequest,
    db: AsyncSession = Depends(get_db),
) -> InvestigateResponse:
    """AI agent investigates a case and produces a structured analysis."""
    agent = AgentService(db)
    result = await agent.investigate_case(body.case_id)

    return InvestigateResponse(
        case_id=result.case_id,
        summary=result.summary,
        findings=result.findings,
        risk_assessment=result.risk_assessment,
        recommended_actions=result.recommended_actions,
        confidence=result.confidence,
        model_used=result.model_used,
        generated_at=result.generated_at,
    )


@router.post("/chat", response_model=ChatResponseSchema)
async def agent_chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponseSchema:
    """Interactive chat with the investigation assistant."""
    agent = AgentService(db)
    result = await agent.chat(body.message, body.case_id)

    return ChatResponseSchema(
        response=result.response,
        sources_cited=result.sources_cited,
        model_used=result.model_used,
    )
