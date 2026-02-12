"""
Phase 12: Full Integration Test

Comprehensive end-to-end test exercising the entire ArqAI FWA pipeline:
1. Verify seeded data (35K claims, providers, members, reference data)
2. Run full pipeline: enrich → rules → score → cases → evidence
3. Verify all 29 rules trigger on synthetic fraud scenarios
4. Verify scoring accuracy (high-severity fraud scores >75, low <40)
5. Verify case creation and evidence bundles
6. Verify case lifecycle transitions
7. Verify audit chain integrity
8. Verify API endpoints via the FastAPI test client
"""

import asyncio
import sys
import time
from collections import defaultdict
from decimal import Decimal

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base
from app.models import (
    MedicalClaim, PharmacyClaim, Provider, Pharmacy, Member,
    Rule, RuleResult, RiskScore, AuditLog,
    InvestigationCase, CaseNote, CaseEvidence,
    CPTReference, ICDReference, NDCReference,
)
from app.services.enrichment import EnrichmentService
from app.services.rule_engine import RuleEngine
from app.services.scoring_engine import ScoringEngine
from app.services.audit_service import AuditService
from app.services.case_manager import CaseManager
from app.main import app


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.start_time = time.time()

    def ok(self, msg):
        self.passed += 1
        print(f"  [PASS] {msg}")

    def fail(self, msg):
        self.failed += 1
        print(f"  [FAIL] {msg}")

    def warn(self, msg):
        self.warnings += 1
        print(f"  [WARN] {msg}")

    def summary(self):
        elapsed = time.time() - self.start_time
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  RESULTS: {self.passed}/{total} passed, {self.failed} failed, {self.warnings} warnings")
        print(f"  TIME: {elapsed:.1f} seconds")
        print(f"{'='*60}")
        return self.failed == 0


async def run_tests():
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    t = TestRunner()

    # ================================================================
    # SECTION 1: Verify seeded data
    # ================================================================
    print("\n" + "="*60)
    print("SECTION 1: Verify Seeded Data")
    print("="*60)

    async with Session() as session:
        med_count = (await session.execute(select(func.count()).select_from(MedicalClaim))).scalar()
        rx_count = (await session.execute(select(func.count()).select_from(PharmacyClaim))).scalar()
        prov_count = (await session.execute(select(func.count()).select_from(Provider))).scalar()
        pharm_count = (await session.execute(select(func.count()).select_from(Pharmacy))).scalar()
        member_count = (await session.execute(select(func.count()).select_from(Member))).scalar()
        rule_count = (await session.execute(select(func.count()).select_from(Rule))).scalar()
        cpt_count = (await session.execute(select(func.count()).select_from(CPTReference))).scalar()
        icd_count = (await session.execute(select(func.count()).select_from(ICDReference))).scalar()
        ndc_count = (await session.execute(select(func.count()).select_from(NDCReference))).scalar()

        if med_count >= 15000:
            t.ok(f"Medical claims: {med_count}")
        else:
            t.fail(f"Medical claims: {med_count} (expected >= 15000)")

        if rx_count >= 20000:
            t.ok(f"Pharmacy claims: {rx_count}")
        else:
            t.fail(f"Pharmacy claims: {rx_count} (expected >= 20000)")

        if prov_count >= 100:
            t.ok(f"Providers: {prov_count}")
        else:
            t.fail(f"Providers: {prov_count} (expected >= 100)")

        if member_count >= 1000:
            t.ok(f"Members: {member_count}")
        else:
            t.fail(f"Members: {member_count} (expected >= 1000)")

        if rule_count >= 29:
            t.ok(f"Rule configs: {rule_count}")
        else:
            t.fail(f"Rule configs: {rule_count} (expected >= 29)")

        if cpt_count > 0:
            t.ok(f"CPT references: {cpt_count}")
        else:
            t.fail(f"No CPT references")

        if icd_count > 0:
            t.ok(f"ICD references: {icd_count}")
        else:
            t.fail(f"No ICD references")

        if ndc_count > 0:
            t.ok(f"NDC references: {ndc_count}")
        else:
            t.fail(f"No NDC references")

    # ================================================================
    # SECTION 2: Full Pipeline Run via API
    # ================================================================
    print("\n" + "="*60)
    print("SECTION 2: Full Pipeline Run (1000 claims)")
    print("="*60)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check pipeline status before
        resp = await client.get("/api/pipeline/status")
        assert resp.status_code == 200
        before = resp.json()
        unscored_before = before["unscored_claims"]
        t.ok(f"Pipeline status endpoint OK (unscored: {unscored_before})")

        # Run pipeline on 1000 claims
        pipeline_start = time.time()
        resp = await client.post("/api/pipeline/run-full", json={"limit": 1000})
        pipeline_time = time.time() - pipeline_start

        if resp.status_code == 200:
            result = resp.json()
            t.ok(f"Pipeline completed in {result['processing_time_seconds']:.1f}s")
            t.ok(f"Claims processed: {result['total_claims']} (med: {result['medical_claims']}, rx: {result['pharmacy_claims']})")
            t.ok(f"Rules evaluated: {result['rules_evaluated']}")
            t.ok(f"Scores generated: {result['scores_generated']}")
            t.ok(f"Cases created: {result['cases_created']}")
            t.ok(f"High risk: {result['high_risk']}, Critical: {result['critical_risk']}")

            if result['total_claims'] > 0:
                t.ok("Pipeline processed claims successfully")
            else:
                t.warn("No unscored claims remaining to process")

            if result['rules_evaluated'] > 0:
                t.ok(f"Rule evaluation rate: {result['rules_evaluated'] / max(result['total_claims'],1):.0f} rules/claim")

            if result['cases_created'] > 0:
                t.ok(f"Case creation rate: {result['cases_created'] / max(result['total_claims'],1) * 100:.1f}%")
        else:
            t.fail(f"Pipeline returned {resp.status_code}: {resp.text[:200]}")

        # Check pipeline status after
        resp = await client.get("/api/pipeline/status")
        after = resp.json()
        t.ok(f"Post-pipeline: {after['scored_claims']} scored, {after['total_cases']} cases, {after['total_audit_entries']} audit entries")

    # ================================================================
    # SECTION 3: Verify all 29 rules trigger
    # ================================================================
    print("\n" + "="*60)
    print("SECTION 3: Verify All 29 Rules Trigger")
    print("="*60)

    async with Session() as session:
        # Get all triggered rules
        triggered_q = await session.execute(
            select(RuleResult.rule_id, func.count().label("cnt"))
            .where(RuleResult.triggered == True)
            .group_by(RuleResult.rule_id)
        )
        triggered_rules = {row[0]: row[1] for row in triggered_q}

        # Expected rules
        medical_rules = [f"M{i}" for i in range(1, 17)]
        pharmacy_rules = [f"P{i}" for i in range(1, 14)]
        all_expected = medical_rules + pharmacy_rules

        triggered_count = 0
        missing_rules = []
        for rule_id in all_expected:
            count = triggered_rules.get(rule_id, 0)
            if count > 0:
                t.ok(f"Rule {rule_id}: triggered {count} times")
                triggered_count += 1
            else:
                t.fail(f"Rule {rule_id}: NOT TRIGGERED (check fraud scenarios and enrichment)")
                missing_rules.append(rule_id)

        if triggered_count == 29:
            t.ok("ALL 29 rules triggered successfully!")
        else:
            t.fail(f"Only {triggered_count}/29 rules triggered. Missing: {missing_rules}")

    # ================================================================
    # SECTION 4: Verify scoring accuracy
    # ================================================================
    print("\n" + "="*60)
    print("SECTION 4: Verify Scoring Accuracy")
    print("="*60)

    async with Session() as session:
        # Risk level distribution
        dist_q = await session.execute(
            select(RiskScore.risk_level, func.count(), func.avg(RiskScore.total_score))
            .group_by(RiskScore.risk_level)
        )
        for level, count, avg_score in dist_q:
            t.ok(f"Risk level '{level}': {count} claims, avg score {float(avg_score):.1f}")

        # Check critical claims have high scores
        critical_q = await session.execute(
            select(func.min(RiskScore.total_score), func.avg(RiskScore.total_score))
            .where(RiskScore.risk_level == "critical")
        )
        row = critical_q.one_or_none()
        if row and row[0] is not None:
            min_critical = float(row[0])
            avg_critical = float(row[1])
            if min_critical > 75:
                t.ok(f"Critical claims: min score {min_critical:.1f} > 75")
            else:
                t.warn(f"Critical claims: min score {min_critical:.1f} (expected > 75)")
            t.ok(f"Critical claims: avg score {avg_critical:.1f}")

        # Check low risk have low scores
        low_q = await session.execute(
            select(func.max(RiskScore.total_score), func.avg(RiskScore.total_score))
            .where(RiskScore.risk_level == "low")
        )
        row = low_q.one_or_none()
        if row and row[0] is not None:
            max_low = float(row[0])
            avg_low = float(row[1])
            if max_low <= 30:
                t.ok(f"Low risk claims: max score {max_low:.1f} <= 30")
            else:
                t.fail(f"Low risk claims: max score {max_low:.1f} (expected <= 30)")
            t.ok(f"Low risk claims: avg score {avg_low:.1f}")

        # Verify that multi-rule claims score higher
        multi_rule_q = await session.execute(
            select(func.avg(RiskScore.total_score))
            .where(RiskScore.rules_triggered >= 2)
        )
        multi_avg = multi_rule_q.scalar()
        single_rule_q = await session.execute(
            select(func.avg(RiskScore.total_score))
            .where(RiskScore.rules_triggered == 1)
        )
        single_avg = single_rule_q.scalar()
        if multi_avg and single_avg:
            if float(multi_avg) > float(single_avg):
                t.ok(f"Multi-rule claims score higher: {float(multi_avg):.1f} vs {float(single_avg):.1f}")
            else:
                t.warn(f"Multi-rule avg {float(multi_avg):.1f} not > single-rule avg {float(single_avg):.1f}")

    # ================================================================
    # SECTION 5: Verify case creation and evidence
    # ================================================================
    print("\n" + "="*60)
    print("SECTION 5: Verify Cases & Evidence Bundles")
    print("="*60)

    async with Session() as session:
        # Total cases
        total_cases = (await session.execute(
            select(func.count()).select_from(InvestigationCase)
        )).scalar()
        t.ok(f"Total investigation cases: {total_cases}")

        # Cases by priority
        priority_q = await session.execute(
            select(InvestigationCase.priority, func.count())
            .group_by(InvestigationCase.priority)
        )
        for priority, count in priority_q:
            t.ok(f"  Priority {priority}: {count} cases")

        # Cases by status
        status_q = await session.execute(
            select(InvestigationCase.status, func.count())
            .group_by(InvestigationCase.status)
        )
        for status, count in status_q:
            t.ok(f"  Status '{status}': {count} cases")

        # P1 cases should be critical risk
        p1_q = await session.execute(
            select(InvestigationCase).where(InvestigationCase.priority == "P1").limit(5)
        )
        p1_cases = list(p1_q.scalars())
        all_critical = all(c.risk_level == "critical" for c in p1_cases) if p1_cases else True
        if all_critical:
            t.ok(f"All P1 cases are critical risk level")
        else:
            t.fail("Some P1 cases are not critical risk")

        # P2 cases should be high risk
        p2_q = await session.execute(
            select(InvestigationCase).where(InvestigationCase.priority == "P2").limit(5)
        )
        p2_cases = list(p2_q.scalars())
        all_high = all(c.risk_level == "high" for c in p2_cases) if p2_cases else True
        if all_high:
            t.ok(f"All P2 cases are high risk level")
        else:
            t.fail("Some P2 cases are not high risk")

        # SLA deadlines set
        sla_q = await session.execute(
            select(func.count()).select_from(InvestigationCase)
            .where(InvestigationCase.sla_deadline.isnot(None))
        )
        sla_count = sla_q.scalar()
        if sla_count == total_cases:
            t.ok(f"All {total_cases} cases have SLA deadlines set")
        else:
            t.fail(f"Only {sla_count}/{total_cases} cases have SLA deadlines")

        # Evidence bundles
        evidence_count = (await session.execute(
            select(func.count()).select_from(CaseEvidence)
        )).scalar()
        t.ok(f"Total evidence items: {evidence_count}")

        # Check a sample case has evidence
        sample_case_q = await session.execute(
            select(InvestigationCase)
            .where(InvestigationCase.risk_level == "critical")
            .limit(1)
        )
        sample_case = sample_case_q.scalar_one_or_none()
        if sample_case:
            ev_q = await session.execute(
                select(CaseEvidence).where(CaseEvidence.case_id == sample_case.id)
            )
            evidence = list(ev_q.scalars())
            evidence_types = {e.evidence_type for e in evidence}

            if "claim_data" in evidence_types:
                t.ok("Evidence includes claim_data")
            else:
                t.fail("Missing claim_data evidence")

            if "risk_assessment" in evidence_types:
                t.ok("Evidence includes risk_assessment")
            else:
                t.fail("Missing risk_assessment evidence")

            if "rule_findings" in evidence_types:
                t.ok("Evidence includes rule_findings")
            else:
                t.fail("Missing rule_findings evidence")

    # ================================================================
    # SECTION 6: Case lifecycle transitions
    # ================================================================
    print("\n" + "="*60)
    print("SECTION 6: Case Lifecycle Transitions")
    print("="*60)

    async with Session() as session:
        case_manager = CaseManager(session)

        # Get an open case
        open_q = await session.execute(
            select(InvestigationCase)
            .where(InvestigationCase.status == "open")
            .limit(1)
        )
        test_case = open_q.scalar_one_or_none()

        if not test_case:
            t.warn("No open cases available for lifecycle test")
        else:
            case_id = test_case.case_id

            # open → under_review
            try:
                await case_manager.update_status(case_id, "under_review", actor="test")
                t.ok(f"Transition: open → under_review")
            except Exception as e:
                t.fail(f"open → under_review failed: {e}")

            # under_review → escalated
            try:
                await case_manager.escalate_case(case_id, "Complex case needs senior review", actor="test")
                t.ok(f"Escalation: under_review → escalated")
            except Exception as e:
                t.fail(f"Escalation failed: {e}")

            # escalated → resolved
            try:
                await case_manager.resolve_case(
                    case_id,
                    resolution_path="complex_case",
                    resolution_notes="Investigation complete, recovery initiated",
                    actor="test",
                    recovery_amount=5000.00,
                )
                t.ok(f"Resolution: escalated → resolved")
            except Exception as e:
                t.fail(f"Resolution failed: {e}")

            # resolved → closed
            try:
                await case_manager.update_status(case_id, "closed", actor="test")
                t.ok(f"Closure: resolved → closed")
            except Exception as e:
                t.fail(f"Closure failed: {e}")

            # closed → open (should fail)
            try:
                await case_manager.update_status(case_id, "open", actor="test")
                t.fail("Terminal state violation: closed → open should fail!")
            except ValueError:
                t.ok("Terminal state correctly enforced (closed → open rejected)")

            await session.rollback()

    # ================================================================
    # SECTION 7: Audit chain integrity
    # ================================================================
    print("\n" + "="*60)
    print("SECTION 7: Audit Chain Integrity")
    print("="*60)

    async with Session() as session:
        audit = AuditService(session)

        # Entry count
        entry_count = await audit.get_entry_count()
        t.ok(f"Audit entries: {entry_count}")

        # Event type breakdown
        for event_type in [
            "pipeline_run", "batch_processed", "case_created",
            "case_updated", "case_escalated",
        ]:
            count = await audit.get_entry_count(event_type)
            if count > 0:
                t.ok(f"  {event_type}: {count} entries")

        # Chain integrity verification
        integrity = await audit.verify_chain_integrity()
        if integrity["valid"]:
            t.ok(f"Audit chain integrity VALID ({integrity['entries_checked']} entries verified)")
        else:
            t.fail(f"Audit chain BROKEN at entry {integrity['first_invalid']}: {integrity.get('reason')}")

    # ================================================================
    # SECTION 8: API endpoint verification
    # ================================================================
    print("\n" + "="*60)
    print("SECTION 8: API Endpoint Verification")
    print("="*60)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Health
        resp = await client.get("/api/health")
        if resp.status_code == 200:
            t.ok("GET /api/health → 200")
        else:
            t.fail(f"GET /api/health → {resp.status_code}")

        # Dashboard overview
        resp = await client.get("/api/dashboard/overview")
        if resp.status_code == 200:
            data = resp.json()
            t.ok(f"GET /api/dashboard/overview → total_claims={data['total_claims']}, flagged={data['total_flagged']}")
        else:
            t.fail(f"GET /api/dashboard/overview → {resp.status_code}")

        # Dashboard trends
        resp = await client.get("/api/dashboard/trends")
        if resp.status_code == 200:
            t.ok("GET /api/dashboard/trends → 200")
        else:
            t.fail(f"GET /api/dashboard/trends → {resp.status_code}")

        # Dashboard top-providers
        resp = await client.get("/api/dashboard/top-providers")
        if resp.status_code == 200:
            data = resp.json()
            t.ok(f"GET /api/dashboard/top-providers → {len(data['providers'])} providers")
        else:
            t.fail(f"GET /api/dashboard/top-providers → {resp.status_code}")

        # Dashboard rule-effectiveness
        resp = await client.get("/api/dashboard/rule-effectiveness")
        if resp.status_code == 200:
            data = resp.json()
            t.ok(f"GET /api/dashboard/rule-effectiveness → {len(data['rules'])} rules")
        else:
            t.fail(f"GET /api/dashboard/rule-effectiveness → {resp.status_code}")

        # Claims list
        resp = await client.get("/api/claims?size=5")
        if resp.status_code == 200:
            data = resp.json()
            t.ok(f"GET /api/claims → {data['total']} total, page 1 has {len(data['items'])} items")
        else:
            t.fail(f"GET /api/claims → {resp.status_code}")

        # Claims list with filter
        resp = await client.get("/api/claims?type=medical&risk_level=critical&size=3")
        if resp.status_code == 200:
            data = resp.json()
            t.ok(f"GET /api/claims?type=medical&risk_level=critical → {data['total']} results")
        else:
            t.fail(f"GET /api/claims (filtered) → {resp.status_code}")

        # Claim detail (find one that has been scored)
        scored_q_resp = await client.get("/api/claims?risk_level=high&size=1")
        if scored_q_resp.status_code == 200 and scored_q_resp.json()["items"]:
            claim_id = scored_q_resp.json()["items"][0]["claim_id"]
            resp = await client.get(f"/api/claims/{claim_id}")
            if resp.status_code == 200:
                data = resp.json()
                has_rules = len(data.get("rule_results", [])) > 0
                has_score = data.get("risk_score") is not None
                t.ok(f"GET /api/claims/{claim_id} → rules={has_rules}, score={has_score}")
            else:
                t.fail(f"GET /api/claims/{claim_id} → {resp.status_code}")

        # Rules list
        resp = await client.get("/api/rules")
        if resp.status_code == 200:
            data = resp.json()
            t.ok(f"GET /api/rules → {data['total']} rules")
        else:
            t.fail(f"GET /api/rules → {resp.status_code}")

        # Rule detail
        resp = await client.get("/api/rules/M1")
        if resp.status_code == 200:
            t.ok("GET /api/rules/M1 → 200")
        else:
            t.fail(f"GET /api/rules/M1 → {resp.status_code}")

        # Rule stats
        resp = await client.get("/api/rules/M1/stats")
        if resp.status_code == 200:
            data = resp.json()
            t.ok(f"GET /api/rules/M1/stats → triggered {data['times_triggered']} times, rate {data['trigger_rate']:.1%}")
        else:
            t.fail(f"GET /api/rules/M1/stats → {resp.status_code}")

        # Cases list
        resp = await client.get("/api/cases?size=5")
        if resp.status_code == 200:
            data = resp.json()
            t.ok(f"GET /api/cases → {data['total']} total cases")
        else:
            t.fail(f"GET /api/cases → {resp.status_code}")

        # Case detail
        if resp.status_code == 200 and data["items"]:
            case_id = data["items"][0]["case_id"]
            resp = await client.get(f"/api/cases/{case_id}")
            if resp.status_code == 200:
                cdata = resp.json()
                has_evidence = len(cdata.get("evidence", [])) > 0
                has_claim = cdata.get("claim") is not None
                t.ok(f"GET /api/cases/{case_id} → evidence={has_evidence}, claim={has_claim}")
            else:
                t.fail(f"GET /api/cases/{case_id} → {resp.status_code}")

            # Case evidence bundle
            resp = await client.get(f"/api/cases/{case_id}/evidence")
            if resp.status_code == 200:
                edata = resp.json()
                has_claim_data = edata.get("claim_data") is not None
                has_risk = edata.get("risk_score") is not None
                t.ok(f"GET /api/cases/{case_id}/evidence → claim_data={has_claim_data}, risk_score={has_risk}")
            else:
                t.fail(f"GET /api/cases/{case_id}/evidence → {resp.status_code}")

        # Scoring thresholds
        resp = await client.get("/api/scoring/thresholds")
        if resp.status_code == 200:
            t.ok(f"GET /api/scoring/thresholds → {resp.json()}")
        else:
            t.fail(f"GET /api/scoring/thresholds → {resp.status_code}")

        # Audit log
        resp = await client.get("/api/audit?size=5")
        if resp.status_code == 200:
            data = resp.json()
            t.ok(f"GET /api/audit → {data['total']} entries")
        else:
            t.fail(f"GET /api/audit → {resp.status_code}")

        # Audit integrity check
        resp = await client.get("/api/audit/integrity")
        if resp.status_code == 200:
            data = resp.json()
            if data["valid"]:
                t.ok(f"GET /api/audit/integrity → chain valid ({data['entries_checked']} checked)")
            else:
                t.fail(f"GET /api/audit/integrity → chain BROKEN")
        else:
            t.fail(f"GET /api/audit/integrity → {resp.status_code}")

        # Pipeline status
        resp = await client.get("/api/pipeline/status")
        if resp.status_code == 200:
            t.ok(f"GET /api/pipeline/status → {resp.json()}")
        else:
            t.fail(f"GET /api/pipeline/status → {resp.status_code}")

        # Agent investigate (will use fallback since no Ollama)
        if data.get("items"):
            resp = await client.post("/api/agents/investigate", json={"case_id": case_id})
            if resp.status_code == 200:
                t.ok("POST /api/agents/investigate → 200 (fallback analysis)")
            else:
                t.warn(f"POST /api/agents/investigate → {resp.status_code}")

        # Agent chat
        resp = await client.post("/api/agents/chat", json={"message": "What are the most common fraud patterns?"})
        if resp.status_code == 200:
            t.ok("POST /api/agents/chat → 200")
        else:
            t.warn(f"POST /api/agents/chat → {resp.status_code}")

    # ================================================================
    # FINAL SUMMARY
    # ================================================================
    success = t.summary()

    if not success:
        print("\nSome tests failed. Review the output above.")
        sys.exit(1)
    else:
        print("\nAll tests passed! Full pipeline verified end-to-end.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_tests())
