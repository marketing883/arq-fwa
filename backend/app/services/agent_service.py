"""
Agent Service (Phase 9) — AI-powered investigation assistant.

Uses a local SLM via Ollama for case investigation and chat.
When the model is still loading or unavailable, falls back to a data-driven
assistant that queries the database to answer questions about cases, claims,
rules, providers, and pipeline statistics.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from sqlalchemy import select, func, and_
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
    model_used: str = "data-engine"


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(p in text for p in patterns)


class AgentService:
    """AI investigation assistant — SLM-powered with data-driven fallback."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.ollama_url = settings.ollama_url
        self.model = settings.llm_model
        self._available: bool | None = None

    # ------------------------------------------------------------------
    # Ollama integration
    # ------------------------------------------------------------------

    async def _check_ollama(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Try direct model check first (most reliable)
                try:
                    show = await client.post(
                        f"{self.ollama_url}/api/show",
                        json={"name": self.model},
                    )
                    if show.status_code == 200:
                        self._available = True
                        logger.info("Ollama model %s confirmed via /api/show", self.model)
                        return True
                except Exception:
                    pass

                # Fallback to tag list
                resp = await client.get(f"{self.ollama_url}/api/tags")
                if resp.status_code == 200:
                    tags = resp.json()
                    models = [m.get("name", "") for m in tags.get("models", [])]
                    self._available = any(
                        self.model == m or self.model in m for m in models
                    )
                    if not self._available:
                        logger.warning(
                            "Model %s not in Ollama tags: %s", self.model, models
                        )
                else:
                    self._available = False
        except Exception as exc:
            logger.warning("Ollama check failed: %s", exc)
            self._available = False
        return self._available

    @staticmethod
    def _strip_think_tags(text: str) -> str:
        """Strip <think>…</think> reasoning blocks from qwen3-style output."""
        return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()

    async def _call_ollama(self, prompt: str, system_prompt: str = "") -> str | None:
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
                    content = data.get("message", {}).get("content", "")
                    return self._strip_think_tags(content)
        except Exception as e:
            logger.warning(f"Ollama call failed: {e}")
        return None

    # ------------------------------------------------------------------
    # Case context gathering
    # ------------------------------------------------------------------

    async def _gather_case_context(self, case_id: str) -> dict:
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

        rr_q = await self.session.execute(
            select(RuleResult).where(
                RuleResult.claim_id == case.claim_id,
                RuleResult.triggered == True,
            )
        )
        triggered_rules = []
        for rr in rr_q.scalars():
            rule_q = await self.session.execute(
                select(Rule.category, Rule.description, Rule.fraud_type).where(Rule.rule_id == rr.rule_id)
            )
            rule_info = rule_q.first()
            triggered_rules.append({
                "rule_id": rr.rule_id,
                "category": rule_info[0] if rule_info else rr.rule_id,
                "description": rule_info[1] if rule_info else "",
                "fraud_type": rule_info[2] if rule_info else "",
                "severity": float(rr.severity) if rr.severity else 0,
                "confidence": float(rr.confidence) if rr.confidence else 0,
                "evidence": rr.evidence,
                "details": rr.details,
            })
        context["triggered_rules"] = triggered_rules

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

    # ------------------------------------------------------------------
    # Investigate case
    # ------------------------------------------------------------------

    async def investigate_case(self, case_id: str) -> InvestigationResult:
        context = await self._gather_case_context(case_id)

        if "error" in context:
            return InvestigationResult(
                case_id=case_id,
                summary=context["error"],
                findings=[], risk_assessment="", recommended_actions=[],
                confidence=0, model_used="none",
            )

        system_prompt = (
            "You are an expert healthcare fraud, waste, and abuse (FWA) investigator.\n"
            "Analyze the case data and produce a structured investigation report.\n"
            "Be specific, reference the evidence, and provide actionable recommendations.\n"
            "Format your response as JSON with keys: summary, findings (array), "
            "risk_assessment, recommended_actions (array), confidence (0.0-1.0)."
        )

        prompt = (
            f"Investigate this FWA case:\n\n"
            f"{json.dumps(context, indent=2, default=str)}\n\n"
            f"Provide your investigation report as JSON."
        )

        response = await self._call_ollama(prompt, system_prompt)

        if response:
            try:
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
            result = self._generate_fallback_analysis(case_id, context)

        audit = AuditService(self.session)
        await audit.log_event(
            event_type="agent_investigation",
            actor=f"agent:{result.model_used}",
            action=f"Investigated case {case_id}",
            resource_type="case",
            resource_id=case_id,
            details={"model": result.model_used, "confidence": result.confidence},
        )

        return result

    def _generate_fallback_analysis(self, case_id: str, context: dict) -> InvestigationResult:
        rules = context.get("triggered_rules", [])
        claim = context.get("claim", {})
        provider = context.get("provider", {})
        risk = context.get("risk_score_detail", {})

        findings = []
        for r in rules:
            sev_label = "High" if r["severity"] >= 2.0 else "Medium" if r["severity"] >= 1.0 else "Low"
            findings.append(
                f"[{sev_label} Severity] {r.get('description') or r['rule_id']}: "
                f"{r.get('details', 'Triggered')} "
                f"(Confidence: {r['confidence']:.0%})"
            )

        amount = claim.get("amount_billed", 0)
        summary = (
            f"Case {case_id} involves a {context.get('claim_type', 'unknown')} claim "
            f"for ${amount:,.2f} with a risk score of {risk.get('total', 0):.1f}/100 "
            f"({risk.get('level', 'unknown')} risk). "
            f"{len(rules)} fraud detection rule(s) triggered."
        )
        if provider:
            summary += f" Provider: {provider.get('name', 'N/A')} ({provider.get('specialty', 'N/A')})."

        fraud_types = list({r.get("fraud_type", "") for r in rules if r.get("fraud_type")})

        actions = []
        if provider.get("oig_excluded"):
            actions.append("URGENT: Provider is OIG-excluded — report to compliance immediately")
        if any(r["severity"] >= 2.0 for r in rules):
            actions.append("Escalate for SIU review due to high-severity findings")
        if fraud_types:
            actions.append(f"Investigate {', '.join(ft.replace('_', ' ') for ft in fraud_types)} pattern(s)")
        if context.get("claim_type") == "medical":
            actions.append("Pull provider billing history for the past 12 months")
            actions.append("Verify medical necessity with clinical documentation")
        else:
            actions.append("Check prescription validity and prescriber DEA registration")
            actions.append("Review member controlled substance fill history")
        actions.append("Contact member for verification if applicable")

        risk_text = (
            f"Risk level: {risk.get('level', 'unknown').upper()}. "
            f"Total score: {risk.get('total', 0):.1f}/100. "
        )
        if fraud_types:
            risk_text += f"Detected fraud patterns: {', '.join(ft.replace('_', ' ') for ft in fraud_types)}. "
        if rules:
            top_severity = max(r["severity"] for r in rules)
            risk_text += f"Highest rule severity: {top_severity:.1f}/3.0."

        return InvestigationResult(
            case_id=case_id,
            summary=summary,
            findings=findings,
            risk_assessment=risk_text,
            recommended_actions=actions,
            confidence=0.75,
            model_used="data-engine",
        )

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    async def chat(self, message: str, case_id: str | None = None) -> ChatResponse:
        context_text = ""
        sources: list[str] = []

        if case_id:
            context = await self._gather_case_context(case_id)
            if "error" not in context:
                context_text = f"\n\nCase context:\n{json.dumps(context, indent=2, default=str)}"
                sources.append(f"case:{case_id}")
                for r in context.get("triggered_rules", []):
                    sources.append(f"rule:{r['rule_id']}")

        # Try LLM
        system_prompt = (
            "You are an AI assistant specializing in healthcare fraud, waste, and abuse (FWA) detection. "
            "You help investigators analyze cases, explain fraud patterns, and provide guidance. "
            "Be precise, reference specific data when available, and explain your reasoning."
        )
        prompt = f"{message}{context_text}"
        response = await self._call_ollama(prompt, system_prompt)

        if response:
            return ChatResponse(response=response, sources_cited=sources, model_used=self.model)

        # Data-driven fallback
        return await self._data_driven_chat(message, case_id, sources)

    # ------------------------------------------------------------------
    # Data-driven fallback chat
    # ------------------------------------------------------------------

    async def _data_driven_chat(
        self, message: str, case_id: str | None, sources: list[str]
    ) -> ChatResponse:
        msg = message.lower().strip()

        # Case-scoped questions
        if case_id:
            ctx = await self._gather_case_context(case_id)
            if "error" in ctx:
                return ChatResponse(response=ctx["error"], sources_cited=sources)
            return self._answer_case_question(msg, ctx, sources)

        # General questions
        if _matches_any(msg, ["how many", "total", "count", "overview", "summary", "stats", "statistics", "dashboard"]):
            return await self._answer_stats(sources)
        if _matches_any(msg, ["high risk", "critical", "top risk", "worst", "most severe", "riskiest"]):
            return await self._answer_top_risk(sources)
        if _matches_any(msg, ["rule", "what rules", "which rules", "detection", "trigger"]):
            return await self._answer_rules(sources)
        if _matches_any(msg, ["provider", "doctor", "npi"]):
            return await self._answer_provider(msg, sources)
        if _matches_any(msg, ["help", "what can you", "capabilities", "what do you"]):
            return self._answer_help(sources)

        return await self._answer_general(sources)

    def _answer_case_question(self, msg: str, ctx: dict, sources: list[str]) -> ChatResponse:
        rules = ctx.get("triggered_rules", [])
        claim = ctx.get("claim", {})
        provider = ctx.get("provider", {})
        risk = ctx.get("risk_score_detail", {})

        # Explain / analyze
        if _matches_any(msg, ["why", "explain", "what happened", "what's wrong", "what is wrong",
                               "tell me about", "analyze", "detail", "describe"]):
            lines = [f"**Case {ctx['case_id']}** — {ctx['risk_level'].upper()} risk (score: {ctx['risk_score']:.1f}/100)\n"]
            if claim:
                if ctx["claim_type"] == "medical":
                    lines.append(f"**Claim:** CPT {claim.get('cpt_code', 'N/A')}, "
                                 f"Dx {claim.get('diagnosis_primary', 'N/A')}, "
                                 f"billed ${claim.get('amount_billed', 0):,.2f}, "
                                 f"date {claim.get('service_date', 'N/A')}")
                else:
                    ctrl = "controlled substance" if claim.get("is_controlled") else "non-controlled"
                    lines.append(f"**Claim:** {claim.get('drug_name', 'N/A')} "
                                 f"(NDC {claim.get('ndc_code', 'N/A')}), "
                                 f"billed ${claim.get('amount_billed', 0):,.2f}, {ctrl}")
            if provider:
                oig = " **[OIG EXCLUDED]**" if provider.get("oig_excluded") else ""
                lines.append(f"\n**Provider:** {provider.get('name', 'N/A')} "
                             f"(NPI: {provider.get('npi', 'N/A')}, {provider.get('specialty', 'N/A')}){oig}")
            if rules:
                lines.append(f"\n**{len(rules)} rule(s) triggered:**")
                for r in sorted(rules, key=lambda x: x["severity"], reverse=True):
                    lines.append(f"- **{r['rule_id']}** — {r.get('description') or r.get('details', 'Triggered')} "
                                 f"(severity {r['severity']:.1f}, confidence {r['confidence']:.0%})")
            return ChatResponse(response="\n".join(lines), sources_cited=sources)

        # Rules
        if _matches_any(msg, ["rule", "trigger", "flag", "fired"]):
            if not rules:
                return ChatResponse(response=f"No rules triggered for case {ctx['case_id']}.", sources_cited=sources)
            lines = [f"**{len(rules)} rule(s) triggered for {ctx['case_id']}:**\n"]
            for r in sorted(rules, key=lambda x: x["severity"], reverse=True):
                lines.append(f"- **{r['rule_id']}** ({r.get('category', 'N/A')}): "
                             f"{r.get('description') or r.get('details', 'Triggered')} — "
                             f"severity {r['severity']:.1f}/3, confidence {r['confidence']:.0%}")
                if r.get("evidence"):
                    ev = ", ".join(f"{k}: {v}" for k, v in list(r["evidence"].items())[:3])
                    lines.append(f"  Evidence: {ev}")
            return ChatResponse(response="\n".join(lines), sources_cited=sources)

        # Risk / score
        if _matches_any(msg, ["risk", "score"]):
            contributions = risk.get("contributions", {})
            lines = [f"**Risk score for {ctx['case_id']}:** {risk.get('total', 0):.1f}/100 ({risk.get('level', 'N/A')})\n"]
            if contributions:
                lines.append("**Score breakdown by rule:**")
                for rule_id, contrib in sorted(
                    contributions.items(),
                    key=lambda x: x[1].get("contribution", 0) if isinstance(x[1], dict) else 0,
                    reverse=True,
                ):
                    if isinstance(contrib, dict):
                        lines.append(f"  - {rule_id}: +{contrib.get('contribution', 0):.2f} "
                                     f"(weight: {contrib.get('weight', 0)}, severity: {contrib.get('severity', 0):.1f})")
                    else:
                        lines.append(f"  - {rule_id}: +{float(contrib):.2f}")
            return ChatResponse(response="\n".join(lines), sources_cited=sources)

        # Recommendations
        if _matches_any(msg, ["recommend", "action", "should", "next step", "what to do"]):
            actions = []
            if provider and provider.get("oig_excluded"):
                actions.append("URGENT: Provider is OIG-excluded. Report to compliance immediately.")
            if any(r["severity"] >= 2.0 for r in rules):
                actions.append("Escalate to SIU for detailed review — high-severity findings present.")
            fraud_types = list({r.get("fraud_type", "") for r in rules if r.get("fraud_type")})
            if fraud_types:
                actions.append(f"Focus investigation on: {', '.join(ft.replace('_', ' ') for ft in fraud_types)}")
            actions.append("Review provider billing patterns and history.")
            actions.append("Verify medical necessity with supporting documentation.")
            actions.append("Contact member for verification if applicable.")
            return ChatResponse(
                response=f"**Recommended actions for {ctx['case_id']}:**\n\n"
                         + "\n".join(f"{i+1}. {a}" for i, a in enumerate(actions)),
                sources_cited=sources,
            )

        # Provider
        if _matches_any(msg, ["provider", "doctor", "who"]):
            if not provider:
                return ChatResponse(response="No provider information available for this case.", sources_cited=sources)
            oig = " **[OIG EXCLUDED]**" if provider.get("oig_excluded") else ""
            return ChatResponse(
                response=f"**Provider:** {provider.get('name', 'N/A')}\n"
                         f"- NPI: {provider.get('npi', 'N/A')}\n"
                         f"- Specialty: {provider.get('specialty', 'N/A')}{oig}",
                sources_cited=sources,
            )

        # Default case summary
        lines = [
            f"**{ctx['case_id']}** — {ctx['risk_level'].upper()} risk, score {ctx['risk_score']:.1f}/100, "
            f"priority {ctx.get('priority', 'N/A')}, status: {ctx.get('status', 'N/A')}",
            f"Claim type: {ctx['claim_type']}, Claim ID: {ctx['claim_id']}",
            f"Rules triggered: {len(rules)}",
        ]
        if claim:
            lines.append(f"Amount billed: ${claim.get('amount_billed', 0):,.2f}")
        lines.append("\nAsk me to *explain*, show *rules*, *risk score*, *recommendations*, or *provider* info.")
        return ChatResponse(response="\n".join(lines), sources_cited=sources)

    # --- General answers ---

    async def _answer_stats(self, sources: list[str]) -> ChatResponse:
        med = (await self.session.execute(select(func.count()).select_from(MedicalClaim))).scalar() or 0
        rx = (await self.session.execute(select(func.count()).select_from(PharmacyClaim))).scalar() or 0
        cases = (await self.session.execute(select(func.count()).select_from(InvestigationCase))).scalar() or 0
        active = (await self.session.execute(
            select(func.count()).select_from(InvestigationCase).where(
                InvestigationCase.status.in_(["open", "under_review", "escalated"])
            )
        )).scalar() or 0
        scored = (await self.session.execute(select(func.count()).select_from(RiskScore))).scalar() or 0
        high = (await self.session.execute(
            select(func.count()).select_from(RiskScore).where(RiskScore.risk_level.in_(["high", "critical"]))
        )).scalar() or 0
        lines = [
            "**Pipeline Overview:**\n",
            f"- **{med:,}** medical + **{rx:,}** pharmacy = **{med + rx:,}** total claims",
            f"- **{scored:,}** scored, **{med + rx - scored:,}** unscored",
            f"- **{high:,}** high/critical risk flagged",
            f"- **{cases:,}** investigation cases ({active:,} active)",
        ]
        return ChatResponse(response="\n".join(lines), sources_cited=sources)

    async def _answer_top_risk(self, sources: list[str]) -> ChatResponse:
        q = await self.session.execute(
            select(InvestigationCase)
            .where(InvestigationCase.status.in_(["open", "under_review", "escalated"]))
            .order_by(InvestigationCase.risk_score.desc())
            .limit(10)
        )
        cases = list(q.scalars())
        if not cases:
            return ChatResponse(response="No active investigation cases found.", sources_cited=sources)
        lines = [f"**Top {len(cases)} highest-risk active cases:**\n"]
        for c in cases:
            lines.append(f"- **{c.case_id}** — score {float(c.risk_score):.1f} ({c.risk_level}), "
                         f"priority {c.priority}, claim {c.claim_id}")
        lines.append("\nSelect a case above to investigate further.")
        return ChatResponse(response="\n".join(lines), sources_cited=sources)

    async def _answer_rules(self, sources: list[str]) -> ChatResponse:
        q = await self.session.execute(
            select(RuleResult.rule_id, func.count().label("cnt"))
            .where(RuleResult.triggered == True)
            .group_by(RuleResult.rule_id)
            .order_by(func.count().desc())
            .limit(10)
        )
        top = list(q)
        if not top:
            return ChatResponse(response="No rule results found yet. Run the pipeline first.", sources_cited=sources)
        rule_ids = [r[0] for r in top]
        rules_q = await self.session.execute(select(Rule).where(Rule.rule_id.in_(rule_ids)))
        rm = {r.rule_id: r for r in rules_q.scalars()}
        lines = ["**Most frequently triggered rules:**\n"]
        for rule_id, cnt in top:
            rule = rm.get(rule_id)
            desc = rule.description if rule else rule_id
            cat = rule.category if rule else "N/A"
            lines.append(f"- **{rule_id}** ({cat}): {desc} — triggered **{cnt}** times")
        return ChatResponse(response="\n".join(lines), sources_cited=sources)

    async def _answer_provider(self, msg: str, sources: list[str]) -> ChatResponse:
        npi_match = re.search(r'\b(\d{10})\b', msg)
        if npi_match:
            npi = npi_match.group(1)
            prov_q = await self.session.execute(select(Provider).where(Provider.npi == npi))
            prov = prov_q.scalar_one_or_none()
            if prov:
                flagged = (await self.session.execute(
                    select(func.count()).select_from(InvestigationCase).where(
                        InvestigationCase.claim_id.in_(
                            select(MedicalClaim.claim_id).where(MedicalClaim.provider_id == prov.id)
                        )
                    )
                )).scalar() or 0
                oig = " **[OIG EXCLUDED]**" if prov.oig_excluded else ""
                return ChatResponse(
                    response=f"**Provider: {prov.name}**{oig}\n- NPI: {prov.npi}\n"
                             f"- Specialty: {prov.specialty}\n- Active: {'Yes' if prov.is_active else 'No'}\n"
                             f"- Investigation cases: {flagged}",
                    sources_cited=sources,
                )
            return ChatResponse(response=f"No provider found with NPI {npi}.", sources_cited=sources)

        # Top providers by case count
        subq = (
            select(MedicalClaim.provider_id, func.count().label("cnt"))
            .where(MedicalClaim.claim_id.in_(select(InvestigationCase.claim_id)))
            .group_by(MedicalClaim.provider_id)
            .order_by(func.count().desc())
            .limit(5)
            .subquery()
        )
        q = await self.session.execute(
            select(Provider.npi, Provider.name, Provider.specialty, subq.c.cnt)
            .join(subq, Provider.id == subq.c.provider_id)
            .order_by(subq.c.cnt.desc())
        )
        top = list(q)
        if not top:
            return ChatResponse(response="No providers with investigation cases found.", sources_cited=sources)
        lines = ["**Providers with the most investigation cases:**\n"]
        for npi, name, spec, cnt in top:
            lines.append(f"- **{name}** (NPI: {npi}, {spec}) — {cnt} case(s)")
        return ChatResponse(response="\n".join(lines), sources_cited=sources)

    def _answer_help(self, sources: list[str]) -> ChatResponse:
        return ChatResponse(
            response=(
                "I'm your investigation assistant. Here's what I can help with:\n\n"
                "**With a case selected:**\n"
                "- \"Explain this case\" — full case breakdown\n"
                "- \"What rules triggered?\" — detailed rule analysis\n"
                "- \"Show risk score\" — score breakdown by rule\n"
                "- \"What should I do?\" — recommended next steps\n"
                "- \"Tell me about the provider\" — provider details\n"
                "- Click **Investigate** for a full structured analysis\n\n"
                "**General questions:**\n"
                "- \"Show me stats\" — pipeline overview\n"
                "- \"Top risk cases\" — highest-risk active cases\n"
                "- \"Most triggered rules\" — common fraud patterns\n"
                "- \"Provider with NPI 1234567890\" — provider lookup"
            ),
            sources_cited=sources,
        )

    async def _answer_general(self, sources: list[str]) -> ChatResponse:
        active = (await self.session.execute(
            select(func.count()).select_from(InvestigationCase).where(
                InvestigationCase.status.in_(["open", "under_review", "escalated"])
            )
        )).scalar() or 0
        return ChatResponse(
            response=(
                f"I can help you investigate fraud cases and analyze patterns. "
                f"There are currently **{active}** active investigation cases.\n\n"
                f"Try asking me:\n"
                f"- \"Show me stats\" for a pipeline overview\n"
                f"- \"Top risk cases\" for the highest-risk cases\n"
                f"- \"Which rules trigger most?\" for common fraud patterns\n\n"
                f"Or **select a case** above and ask me to explain it, show its rules, or recommend next steps."
            ),
            sources_cited=sources,
        )
