"""
End-to-end pipeline integration test.

Tests: DB connection → Enrichment → Rule Engine → Scoring → Audit
against the seeded data (35K claims with tagged fraud scenarios).
"""

import asyncio
import sys
from collections import defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base
from app.models import (
    MedicalClaim, PharmacyClaim, Provider, Pharmacy, Member,
    Rule, RuleResult, RiskScore, AuditLog,
    CPTReference, ICDReference, NDCReference,
)
from app.services.enrichment import EnrichmentService
from app.services.rule_engine import RuleEngine
from app.services.scoring_engine import ScoringEngine
from app.services.audit_service import AuditService


async def run_tests():
    engine = create_async_engine(settings.database_url, echo=False)
    SessionFactory = async_sessionmaker(engine, expire_on_commit=False)

    passed = 0
    failed = 0

    def ok(msg):
        nonlocal passed
        passed += 1
        print(f"  [PASS] {msg}")

    def fail(msg):
        nonlocal failed
        failed += 1
        print(f"  [FAIL] {msg}")

    async with SessionFactory() as session:
        # ================================================================
        # TEST 1: Verify seeded data is present
        # ================================================================
        print("\n=== TEST 1: Verify seeded data ===")
        med_count = (await session.execute(select(func.count()).select_from(MedicalClaim))).scalar()
        pharm_count = (await session.execute(select(func.count()).select_from(PharmacyClaim))).scalar()
        prov_count = (await session.execute(select(func.count()).select_from(Provider))).scalar()
        mem_count = (await session.execute(select(func.count()).select_from(Member))).scalar()
        rule_count = (await session.execute(select(func.count()).select_from(Rule))).scalar()
        cpt_count = (await session.execute(select(func.count()).select_from(CPTReference))).scalar()
        icd_count = (await session.execute(select(func.count()).select_from(ICDReference))).scalar()
        ndc_count = (await session.execute(select(func.count()).select_from(NDCReference))).scalar()

        if med_count > 10000: ok(f"Medical claims: {med_count}")
        else: fail(f"Medical claims only {med_count}, expected > 10000")

        if pharm_count > 10000: ok(f"Pharmacy claims: {pharm_count}")
        else: fail(f"Pharmacy claims only {pharm_count}, expected > 10000")

        if prov_count >= 200: ok(f"Providers: {prov_count}")
        else: fail(f"Providers {prov_count}, expected >= 200")

        if mem_count >= 2000: ok(f"Members: {mem_count}")
        else: fail(f"Members {mem_count}, expected >= 2000")

        if rule_count >= 29: ok(f"Rules: {rule_count}")
        else: fail(f"Rules {rule_count}, expected >= 29")

        if cpt_count > 0: ok(f"CPT codes: {cpt_count}")
        else: fail("No CPT reference data")

        if icd_count > 0: ok(f"ICD codes: {icd_count}")
        else: fail("No ICD reference data")

        if ndc_count > 0: ok(f"NDC codes: {ndc_count}")
        else: fail("No NDC reference data")

        # ================================================================
        # TEST 2: Enrichment Service — Medical
        # ================================================================
        print("\n=== TEST 2: Enrichment — Medical Claims ===")
        enrichment = EnrichmentService(session)

        # Get a small batch of medical claims (10 random)
        med_q = await session.execute(
            select(MedicalClaim).limit(10)
        )
        med_claims = list(med_q.scalars())

        try:
            enriched_med = await enrichment.enrich_medical_batch(med_claims)
            ok(f"Enriched {len(enriched_med)} medical claims")
            sample = enriched_med[0]
            if sample.claim_id: ok(f"  claim_id: {sample.claim_id}")
            else: fail("  Missing claim_id")
            if sample.cpt_description: ok(f"  CPT lookup: {sample.cpt_code} → {sample.cpt_description[:40]}")
            else: ok("  CPT description not in reference (may be expected)")
            if sample.provider_npi: ok(f"  Provider NPI: {sample.provider_npi}")
            else: fail("  Missing provider NPI")
            ok(f"  Member claims 30d: {sample.member_claims_30d}")
            ok(f"  Provider claims 30d: {sample.provider_claims_30d}")
        except Exception as e:
            fail(f"Enrichment failed: {e}")
            import traceback
            traceback.print_exc()

        # ================================================================
        # TEST 3: Enrichment Service — Pharmacy
        # ================================================================
        print("\n=== TEST 3: Enrichment — Pharmacy Claims ===")
        pharm_q = await session.execute(
            select(PharmacyClaim).limit(10)
        )
        pharm_claims = list(pharm_q.scalars())

        try:
            enriched_pharm = await enrichment.enrich_pharmacy_batch(pharm_claims)
            ok(f"Enriched {len(enriched_pharm)} pharmacy claims")
            sample = enriched_pharm[0]
            if sample.claim_id: ok(f"  claim_id: {sample.claim_id}")
            else: fail("  Missing claim_id")
            if sample.ndc_proprietary_name: ok(f"  NDC lookup: {sample.ndc_code} → {sample.ndc_proprietary_name[:40]}")
            else: ok("  NDC proprietary name not in reference (may be expected)")
            if sample.prescriber_name: ok(f"  Prescriber: {sample.prescriber_name}")
            else: ok("  Prescriber not found (may be expected for some claims)")
        except Exception as e:
            fail(f"Pharmacy enrichment failed: {e}")
            import traceback
            traceback.print_exc()

        # ================================================================
        # TEST 4: Rule Engine Discovery
        # ================================================================
        print("\n=== TEST 4: Rule Engine — Rule Discovery ===")
        rule_engine = RuleEngine(session)
        await rule_engine.load_rules()
        await rule_engine.load_configs()

        total_rules = rule_engine.get_rule_count()
        if total_rules >= 29: ok(f"Discovered {total_rules} rules")
        else: fail(f"Only discovered {total_rules} rules, expected >= 29")

        medical_rules = [r for r in rule_engine.rules.values() if r.claim_type == "medical"]
        pharmacy_rules = [r for r in rule_engine.rules.values() if r.claim_type == "pharmacy"]
        if len(medical_rules) >= 16: ok(f"  Medical rules: {len(medical_rules)}")
        else: fail(f"  Only {len(medical_rules)} medical rules")
        if len(pharmacy_rules) >= 13: ok(f"  Pharmacy rules: {len(pharmacy_rules)}")
        else: fail(f"  Only {len(pharmacy_rules)} pharmacy rules")

        for rule_id, cfg in rule_engine.configs.items():
            if not cfg.get("enabled"):
                print(f"  WARNING: Rule {rule_id} is disabled")

        # ================================================================
        # TEST 5: Rule Engine — Evaluate medical claims
        # ================================================================
        print("\n=== TEST 5: Rule Engine — Evaluate Medical Claims ===")
        try:
            # Evaluate the enriched claims
            med_results = {}
            for ec in enriched_med:
                results = await rule_engine.evaluate_claim(ec)
                med_results[ec.claim_id] = results

            total_evals = sum(len(r) for r in med_results.values())
            triggered = sum(1 for rs in med_results.values() for r in rs if r.triggered)
            ok(f"Evaluated {len(med_results)} medical claims → {total_evals} rule checks, {triggered} triggered")

            # Show triggered rules
            for claim_id, results in med_results.items():
                for r in results:
                    if r.triggered:
                        print(f"    {claim_id}: {r.rule_id} triggered (severity={r.severity}, confidence={r.confidence})")
        except Exception as e:
            fail(f"Medical rule evaluation failed: {e}")
            import traceback
            traceback.print_exc()

        # ================================================================
        # TEST 6: Rule Engine — Evaluate pharmacy claims
        # ================================================================
        print("\n=== TEST 6: Rule Engine — Evaluate Pharmacy Claims ===")
        try:
            pharm_results = {}
            for ec in enriched_pharm:
                results = await rule_engine.evaluate_claim(ec)
                pharm_results[ec.claim_id] = results

            total_evals = sum(len(r) for r in pharm_results.values())
            triggered = sum(1 for rs in pharm_results.values() for r in rs if r.triggered)
            ok(f"Evaluated {len(pharm_results)} pharmacy claims → {total_evals} rule checks, {triggered} triggered")

            for claim_id, results in pharm_results.items():
                for r in results:
                    if r.triggered:
                        print(f"    {claim_id}: {r.rule_id} triggered (severity={r.severity}, confidence={r.confidence})")
        except Exception as e:
            fail(f"Pharmacy rule evaluation failed: {e}")
            import traceback
            traceback.print_exc()

        # ================================================================
        # TEST 7: Scoring Engine
        # ================================================================
        print("\n=== TEST 7: Scoring Engine ===")
        scorer = ScoringEngine(session)
        try:
            # Score medical claims
            for claim_id, results in med_results.items():
                score = await scorer.score_claim(claim_id, "medical", results)
                print(f"    {claim_id}: score={score.total_score}, level={score.risk_level}, rules_triggered={score.rules_triggered}")

            # Score pharmacy claims
            for claim_id, results in pharm_results.items():
                score = await scorer.score_claim(claim_id, "pharmacy", results)
                print(f"    {claim_id}: score={score.total_score}, level={score.risk_level}, rules_triggered={score.rules_triggered}")

            ok("Scoring engine working")
        except Exception as e:
            fail(f"Scoring failed: {e}")
            import traceback
            traceback.print_exc()

        # ================================================================
        # TEST 8: Audit Service
        # ================================================================
        print("\n=== TEST 8: Audit Service (ArqMesh) ===")
        audit = AuditService(session)
        try:
            # Write a few test entries
            e1 = await audit.log_event(
                event_type="test_event",
                actor="test_pipeline",
                action="Pipeline integration test started",
                details={"test": True},
            )
            ok(f"Audit entry 1: event_id={e1.event_id}, hash={e1.current_hash[:16]}...")

            e2 = await audit.log_event(
                event_type="test_event",
                actor="test_pipeline",
                action="Pipeline integration test entry 2",
                details={"entry": 2},
            )
            ok(f"Audit entry 2: event_id={e2.event_id}, prev_hash={e2.previous_hash[:16] if e2.previous_hash else 'None'}...")

            # Verify chain integrity
            integrity = await audit.verify_chain_integrity()
            if integrity["valid"]:
                ok(f"Chain integrity: VALID ({integrity['entries_checked']} entries)")
            else:
                fail(f"Chain integrity: INVALID at entry {integrity['first_invalid']} - {integrity.get('reason')}")

            # Query entries
            entries = await audit.get_entries(event_type="test_event")
            if len(entries) >= 2:
                ok(f"Query returned {len(entries)} test entries")
            else:
                fail(f"Query returned only {len(entries)} entries, expected >= 2")

            count = await audit.get_entry_count()
            ok(f"Total audit entries: {count}")

            # Rollback test entries to keep DB clean
            await session.rollback()
            ok("Test audit entries rolled back")
        except Exception as e:
            fail(f"Audit service failed: {e}")
            import traceback
            traceback.print_exc()

        # ================================================================
        # TEST 9: Large-scale rule evaluation (100 claims per type)
        # ================================================================
        print("\n=== TEST 9: Large-scale evaluation — 100 claims per type ===")
        try:
            # Fresh enrichment service (previous one's caches expired after rollback)
            enrichment = EnrichmentService(session)

            # Medical
            med_q = await session.execute(select(MedicalClaim).limit(100))
            med_batch = list(med_q.scalars())
            enriched_batch = await enrichment.enrich_medical_batch(med_batch)
            ok(f"Enriched {len(enriched_batch)} medical claims")

            triggered_counts = defaultdict(int)
            for ec in enriched_batch:
                results = await rule_engine.evaluate_claim(ec)
                for r in results:
                    if r.triggered:
                        triggered_counts[r.rule_id] += 1

            ok(f"Rules triggered on 100 medical claims:")
            for rid, cnt in sorted(triggered_counts.items()):
                print(f"    {rid}: {cnt} triggers")

            # Pharmacy
            pharm_q = await session.execute(select(PharmacyClaim).limit(100))
            pharm_batch = list(pharm_q.scalars())
            enriched_pharm_batch = await enrichment.enrich_pharmacy_batch(pharm_batch)
            ok(f"Enriched {len(enriched_pharm_batch)} pharmacy claims")

            triggered_counts = defaultdict(int)
            for ec in enriched_pharm_batch:
                results = await rule_engine.evaluate_claim(ec)
                for r in results:
                    if r.triggered:
                        triggered_counts[r.rule_id] += 1

            ok(f"Rules triggered on 100 pharmacy claims:")
            for rid, cnt in sorted(triggered_counts.items()):
                print(f"    {rid}: {cnt} triggers")

        except Exception as e:
            fail(f"Large-scale evaluation failed: {e}")
            import traceback
            traceback.print_exc()

    await engine.dispose()

    # ================================================================
    # SUMMARY
    # ================================================================
    print(f"\n{'='*50}")
    print(f"RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
