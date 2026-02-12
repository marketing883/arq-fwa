"""
Agent API — LLM-powered investigation and chat endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.agent_service import AgentService


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
