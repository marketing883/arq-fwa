"""
ARQ worker entrypoint — processes pipeline jobs from the Redis queue.

Run with: python worker.py
"""

import asyncio
import json
import logging
import time

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("worker")


async def process_pipeline_job(job_data: dict, engine, SessionMaker):
    """Execute a pipeline job — mirrors the logic in pipeline.py run_full."""
    from app.models import MedicalClaim, PharmacyClaim, RiskScore, Workspace
    from app.models.pipeline_run import PipelineRun
    from app.services.enrichment import EnrichmentService
    from app.services.rule_engine import RuleEngine
    from app.services.scoring_engine import ScoringEngine
    from app.services.case_manager import CaseManager
    from app.services.audit_service import AuditService
    from app.services.data_quality import DataQualityService
    from app.services.job_queue import update_job_status

    job_id = job_data["job_id"]
    workspace_id = job_data.get("workspace_id")
    limit = int(job_data.get("limit", 1000))
    batch_id = job_data.get("batch_id") or f"PIPE-{job_id}"

    await update_job_status(job_id, status="running", phase="loading", progress=0)
    t_start = time.time()

    async with SessionMaker() as db:
        try:
            ws_id = None
            if workspace_id:
                ws_result = await db.execute(select(Workspace).where(Workspace.workspace_id == workspace_id))
                ws = ws_result.scalar_one_or_none()
                if ws:
                    ws_id = ws.id

            # Load claims
            scored_med_ids = select(RiskScore.claim_id).where(RiskScore.claim_type == "medical")
            scored_rx_ids = select(RiskScore.claim_id).where(RiskScore.claim_type == "pharmacy")

            med_q = select(MedicalClaim).where(MedicalClaim.claim_id.not_in(scored_med_ids))
            if ws_id is not None:
                med_q = med_q.where(MedicalClaim.workspace_id == ws_id)
            med_q = med_q.limit(limit)

            rx_q = select(PharmacyClaim).where(PharmacyClaim.claim_id.not_in(scored_rx_ids))
            if ws_id is not None:
                rx_q = rx_q.where(PharmacyClaim.workspace_id == ws_id)
            rx_q = rx_q.limit(limit)

            med_claims = list((await db.execute(med_q)).scalars())
            rx_claims = list((await db.execute(rx_q)).scalars())
            total = len(med_claims) + len(rx_claims)

            await update_job_status(job_id, phase="loading", progress=100, claims_processed=0)

            if total == 0:
                await update_job_status(job_id, status="completed", phase="done", progress=100, result={"total_claims": 0})
                return

            # Data quality
            await update_job_status(job_id, phase="quality", progress=0)
            dq = DataQualityService(db)
            med_report = await dq.validate_medical_claims(med_claims)
            rx_report = await dq.validate_pharmacy_claims(rx_claims)
            await update_job_status(job_id, phase="quality", progress=100)

            # Enrich
            await update_job_status(job_id, phase="enrichment", progress=0)
            enrichment = EnrichmentService(db)
            enriched_med = await enrichment.enrich_medical_batch(med_claims) if med_claims else []
            enriched_rx = await enrichment.enrich_pharmacy_batch(rx_claims) if rx_claims else []
            await update_job_status(job_id, phase="enrichment", progress=100)

            # Rules
            await update_job_status(job_id, phase="rules", progress=0)
            rule_engine = RuleEngine(db)
            await rule_engine.load_rules()
            await rule_engine.load_configs()
            med_results = await rule_engine.evaluate_batch(enriched_med, batch_id) if enriched_med else {}
            rx_results = await rule_engine.evaluate_batch(enriched_rx, batch_id) if enriched_rx else {}
            rules_saved = await rule_engine.save_results(med_results) + await rule_engine.save_results(rx_results)
            await update_job_status(job_id, phase="rules", progress=100)

            # Scoring
            await update_job_status(job_id, phase="scoring", progress=0)
            scoring = ScoringEngine(db)
            med_scores = await scoring.score_batch(med_results, "medical", batch_id) if med_results else []
            rx_scores = await scoring.score_batch(rx_results, "pharmacy", batch_id) if rx_results else []
            all_scores = med_scores + rx_scores
            claim_ws_map = {c.claim_id: ws_id or c.workspace_id for c in med_claims + rx_claims}
            for score in all_scores:
                score.workspace_id = claim_ws_map.get(score.claim_id)
            scores_saved = await scoring.save_scores(all_scores)
            await update_job_status(job_id, phase="scoring", progress=100)

            # Update claim statuses
            for c in med_claims + rx_claims:
                c.status = "processed"
                c.batch_id = batch_id
            await db.flush()

            # Cases
            await update_job_status(job_id, phase="cases", progress=0)
            case_manager = CaseManager(db)
            new_cases = await case_manager.create_cases_from_scores(
                all_scores, generate_evidence=True, workspace_id=ws_id, claim_ws_map=claim_ws_map,
            )
            await update_job_status(job_id, phase="cases", progress=100)

            duration = round(time.time() - t_start, 3)

            # Record pipeline run
            run = PipelineRun(
                run_id=job_id,
                workspace_id=ws_id,
                batch_id=batch_id,
                status="completed",
                duration_seconds=duration,
                stats={
                    "medical_claims": len(med_claims),
                    "pharmacy_claims": len(rx_claims),
                    "rules_evaluated": rules_saved,
                    "scores_generated": scores_saved,
                    "cases_created": len(new_cases),
                },
                quality_report={
                    "medical": med_report.to_dict(),
                    "pharmacy": rx_report.to_dict(),
                },
            )
            db.add(run)

            # Audit
            audit = AuditService(db)
            await audit.log_event(
                event_type="pipeline_run",
                actor="worker",
                action=f"Worker pipeline {batch_id}: {total} claims",
                resource_type="batch",
                resource_id=batch_id,
                details={"job_id": job_id, "total_claims": total},
            )

            await db.commit()

            await update_job_status(
                job_id, status="completed", phase="done", progress=100,
                claims_processed=total,
                result={
                    "batch_id": batch_id,
                    "total_claims": total,
                    "medical_claims": len(med_claims),
                    "pharmacy_claims": len(rx_claims),
                    "rules_evaluated": rules_saved,
                    "scores_generated": scores_saved,
                    "cases_created": len(new_cases),
                    "duration_seconds": duration,
                },
            )
            logger.info("Job %s completed: %d claims in %.1fs", job_id, total, duration)

        except Exception as exc:
            logger.error("Job %s failed: %s", job_id, exc, exc_info=True)
            await update_job_status(job_id, status="failed", phase="error", errors=1)
            await db.rollback()


async def main():
    """Main worker loop — polls Redis queue for pipeline jobs."""
    from app.config import settings

    engine = create_async_engine(settings.database_url, echo=False)
    SessionMaker = async_sessionmaker(engine, expire_on_commit=False)

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    logger.info("Worker started, listening on arqai:pipeline:queue")

    while True:
        try:
            # Block-pop from queue (5 second timeout)
            result = await r.brpop("arqai:pipeline:queue", timeout=5)
            if result is None:
                continue
            _, raw = result
            job_data = json.loads(raw)
            logger.info("Processing job: %s", job_data.get("job_id"))
            await process_pipeline_job(job_data, engine, SessionMaker)
        except Exception as exc:
            logger.error("Worker loop error: %s", exc, exc_info=True)
            await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
