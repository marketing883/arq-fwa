"""
Agent Service — AI-powered investigation assistant.

Uses a local SLM via Ollama for case investigation and chat.
When the model is still loading or unavailable, falls back to a data-driven
assistant that queries the database to answer questions about cases, claims,
rules, providers, and pipeline statistics.

Features:
- Conversation memory (session-based)
- Workspace-scoped guardrails
- Tool-use / ReAct loop
- Citation linking (case/rule IDs → markdown links)
- Confidence indicator (high/medium/low)
- Streaming support
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    InvestigationCase, MedicalClaim, PharmacyClaim,
    RiskScore, RuleResult, Rule, Provider, Member,
)
from app.models.chat import ChatSession, ChatMessage
from app.services.audit_service import AuditService
from app.middleware.metrics import agent_chat_requests_total, agent_chat_duration_seconds

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 20


@dataclass
class InvestigationResult:
    case_id: str
    summary: str
    findings: list[str]
    risk_assessment: str
    recommended_actions: list[str]
    confidence: float
    model_used: str
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ChatResponse:
    response: str
    sources_cited: list[str] = field(default_factory=list)
    model_used: str = "data-engine"
    confidence: str = "medium"


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(p in text for p in patterns)


# ── Citation linking ─────────────────────────────────────────────────────────

_CASE_ID_RE = re.compile(r'\b(CASE-[A-Z0-9]{6,})\b')
_RULE_SHORT_RE = re.compile(r'\b([MP]\d{2}_[A-Za-z_]+)\b')


def linkify_citations(text: str) -> str:
    text = _CASE_ID_RE.sub(r'[\1](/cases/\1)', text)
    text = _RULE_SHORT_RE.sub(r'[\1](/rules/\1)', text)
    return text


# ── Tool definitions for ReAct ───────────────────────────────────────────────

TOOL_DEFINITIONS = """
Available tools (respond with EXACTLY this JSON format to use one):
{"tool": "query_pipeline_stats"} - Get claim counts, case counts, risk breakdown
{"tool": "query_cases", "args": {"risk_level": "critical", "status": "open", "limit": 10}}
{"tool": "query_case_detail", "args": {"case_id": "CASE-XXXXXX"}}
{"tool": "query_rules", "args": {"triggered_only": true, "limit": 10}}
{"tool": "query_provider", "args": {"npi": "1234567890"}}
"""


class AgentService:
    def __init__(self, session: AsyncSession, workspace_id: int | None = None):
        self.session = session
        self.ollama_url = settings.ollama_url
        self.model = settings.llm_model
        self._available: bool | None = None
        self.workspace_id = workspace_id

    # ------------------------------------------------------------------
    # Ollama
    # ------------------------------------------------------------------

    async def _check_ollama(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                try:
                    show = await client.post(
                        f"{self.ollama_url}/api/show", json={"name": self.model},
                    )
                    if show.status_code == 200:
                        self._available = True
                        return True
                except Exception:
                    pass
                resp = await client.get(f"{self.ollama_url}/api/tags")
                if resp.status_code == 200:
                    models = [m.get("name", "") for m in resp.json().get("models", [])]
                    self._available = any(self.model == m or self.model in m for m in models)
                else:
                    self._available = False
        except Exception as exc:
            logger.warning("Ollama check failed: %s", exc)
            self._available = False
        return self._available

    @staticmethod
    def _strip_think_tags(text: str) -> str:
        return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()

    async def _call_ollama(self, prompt: str, system_prompt: str = "", history: list[dict] | None = None) -> str | None:
        if not await self._check_ollama():
            return None
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": prompt})

            timeout = httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": False,
                           "options": {"temperature": 0.3, "num_predict": 2048}},
                )
                if resp.status_code == 200:
                    content = resp.json().get("message", {}).get("content", "")
                    return self._strip_think_tags(content)
        except httpx.TimeoutException:
            self._available = None
        except Exception as e:
            logger.warning("Ollama call failed: %s", e)
            self._available = None
        return None

    async def _call_ollama_stream(self, prompt: str, system_prompt: str = "", history: list[dict] | None = None) -> AsyncIterator[str]:
        if not await self._check_ollama():
            return
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        timeout = httpx.Timeout(connect=10.0, read=180.0, write=10.0, pool=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", f"{self.ollama_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": True,
                           "options": {"temperature": 0.3, "num_predict": 2048}},
                ) as resp:
                    if resp.status_code != 200:
                        return
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.warning("Ollama stream failed: %s", e)
            self._available = None

    # ------------------------------------------------------------------
    # Tool execution (ReAct)
    # ------------------------------------------------------------------

    async def _execute_tool(self, tool_name: str, args: dict) -> str:
        if tool_name == "query_pipeline_stats":
            return await self._tool_pipeline_stats()
        elif tool_name == "query_cases":
            return await self._tool_query_cases(args)
        elif tool_name == "query_case_detail":
            return await self._tool_case_detail(args.get("case_id", ""))
        elif tool_name == "query_rules":
            return await self._tool_query_rules(args)
        elif tool_name == "query_provider":
            return await self._tool_query_provider(args.get("npi", ""))
        return f"Unknown tool: {tool_name}"

    async def _tool_pipeline_stats(self) -> str:
        med = (await self.session.execute(select(func.count()).select_from(MedicalClaim))).scalar() or 0
        rx = (await self.session.execute(select(func.count()).select_from(PharmacyClaim))).scalar() or 0
        cases = (await self.session.execute(select(func.count()).select_from(InvestigationCase))).scalar() or 0
        active = (await self.session.execute(
            select(func.count()).select_from(InvestigationCase).where(
                InvestigationCase.status.in_(["open", "under_review", "escalated"]))
        )).scalar() or 0
        risk_counts = {}
        for level in ("critical", "high", "medium", "low"):
            risk_counts[level] = (await self.session.execute(
                select(func.count()).select_from(InvestigationCase).where(InvestigationCase.risk_level == level)
            )).scalar() or 0
        return json.dumps({"total_claims": med + rx, "medical": med, "pharmacy": rx,
                           "cases": cases, "active_cases": active, "risk_breakdown": risk_counts})

    async def _tool_query_cases(self, args: dict) -> str:
        q = select(InvestigationCase)
        if args.get("risk_level"):
            q = q.where(InvestigationCase.risk_level == args["risk_level"])
        if args.get("status"):
            q = q.where(InvestigationCase.status == args["status"])
        q = q.order_by(InvestigationCase.risk_score.desc()).limit(args.get("limit", 10))
        result = await self.session.execute(q)
        cases = [{"case_id": c.case_id, "risk_score": float(c.risk_score), "risk_level": c.risk_level,
                  "status": c.status, "priority": c.priority, "claim_id": c.claim_id}
                 for c in result.scalars()]
        return json.dumps(cases)

    async def _tool_case_detail(self, case_id: str) -> str:
        ctx = await self._gather_case_context(case_id)
        return json.dumps(ctx, default=str)

    async def _tool_query_rules(self, args: dict) -> str:
        q = (select(RuleResult.rule_id, func.count().label("cnt"))
             .where(RuleResult.triggered == True)
             .group_by(RuleResult.rule_id)
             .order_by(func.count().desc())
             .limit(args.get("limit", 10)))
        result = await self.session.execute(q)
        return json.dumps([{"rule_id": r[0], "trigger_count": r[1]} for r in result])

    async def _tool_query_provider(self, npi: str) -> str:
        prov_q = await self.session.execute(select(Provider).where(Provider.npi == npi))
        prov = prov_q.scalar_one_or_none()
        if not prov:
            return json.dumps({"error": f"Provider NPI {npi} not found"})
        return json.dumps({"npi": prov.npi, "name": prov.name, "specialty": prov.specialty,
                           "is_active": prov.is_active, "oig_excluded": prov.oig_excluded})

    def _parse_tool_call(self, text: str) -> tuple[str, dict] | None:
        match = re.search(r'\{[^{}]*"tool"\s*:\s*"[^"]+?"[^{}]*\}', text)
        if match:
            try:
                parsed = json.loads(match.group())
                tool_name = parsed.get("tool")
                if tool_name:
                    return tool_name, parsed.get("args", {})
            except json.JSONDecodeError:
                pass
        return None

    async def _react_loop(self, message: str, system_prompt: str, history: list[dict] | None = None) -> tuple[str, list[str]]:
        sources: list[str] = []
        current_prompt = message
        for i in range(5):
            response = await self._call_ollama(current_prompt, system_prompt, history)
            if not response:
                return "", sources
            tool_call = self._parse_tool_call(response)
            if tool_call is None:
                return response, sources
            tool_name, args = tool_call
            logger.info("ReAct %d: tool=%s args=%s", i + 1, tool_name, args)
            tool_result = await self._execute_tool(tool_name, args)
            sources.append(f"tool:{tool_name}")
            current_prompt = (
                f"Tool result for {tool_name}:\n{tool_result}\n\n"
                f"Now answer the user's original question based on this data. "
                f"Do NOT call another tool unless you need additional information."
            )
        return response or "", sources

    # ------------------------------------------------------------------
    # Case context
    # ------------------------------------------------------------------

    async def _gather_case_context(self, case_id: str) -> dict:
        q = select(InvestigationCase).where(InvestigationCase.case_id == case_id)
        if self.workspace_id is not None:
            q = q.where(InvestigationCase.workspace_id == self.workspace_id)
        case = (await self.session.execute(q)).scalar_one_or_none()
        if not case:
            return {"error": f"Case {case_id} not found"}

        context: dict = {
            "case_id": case.case_id, "status": case.status, "priority": case.priority,
            "risk_level": case.risk_level, "risk_score": float(case.risk_score),
            "claim_id": case.claim_id, "claim_type": case.claim_type,
        }

        if case.claim_type == "medical":
            claim = (await self.session.execute(
                select(MedicalClaim).where(MedicalClaim.claim_id == case.claim_id)
            )).scalar_one_or_none()
            if claim:
                context["claim"] = {
                    "service_date": str(claim.service_date), "cpt_code": claim.cpt_code,
                    "cpt_modifier": claim.cpt_modifier, "diagnosis_primary": claim.diagnosis_code_primary,
                    "amount_billed": float(claim.amount_billed),
                    "amount_paid": float(claim.amount_paid) if claim.amount_paid else None,
                    "place_of_service": claim.place_of_service, "units": claim.units,
                }
                prov = (await self.session.execute(
                    select(Provider).where(Provider.id == claim.provider_id)
                )).scalar_one_or_none()
                if prov:
                    context["provider"] = {"npi": prov.npi, "name": prov.name,
                                            "specialty": prov.specialty, "oig_excluded": prov.oig_excluded}
        else:
            claim = (await self.session.execute(
                select(PharmacyClaim).where(PharmacyClaim.claim_id == case.claim_id)
            )).scalar_one_or_none()
            if claim:
                context["claim"] = {
                    "fill_date": str(claim.fill_date), "ndc_code": claim.ndc_code,
                    "drug_name": claim.drug_name, "is_controlled": claim.is_controlled,
                    "dea_schedule": claim.dea_schedule,
                    "quantity_dispensed": float(claim.quantity_dispensed),
                    "days_supply": claim.days_supply, "amount_billed": float(claim.amount_billed),
                }

        rr_q = await self.session.execute(
            select(RuleResult).where(RuleResult.claim_id == case.claim_id, RuleResult.triggered == True)
        )
        triggered_rules = []
        for rr in rr_q.scalars():
            rule_info = (await self.session.execute(
                select(Rule.category, Rule.description, Rule.fraud_type).where(Rule.rule_id == rr.rule_id)
            )).first()
            triggered_rules.append({
                "rule_id": rr.rule_id,
                "category": rule_info[0] if rule_info else rr.rule_id,
                "description": rule_info[1] if rule_info else "",
                "fraud_type": rule_info[2] if rule_info else "",
                "severity": float(rr.severity) if rr.severity else 0,
                "confidence": float(rr.confidence) if rr.confidence else 0,
                "evidence": rr.evidence, "details": rr.details,
            })
        context["triggered_rules"] = triggered_rules

        rs = (await self.session.execute(
            select(RiskScore).where(RiskScore.claim_id == case.claim_id)
        )).scalar_one_or_none()
        if rs:
            context["risk_score_detail"] = {
                "total": float(rs.total_score), "level": rs.risk_level,
                "contributions": rs.rule_contributions,
            }
        return context

    # ------------------------------------------------------------------
    # Data context for RAG
    # ------------------------------------------------------------------

    async def _gather_data_context(self, message: str) -> tuple[str, list[str]]:
        msg = message.lower()
        sections: list[str] = []
        sources: list[str] = []

        med = (await self.session.execute(select(func.count()).select_from(MedicalClaim))).scalar() or 0
        rx = (await self.session.execute(select(func.count()).select_from(PharmacyClaim))).scalar() or 0
        total_cases = (await self.session.execute(select(func.count()).select_from(InvestigationCase))).scalar() or 0
        active = (await self.session.execute(
            select(func.count()).select_from(InvestigationCase).where(
                InvestigationCase.status.in_(["open", "under_review", "escalated"]))
        )).scalar() or 0

        risk_counts = {}
        for level in ("critical", "high", "medium", "low"):
            risk_counts[level] = (await self.session.execute(
                select(func.count()).select_from(InvestigationCase).where(InvestigationCase.risk_level == level)
            )).scalar() or 0

        status_counts = {}
        for st in ("open", "under_review", "escalated", "resolved", "closed"):
            status_counts[st] = (await self.session.execute(
                select(func.count()).select_from(InvestigationCase).where(InvestigationCase.status == st)
            )).scalar() or 0

        scored = (await self.session.execute(select(func.count()).select_from(RiskScore))).scalar() or 0

        sections.append(
            f"PLATFORM DATA (live):\n"
            f"- Total claims: {med + rx:,} ({med:,} medical, {rx:,} pharmacy)\n"
            f"- Scored: {scored:,}\n- Cases: {total_cases:,} total, {active:,} active\n"
            f"- Risk: {risk_counts['critical']} critical, {risk_counts['high']} high, "
            f"{risk_counts['medium']} medium, {risk_counts['low']} low\n"
            f"- Status: {', '.join(f'{v} {k}' for k, v in status_counts.items() if v > 0)}"
        )
        sources.append("database:pipeline-stats")

        if _matches_any(msg, ["risk", "critical", "high", "case", "top", "worst", "severe",
                               "many", "total", "count", "list", "show", "open", "active", "investigate"]):
            q = await self.session.execute(
                select(InvestigationCase).order_by(InvestigationCase.risk_score.desc()).limit(10)
            )
            cases = list(q.scalars())
            if cases:
                lines = [f"  {c.case_id}: score={float(c.risk_score):.1f}, level={c.risk_level}, "
                         f"status={c.status}, priority={c.priority}, claim={c.claim_id}" for c in cases]
                sections.append("TOP 10 CASES:\n" + "\n".join(lines))
                sources.append("database:top-cases")

        if _matches_any(msg, ["rule", "trigger", "detection", "pattern", "flag", "fired", "common"]):
            q = await self.session.execute(
                select(RuleResult.rule_id, func.count().label("cnt"))
                .where(RuleResult.triggered == True)
                .group_by(RuleResult.rule_id)
                .order_by(func.count().desc()).limit(10)
            )
            top_rules = list(q)
            if top_rules:
                rule_ids = [r[0] for r in top_rules]
                rm = {r.rule_id: r for r in (await self.session.execute(
                    select(Rule).where(Rule.rule_id.in_(rule_ids))
                )).scalars()}
                lines = [f"  {rid} ({rm[rid].category if rid in rm else 'N/A'}): "
                         f"{rm[rid].description if rid in rm else rid} — {cnt} times"
                         for rid, cnt in top_rules]
                sections.append("TOP RULES:\n" + "\n".join(lines))
                sources.append("database:rule-stats")

        return "\n\n".join(sections), sources

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------

    async def _load_session_history(self, session_id: str) -> list[dict]:
        result = await self.session.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        chat_session = result.scalar_one_or_none()
        if not chat_session:
            return []
        msg_result = await self.session.execute(
            select(ChatMessage).where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.created_at.desc()).limit(MAX_HISTORY_MESSAGES)
        )
        messages = list(reversed(list(msg_result.scalars())))
        return [{"role": m.role, "content": m.content} for m in messages]

    # ------------------------------------------------------------------
    # Investigate
    # ------------------------------------------------------------------

    async def investigate_case(self, case_id: str) -> InvestigationResult:
        context = await self._gather_case_context(case_id)
        if "error" in context:
            return InvestigationResult(case_id=case_id, summary=context["error"],
                                       findings=[], risk_assessment="", recommended_actions=[],
                                       confidence=0, model_used="none")

        system_prompt = (
            "You are an expert healthcare FWA investigator.\n"
            "Analyze the case and produce a structured investigation report.\n"
            "Format as JSON: summary, findings (array), risk_assessment, "
            "recommended_actions (array), confidence (0.0-1.0)."
        )
        prompt = f"Investigate:\n{json.dumps(context, indent=2, default=str)}\nProvide JSON report."

        response = await self._call_ollama(prompt, system_prompt)
        if response:
            try:
                clean = response.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
                parsed = json.loads(clean)
                result = InvestigationResult(
                    case_id=case_id, summary=parsed.get("summary", ""),
                    findings=parsed.get("findings", []),
                    risk_assessment=parsed.get("risk_assessment", ""),
                    recommended_actions=parsed.get("recommended_actions", []),
                    confidence=float(parsed.get("confidence", 0.7)),
                    model_used=self.model)
            except (json.JSONDecodeError, ValueError):
                result = InvestigationResult(
                    case_id=case_id, summary=response[:500], findings=[response],
                    risk_assessment="See analysis above",
                    recommended_actions=["Review full analysis"],
                    confidence=0.5, model_used=self.model)
        else:
            result = self._generate_fallback_analysis(case_id, context)

        audit = AuditService(self.session)
        await audit.log_event(
            event_type="agent_investigation", actor=f"agent:{result.model_used}",
            action=f"Investigated case {case_id}", resource_type="case", resource_id=case_id,
            details={"model": result.model_used, "confidence": result.confidence})
        return result

    def _generate_fallback_analysis(self, case_id: str, context: dict) -> InvestigationResult:
        rules = context.get("triggered_rules", [])
        claim = context.get("claim", {})
        provider = context.get("provider", {})
        risk = context.get("risk_score_detail", {})

        findings = []
        for r in rules:
            sev = "High" if r["severity"] >= 2 else "Medium" if r["severity"] >= 1 else "Low"
            findings.append(f"[{sev}] {r.get('description') or r['rule_id']}: "
                           f"{r.get('details', 'Triggered')} (Conf: {r['confidence']:.0%})")

        amount = claim.get("amount_billed", 0)
        summary = (f"Case {case_id}: {context.get('claim_type', 'unknown')} claim "
                   f"${amount:,.2f}, risk {risk.get('total', 0):.1f}/100 ({risk.get('level', 'unknown')}). "
                   f"{len(rules)} rule(s) triggered.")
        if provider:
            summary += f" Provider: {provider.get('name', 'N/A')} ({provider.get('specialty', 'N/A')})."

        actions = []
        if provider.get("oig_excluded"):
            actions.append("URGENT: OIG-excluded provider — report to compliance")
        if any(r["severity"] >= 2 for r in rules):
            actions.append("Escalate for SIU review — high-severity findings")
        fraud_types = list({r.get("fraud_type", "") for r in rules if r.get("fraud_type")})
        if fraud_types:
            actions.append(f"Investigate: {', '.join(ft.replace('_', ' ') for ft in fraud_types)}")
        actions.extend(["Pull provider billing history (12 months)", "Verify medical necessity",
                        "Contact member for verification"])

        risk_text = f"Level: {risk.get('level', 'unknown').upper()}, Score: {risk.get('total', 0):.1f}/100."
        if fraud_types:
            risk_text += f" Patterns: {', '.join(ft.replace('_', ' ') for ft in fraud_types)}."

        return InvestigationResult(
            case_id=case_id, summary=summary, findings=findings,
            risk_assessment=risk_text, recommended_actions=actions,
            confidence=0.75, model_used="data-engine")

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    async def chat(self, message: str, case_id: str | None = None,
                   session_id: str | None = None) -> ChatResponse:
        t_start = time.time()
        sources: list[str] = []
        try:
            history = []
            if session_id:
                history = await self._load_session_history(session_id)

            data_context, data_sources = await self._gather_data_context(message)
            sources.extend(data_sources)

            context_parts = [data_context] if data_context else []
            if case_id:
                case_ctx = await self._gather_case_context(case_id)
                if "error" not in case_ctx:
                    context_parts.append(f"SELECTED CASE:\n{json.dumps(case_ctx, indent=2, default=str)}")
                    sources.append(f"case:{case_id}")
                    for r in case_ctx.get("triggered_rules", []):
                        sources.append(f"rule:{r['rule_id']}")

            ws_note = f"\nScoped to workspace {self.workspace_id}." if self.workspace_id else ""
            system_prompt = (
                "You are an AI assistant for the ArqAI FWA detection platform. "
                "Use the provided LIVE DATA to answer questions accurately.\n"
                "RULES: Always quote exact numbers. Use markdown formatting. "
                "Be concise. Reference case/rule IDs exactly.\n"
                f"{ws_note}\n\n{TOOL_DEFINITIONS}"
            )

            context_block = "\n\n---\n\n".join(context_parts)
            prompt = f"{message}\n\n{context_block}" if context_block else message

            response, tool_sources = await self._react_loop(prompt, system_prompt, history or None)
            sources.extend(tool_sources)

            if response:
                response = linkify_citations(response)
                duration = time.time() - t_start
                agent_chat_requests_total.labels(model_used=self.model).inc()
                agent_chat_duration_seconds.observe(duration)
                return ChatResponse(response=response, sources_cited=sources,
                                    model_used=self.model, confidence="high" if sources else "medium")

            result = await self._data_driven_chat(message, case_id, sources)
            result.response = linkify_citations(result.response)
            result.confidence = "high"
            duration = time.time() - t_start
            agent_chat_requests_total.labels(model_used="data-engine").inc()
            agent_chat_duration_seconds.observe(duration)
            return result

        except Exception as exc:
            logger.error("Chat error: %s", exc, exc_info=True)
            return ChatResponse(
                response=f"Error: {type(exc).__name__}: {exc}. Please try again.",
                sources_cited=sources, model_used="error-fallback", confidence="low")

    # ------------------------------------------------------------------
    # Streaming chat
    # ------------------------------------------------------------------

    async def chat_stream(self, message: str, case_id: str | None = None,
                          session_id: str | None = None) -> AsyncIterator[dict]:
        sources: list[str] = []
        history = await self._load_session_history(session_id) if session_id else []

        data_context, data_sources = await self._gather_data_context(message)
        sources.extend(data_sources)
        context_parts = [data_context] if data_context else []
        if case_id:
            case_ctx = await self._gather_case_context(case_id)
            if "error" not in case_ctx:
                context_parts.append(f"CASE:\n{json.dumps(case_ctx, indent=2, default=str)}")
                sources.append(f"case:{case_id}")

        system_prompt = "You are an AI assistant for ArqAI FWA detection. Use provided data. Markdown format."
        context_block = "\n\n---\n\n".join(context_parts)
        prompt = f"{message}\n\n{context_block}" if context_block else message

        full = ""
        async for token in self._call_ollama_stream(prompt, system_prompt, history or None):
            full += token
            yield {"token": token, "done": False}

        if full:
            full = linkify_citations(self._strip_think_tags(full))
            yield {"done": True, "response": full, "sources_cited": sources,
                   "model_used": self.model, "confidence": "high" if sources else "medium"}
        else:
            result = await self._data_driven_chat(message, case_id, sources)
            result.response = linkify_citations(result.response)
            yield {"done": True, "response": result.response, "sources_cited": result.sources_cited,
                   "model_used": result.model_used, "confidence": "high"}

    # ------------------------------------------------------------------
    # Data-driven fallback
    # ------------------------------------------------------------------

    async def _data_driven_chat(self, message: str, case_id: str | None, sources: list[str]) -> ChatResponse:
        msg = message.lower().strip()
        if case_id:
            ctx = await self._gather_case_context(case_id)
            if "error" in ctx:
                return ChatResponse(response=ctx["error"], sources_cited=sources)
            return self._answer_case_question(msg, ctx, sources)
        if _matches_any(msg, ["how many", "total", "count", "overview", "summary", "stats", "dashboard"]):
            return await self._answer_stats(sources)
        if _matches_any(msg, ["high risk", "critical", "top risk", "worst", "riskiest"]):
            return await self._answer_top_risk(sources)
        if _matches_any(msg, ["rule", "what rules", "which rules", "detection", "trigger"]):
            return await self._answer_rules(sources)
        if _matches_any(msg, ["provider", "doctor", "npi"]):
            return await self._answer_provider(msg, sources)
        if _matches_any(msg, ["help", "what can you", "capabilities"]):
            return self._answer_help(sources)
        return await self._answer_general(sources)

    def _answer_case_question(self, msg: str, ctx: dict, sources: list[str]) -> ChatResponse:
        rules = ctx.get("triggered_rules", [])
        claim = ctx.get("claim", {})
        provider = ctx.get("provider", {})
        risk = ctx.get("risk_score_detail", {})

        if _matches_any(msg, ["why", "explain", "what happened", "tell me", "analyze", "detail", "describe"]):
            lines = [f"**Case {ctx['case_id']}** — {ctx['risk_level'].upper()} risk ({ctx['risk_score']:.1f}/100)\n"]
            if claim:
                if ctx["claim_type"] == "medical":
                    lines.append(f"**Claim:** CPT {claim.get('cpt_code', 'N/A')}, "
                                 f"Dx {claim.get('diagnosis_primary', 'N/A')}, ${claim.get('amount_billed', 0):,.2f}")
                else:
                    lines.append(f"**Claim:** {claim.get('drug_name', 'N/A')} (NDC {claim.get('ndc_code', 'N/A')}), "
                                 f"${claim.get('amount_billed', 0):,.2f}")
            if provider:
                oig = " **[OIG EXCLUDED]**" if provider.get("oig_excluded") else ""
                lines.append(f"\n**Provider:** {provider.get('name')} ({provider.get('specialty')}){oig}")
            if rules:
                lines.append(f"\n**{len(rules)} rule(s):**")
                for r in sorted(rules, key=lambda x: x["severity"], reverse=True):
                    lines.append(f"- **{r['rule_id']}** — {r.get('description') or r.get('details', 'Triggered')} "
                                 f"(sev {r['severity']:.1f}, conf {r['confidence']:.0%})")
            return ChatResponse(response="\n".join(lines), sources_cited=sources)

        if _matches_any(msg, ["rule", "trigger", "flag"]):
            if not rules:
                return ChatResponse(response=f"No rules triggered for {ctx['case_id']}.", sources_cited=sources)
            lines = [f"**{len(rules)} rule(s) for {ctx['case_id']}:**\n"]
            for r in sorted(rules, key=lambda x: x["severity"], reverse=True):
                lines.append(f"- **{r['rule_id']}**: {r.get('description') or r.get('details', 'Triggered')}")
            return ChatResponse(response="\n".join(lines), sources_cited=sources)

        if _matches_any(msg, ["risk", "score"]):
            lines = [f"**Risk: {risk.get('total', 0):.1f}/100 ({risk.get('level', 'N/A')})**"]
            contribs = risk.get("contributions", {})
            if contribs:
                lines.append("\n**Breakdown:**")
                for rid, c in sorted(contribs.items(),
                                     key=lambda x: x[1].get("contribution", 0) if isinstance(x[1], dict) else 0,
                                     reverse=True):
                    if isinstance(c, dict):
                        lines.append(f"  - {rid}: +{c.get('contribution', 0):.2f}")
            return ChatResponse(response="\n".join(lines), sources_cited=sources)

        if _matches_any(msg, ["recommend", "action", "should", "next step"]):
            actions = []
            if provider and provider.get("oig_excluded"):
                actions.append("URGENT: OIG-excluded provider — report to compliance")
            if any(r["severity"] >= 2 for r in rules):
                actions.append("Escalate to SIU for review")
            actions.extend(["Review provider billing history", "Verify medical necessity", "Contact member"])
            return ChatResponse(
                response=f"**Actions for {ctx['case_id']}:**\n\n" + "\n".join(f"{i+1}. {a}" for i, a in enumerate(actions)),
                sources_cited=sources)

        lines = [f"**{ctx['case_id']}** — {ctx['risk_level'].upper()}, score {ctx['risk_score']:.1f}/100, "
                 f"status: {ctx.get('status')}, {len(rules)} rules triggered"]
        if claim:
            lines.append(f"Amount: ${claim.get('amount_billed', 0):,.2f}")
        lines.append("\nAsk: *explain*, *rules*, *risk score*, *recommendations*, or *provider*")
        return ChatResponse(response="\n".join(lines), sources_cited=sources)

    async def _answer_stats(self, sources: list[str]) -> ChatResponse:
        med = (await self.session.execute(select(func.count()).select_from(MedicalClaim))).scalar() or 0
        rx = (await self.session.execute(select(func.count()).select_from(PharmacyClaim))).scalar() or 0
        cases = (await self.session.execute(select(func.count()).select_from(InvestigationCase))).scalar() or 0
        active = (await self.session.execute(
            select(func.count()).select_from(InvestigationCase).where(
                InvestigationCase.status.in_(["open", "under_review", "escalated"]))
        )).scalar() or 0
        scored = (await self.session.execute(select(func.count()).select_from(RiskScore))).scalar() or 0
        return ChatResponse(
            response=f"**Pipeline Overview:**\n\n- **{med:,}** medical + **{rx:,}** pharmacy = **{med + rx:,}** claims\n"
                     f"- **{scored:,}** scored, **{med + rx - scored:,}** unscored\n"
                     f"- **{cases:,}** cases ({active:,} active)",
            sources_cited=sources)

    async def _answer_top_risk(self, sources: list[str]) -> ChatResponse:
        cases = list((await self.session.execute(
            select(InvestigationCase)
            .where(InvestigationCase.status.in_(["open", "under_review", "escalated"]))
            .order_by(InvestigationCase.risk_score.desc()).limit(10)
        )).scalars())
        if not cases:
            return ChatResponse(response="No active cases found.", sources_cited=sources)
        lines = [f"**Top {len(cases)} active cases:**\n"]
        for c in cases:
            lines.append(f"- **{c.case_id}** — {float(c.risk_score):.1f} ({c.risk_level}), {c.priority}")
        return ChatResponse(response="\n".join(lines), sources_cited=sources)

    async def _answer_rules(self, sources: list[str]) -> ChatResponse:
        top = list(await self.session.execute(
            select(RuleResult.rule_id, func.count().label("cnt"))
            .where(RuleResult.triggered == True)
            .group_by(RuleResult.rule_id).order_by(func.count().desc()).limit(10)
        ))
        if not top:
            return ChatResponse(response="No rule results yet. Run the pipeline first.", sources_cited=sources)
        rm = {r.rule_id: r for r in (await self.session.execute(
            select(Rule).where(Rule.rule_id.in_([r[0] for r in top]))
        )).scalars()}
        lines = ["**Top triggered rules:**\n"]
        for rid, cnt in top:
            r = rm.get(rid)
            lines.append(f"- **{rid}** ({r.category if r else 'N/A'}): {r.description if r else rid} — **{cnt}** times")
        return ChatResponse(response="\n".join(lines), sources_cited=sources)

    async def _answer_provider(self, msg: str, sources: list[str]) -> ChatResponse:
        npi_match = re.search(r'\b(\d{10})\b', msg)
        if npi_match:
            prov = (await self.session.execute(
                select(Provider).where(Provider.npi == npi_match.group(1))
            )).scalar_one_or_none()
            if prov:
                oig = " **[OIG EXCLUDED]**" if prov.oig_excluded else ""
                return ChatResponse(
                    response=f"**{prov.name}**{oig}\n- NPI: {prov.npi}\n- Specialty: {prov.specialty}",
                    sources_cited=sources)
            return ChatResponse(response=f"No provider with NPI {npi_match.group(1)}.", sources_cited=sources)
        return ChatResponse(response="Provide a 10-digit NPI to look up a provider.", sources_cited=sources)

    def _answer_help(self, sources: list[str]) -> ChatResponse:
        return ChatResponse(
            response="**I can help with:**\n\n"
                     "**With a case:** explain, rules, risk score, recommendations, provider\n"
                     "**General:** stats, top risk cases, most triggered rules, provider lookup (NPI)",
            sources_cited=sources)

    async def _answer_general(self, sources: list[str]) -> ChatResponse:
        active = (await self.session.execute(
            select(func.count()).select_from(InvestigationCase).where(
                InvestigationCase.status.in_(["open", "under_review", "escalated"]))
        )).scalar() or 0
        return ChatResponse(
            response=f"**{active}** active cases. Try: \"show stats\", \"top risk cases\", \"which rules trigger most?\"\n"
                     "Or **select a case** to investigate.",
            sources_cited=sources)
