"""
Agent API — AI-powered investigation and chat endpoints.

Includes streaming chat, session management, and workspace-scoped guardrails.
"""

import json
import logging
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.auth.permissions import Permission
from app.auth.context import RequestContext
from app.config import settings
from app.models.chat import ChatSession, ChatMessage
from app.models import Workspace
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


class InvestigateRequest(BaseModel):
    case_id: str
    question: str | None = None
    workspace_id: str | None = None


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
    session_id: str | None = None
    workspace_id: str | None = None


class ChatResponseSchema(BaseModel):
    response: str
    sources_cited: list[str]
    model_used: str
    confidence: str = "medium"
    session_id: str | None = None


class SessionSummary(BaseModel):
    session_id: str
    title: str
    case_id: str | None = None
    message_count: int
    created_at: str | None = None
    updated_at: str | None = None


async def _resolve_workspace(db: AsyncSession, workspace_id: str | None) -> int | None:
    if not workspace_id:
        return None
    result = await db.execute(select(Workspace).where(Workspace.workspace_id == workspace_id))
    ws = result.scalar_one_or_none()
    return ws.id if ws else None


@router.get("/status")
async def agent_status():
    """Check if the AI model is available."""
    model = settings.llm_model
    base_url = settings.ollama_url
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                show_resp = await client.post(
                    f"{base_url}/api/show", json={"name": model},
                )
                if show_resp.status_code == 200:
                    return {"status": "ready", "model": model, "mode": "slm"}
            except Exception:
                pass

            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                tags = resp.json()
                models = [m.get("name", "") for m in tags.get("models", [])]
                model_base = model.split(":")[0]
                model_tag = model.split(":")[-1] if ":" in model else ""
                for m in models:
                    if m == model or model in m:
                        return {"status": "ready", "model": model, "mode": "slm"}
                    m_base = m.split(":")[0]
                    m_tag = m.split(":")[-1] if ":" in m else ""
                    if m_base == model_base and (m_tag == model_tag or model_tag in m_tag):
                        return {"status": "ready", "model": model, "mode": "slm"}
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
    ctx: RequestContext = Depends(require(Permission.AGENT_INVESTIGATE)),
    db: AsyncSession = Depends(get_db),
) -> InvestigateResponse:
    """AI agent investigates a case and produces a structured analysis."""
    try:
        ws_id = await _resolve_workspace(db, body.workspace_id) if body.workspace_id else ctx.workspace_id
        agent = AgentService(db, workspace_id=ws_id, ctx=ctx)
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
    except Exception as exc:
        logger.error("Investigate failed for %s: %s", body.case_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Investigation error: {exc}")


@router.post("/chat", response_model=ChatResponseSchema)
async def agent_chat(
    body: ChatRequest,
    ctx: RequestContext = Depends(require(Permission.AGENT_CHAT)),
    db: AsyncSession = Depends(get_db),
) -> ChatResponseSchema:
    """Interactive chat with the investigation assistant."""
    try:
        ws_id = await _resolve_workspace(db, body.workspace_id) if body.workspace_id else ctx.workspace_id
        agent = AgentService(db, workspace_id=ws_id, ctx=ctx)
        result = await agent.chat(body.message, body.case_id, body.session_id)

        # Persist to session if session_id provided
        session_id = body.session_id
        if session_id:
            chat_session = (await db.execute(
                select(ChatSession).where(ChatSession.session_id == session_id)
            )).scalar_one_or_none()

            if not chat_session:
                chat_session = ChatSession(
                    session_id=session_id,
                    workspace_id=ws_id,
                    title=body.message[:100],
                    case_id=body.case_id,
                )
                db.add(chat_session)
                await db.flush()

            db.add(ChatMessage(
                session_id=chat_session.id, role="user", content=body.message,
            ))
            db.add(ChatMessage(
                session_id=chat_session.id, role="assistant", content=result.response,
                sources_cited=result.sources_cited, model_used=result.model_used,
                confidence=result.confidence,
            ))

        return ChatResponseSchema(
            response=result.response,
            sources_cited=result.sources_cited,
            model_used=result.model_used,
            confidence=result.confidence,
            session_id=session_id,
        )
    except Exception as exc:
        logger.error("Chat failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat error: {exc}")


@router.post("/chat/stream")
async def agent_chat_stream(
    body: ChatRequest,
    ctx: RequestContext = Depends(require(Permission.AGENT_CHAT)),
    db: AsyncSession = Depends(get_db),
):
    """Stream chat responses token-by-token via SSE."""
    ws_id = await _resolve_workspace(db, body.workspace_id) if body.workspace_id else ctx.workspace_id
    agent = AgentService(db, workspace_id=ws_id, ctx=ctx)

    async def generate():
        async for event in agent.chat_stream(body.message, body.case_id, body.session_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Session management ───────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(
    ctx: RequestContext = Depends(require(Permission.AGENT_CHAT)),
    db: AsyncSession = Depends(get_db),
    workspace_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """List chat sessions."""
    ws_id = await _resolve_workspace(db, workspace_id)
    q = select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(limit)
    if ws_id is not None:
        q = q.where(ChatSession.workspace_id == ws_id)
    result = await db.execute(q)
    sessions = []
    for s in result.scalars():
        msg_count = (await db.execute(
            select(ChatMessage).where(ChatMessage.session_id == s.id)
        )).scalars()
        sessions.append(SessionSummary(
            session_id=s.session_id,
            title=s.title,
            case_id=s.case_id,
            message_count=len(list(msg_count)),
            created_at=s.created_at.isoformat() if s.created_at else None,
            updated_at=s.updated_at.isoformat() if s.updated_at else None,
        ))
    return {"sessions": [s.model_dump() for s in sessions]}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    ctx: RequestContext = Depends(require(Permission.AGENT_CHAT)),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """Get messages for a chat session."""
    chat_session = (await db.execute(
        select(ChatSession).where(ChatSession.session_id == session_id)
    )).scalar_one_or_none()
    if not chat_session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    messages = (await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )).scalars()

    return {
        "session_id": session_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "sources_cited": m.sources_cited,
                "model_used": m.model_used,
                "confidence": m.confidence,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.post("/sessions/new")
async def create_session(
    ctx: RequestContext = Depends(require(Permission.AGENT_CHAT)),
    db: AsyncSession = Depends(get_db),
    workspace_id: str | None = Query(None),
    case_id: str | None = Query(None),
):
    """Create a new chat session and return its ID."""
    ws_id = await _resolve_workspace(db, workspace_id)
    sid = f"chat-{uuid4().hex[:12]}"
    session = ChatSession(
        session_id=sid, workspace_id=ws_id, case_id=case_id,
        title=f"Chat about {case_id}" if case_id else "New Chat",
    )
    db.add(session)
    await db.flush()
    return {"session_id": sid}
