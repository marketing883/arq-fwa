"""
Agent Service (Phase 9) — LLM-powered investigation assistant.

Uses Ollama (local LLM) for case investigation, chat, and evidence narration.
Provides graceful fallback when Ollama is unavailable.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    InvestigationCase, MedicalClaim, PharmacyClaim,
    RiskScore, RuleResult, Rule, Provider, Member,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


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
    model_used: str = "unavailable"


class AgentService:
    """LLM-powered investigation and chat agent using Ollama."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.ollama_url = settings.ollama_url
        self.model = settings.llm_model
        self._available: bool | None = None

    async def _check_ollama(self) -> bool:
        """Check if Ollama is available."""
        if self._available is not None:
            return self._available
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.ollama_url}/api/tags")
                self._available = resp.status_code == 200
        except Exception:
            self._available = False
        return self._available

    async def _call_ollama(self, prompt: str, system_prompt: str = "") -> str | None:
        """Call Ollama API. Returns None if unavailable."""
        if not await self._check_ollama():
            return None

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 2048},
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("message", {}).get("content", "")
        except Exception as e:
            logger.warning(f"Ollama call failed: {e}")
        return None

    async def _gather_case_context(self, case_id: str) -> dict:
        """Gather all relevant data for a case investigation."""
        # Get case
        case_q = await self.session.execute(
            select(InvestigationCase).where(InvestigationCase.case_id == case_id)
        )
        case = case_q.scalar_one_or_none()
        if not case:
            return {"error": f"Case {case_id} not found"}

        context: dict = {
            "case_id": case.case_id,
            "status": case.status,
            "priority": case.priority,
            "risk_level": case.risk_level,
            "risk_score": float(case.risk_score),
            "claim_id": case.claim_id,
            "claim_type": case.claim_type,
        }

        # Get claim details
        if case.claim_type == "medical":
            claim_q = await self.session.execute(
                select(MedicalClaim).where(MedicalClaim.claim_id == case.claim_id)
            )
            claim = claim_q.scalar_one_or_none()
            if claim:
                context["claim"] = {
                    "service_date": str(claim.service_date),
                    "cpt_code": claim.cpt_code,
                    "cpt_modifier": claim.cpt_modifier,
                    "diagnosis_primary": claim.diagnosis_code_primary,
                    "amount_billed": float(claim.amount_billed),
                    "amount_paid": float(claim.amount_paid) if claim.amount_paid else None,
                    "place_of_service": claim.place_of_service,
                    "units": claim.units,
                }
                # Provider info
                prov_q = await self.session.execute(
                    select(Provider).where(Provider.id == claim.provider_id)
                )
                prov = prov_q.scalar_one_or_none()
                if prov:
                    context["provider"] = {
                        "npi": prov.npi, "name": prov.name,
                        "specialty": prov.specialty,
                        "oig_excluded": prov.oig_excluded,
                    }
        else:
            claim_q = await self.session.execute(
                select(PharmacyClaim).where(PharmacyClaim.claim_id == case.claim_id)
            )
            claim = claim_q.scalar_one_or_none()
            if claim:
                context["claim"] = {
                    "fill_date": str(claim.fill_date),
                    "ndc_code": claim.ndc_code,
                    "drug_name": claim.drug_name,
                    "is_controlled": claim.is_controlled,
                    "dea_schedule": claim.dea_schedule,
                    "quantity_dispensed": float(claim.quantity_dispensed),
                    "days_supply": claim.days_supply,
                    "amount_billed": float(claim.amount_billed),
                }

        # Get rule results
        rr_q = await self.session.execute(
            select(RuleResult).where(
                RuleResult.claim_id == case.claim_id,
                RuleResult.triggered == True,
            )
        )
        triggered_rules = []
        for rr in rr_q.scalars():
            rule_q = await self.session.execute(
                select(Rule.category, Rule.description).where(Rule.rule_id == rr.rule_id)
            )
            rule_info = rule_q.first()
            triggered_rules.append({
                "rule_id": rr.rule_id,
                "category": rule_info[0] if rule_info else rr.rule_id,
                "description": rule_info[1] if rule_info else "",
                "severity": float(rr.severity) if rr.severity else 0,
                "confidence": float(rr.confidence) if rr.confidence else 0,
                "evidence": rr.evidence,
                "details": rr.details,
            })
        context["triggered_rules"] = triggered_rules

        # Risk score breakdown
        rs_q = await self.session.execute(
            select(RiskScore).where(RiskScore.claim_id == case.claim_id)
        )
        rs = rs_q.scalar_one_or_none()
        if rs:
            context["risk_score_detail"] = {
                "total": float(rs.total_score),
                "level": rs.risk_level,
                "contributions": rs.rule_contributions,
            }

        return context

    async def investigate_case(self, case_id: str) -> InvestigationResult:
        """Analyze a case using the LLM and produce structured findings."""
        context = await self._gather_case_context(case_id)

        if "error" in context:
            return InvestigationResult(
                case_id=case_id,
                summary=context["error"],
                findings=[], risk_assessment="", recommended_actions=[],
                confidence=0, model_used="none",
            )

        system_prompt = """You are an expert healthcare fraud, waste, and abuse (FWA) investigator.
Analyze the case data provided and produce a structured investigation report.
Be specific, reference the evidence, and provide actionable recommendations.
Format your response as JSON with these keys:
- summary: Brief 2-3 sentence overview
- findings: Array of specific findings (strings)
- risk_assessment: Overall risk assessment paragraph
- recommended_actions: Array of recommended next steps
- confidence: Float 0.0-1.0 representing your confidence in the assessment"""

        prompt = f"""Investigate this FWA case:

{json.dumps(context, indent=2, default=str)}

Provide your investigation report as JSON."""

        response = await self._call_ollama(prompt, system_prompt)

        if response:
            try:
                # Try to parse as JSON
                # Handle case where LLM wraps in markdown code blocks
                clean = response.strip()
                if clean.startswith("```"):
                    clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
                parsed = json.loads(clean)
                result = InvestigationResult(
                    case_id=case_id,
                    summary=parsed.get("summary", ""),
                    findings=parsed.get("findings", []),
                    risk_assessment=parsed.get("risk_assessment", ""),
                    recommended_actions=parsed.get("recommended_actions", []),
                    confidence=float(parsed.get("confidence", 0.7)),
                    model_used=self.model,
                )
            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, use raw text
                result = InvestigationResult(
                    case_id=case_id,
                    summary=response[:500],
                    findings=[response],
                    risk_assessment="See full analysis above",
                    recommended_actions=["Review the full analysis"],
                    confidence=0.5,
                    model_used=self.model,
                )
        else:
            # Fallback: generate rule-based analysis without LLM
            result = self._generate_fallback_analysis(case_id, context)

        # Audit log
        audit = AuditService(self.session)
        await audit.log_event(
            event_type="agent_investigation",
            actor=f"agent:{self.model}" if response else "agent:fallback",
            action=f"Investigated case {case_id}",
            resource_type="case",
            resource_id=case_id,
            details={"model": result.model_used, "confidence": result.confidence},
        )

        return result

    def _generate_fallback_analysis(self, case_id: str, context: dict) -> InvestigationResult:
        """Generate a rule-based analysis when LLM is unavailable."""
        rules = context.get("triggered_rules", [])
        claim = context.get("claim", {})
        provider = context.get("provider", {})
        risk = context.get("risk_score_detail", {})

        findings = []
        for r in rules:
            findings.append(
                f"Rule {r['rule_id']} ({r['category']}): {r.get('details', 'Triggered')} "
                f"[Severity: {r['severity']:.1f}, Confidence: {r['confidence']:.0%}]"
            )

        summary = (
            f"Case {case_id} involves a {context.get('claim_type', 'unknown')} claim "
            f"with risk score {risk.get('total', 0):.1f} ({risk.get('level', 'unknown')}). "
            f"{len(rules)} rule(s) triggered."
        )

        actions = []
        if any(r["severity"] >= 2.0 for r in rules):
            actions.append("Escalate for detailed review due to high severity findings")
        if provider.get("oig_excluded"):
            actions.append("URGENT: Provider is OIG-excluded. Report to compliance immediately")
        actions.append("Review provider billing history for patterns")
        actions.append("Contact member for verification if applicable")

        risk_text = (
            f"Risk level: {risk.get('level', 'unknown')}. "
            f"Total score: {risk.get('total', 0):.1f}/100. "
            f"Primary concerns: {', '.join(r['category'] for r in rules[:3])}."
        )

        return InvestigationResult(
            case_id=case_id,
            summary=summary,
            findings=findings,
            risk_assessment=risk_text,
            recommended_actions=actions,
            confidence=0.6,
            model_used="rule-based-fallback",
        )

    async def chat(self, message: str, case_id: str | None = None) -> ChatResponse:
        """Interactive investigation chat."""
        context_text = ""
        sources = []

        if case_id:
            context = await self._gather_case_context(case_id)
            if "error" not in context:
                context_text = f"\n\nCase context:\n{json.dumps(context, indent=2, default=str)}"
                sources.append(f"case:{case_id}")
                for r in context.get("triggered_rules", []):
                    sources.append(f"rule:{r['rule_id']}")

        system_prompt = """You are an AI assistant specializing in healthcare fraud, waste, and abuse (FWA) detection.
You help investigators analyze cases, explain fraud patterns, and provide guidance.
Be precise, reference specific data when available, and explain your reasoning."""

        prompt = f"{message}{context_text}"

        response = await self._call_ollama(prompt, system_prompt)

        if response:
            return ChatResponse(
                response=response,
                sources_cited=sources,
                model_used=self.model,
            )

        # Fallback response
        if case_id:
            context = await self._gather_case_context(case_id)
            rules = context.get("triggered_rules", [])
            return ChatResponse(
                response=(
                    f"AI agent is currently unavailable (Ollama not running). "
                    f"Here's what I can tell you from the data:\n\n"
                    f"Case {case_id} has {len(rules)} triggered rule(s):\n"
                    + "\n".join(f"- {r['rule_id']}: {r.get('details', r['category'])}" for r in rules)
                    + "\n\nFor AI-powered analysis, ensure Ollama is running with the "
                    f"{self.model} model."
                ),
                sources_cited=sources,
                model_used="fallback",
            )

        return ChatResponse(
            response=(
                "AI agent is currently unavailable. Ollama is not running or not reachable. "
                f"Please ensure Ollama is running at {self.ollama_url} with the {self.model} model loaded.\n\n"
                "You can still:\n"
                "- View case details and rule evaluations in the Cases tab\n"
                "- Check audit trail in the Compliance tab\n"
                "- Review rule configurations in the Rules tab"
            ),
            model_used="fallback",
        )
