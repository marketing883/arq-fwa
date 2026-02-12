"""
Async job queue for pipeline execution using ARQ + Redis.

Allows pipeline runs to be enqueued as background jobs with status tracking.
"""

import json
import logging
import time
from datetime import datetime
from uuid import uuid4

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

JOB_KEY_PREFIX = "pipeline:job:"


async def get_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def enqueue_pipeline_job(
    workspace_id: str | None = None,
    limit: int = 1000,
    batch_id: str | None = None,
    force_reprocess: bool = False,
) -> str:
    """Enqueue a pipeline job and return its job_id."""
    job_id = f"PJOB-{uuid4().hex[:12].upper()}"
    r = await get_redis()

    job_data = {
        "job_id": job_id,
        "status": "queued",
        "phase": "pending",
        "progress": 0,
        "claims_processed": 0,
        "errors": 0,
        "started_at": "",
        "completed_at": "",
        "workspace_id": workspace_id or "",
        "limit": limit,
        "batch_id": batch_id or "",
        "force_reprocess": str(force_reprocess),
    }
    await r.hset(f"{JOB_KEY_PREFIX}{job_id}", mapping=job_data)
    await r.expire(f"{JOB_KEY_PREFIX}{job_id}", 86400)  # expire after 24h

    # Push to the work queue
    await r.lpush("arqai:pipeline:queue", json.dumps({
        "job_id": job_id,
        "workspace_id": workspace_id,
        "limit": limit,
        "batch_id": batch_id,
        "force_reprocess": force_reprocess,
    }))

    await r.aclose()
    return job_id


async def get_job_status(job_id: str) -> dict | None:
    """Get the current status of a pipeline job."""
    r = await get_redis()
    data = await r.hgetall(f"{JOB_KEY_PREFIX}{job_id}")
    await r.aclose()
    if not data:
        return None
    return data


async def update_job_status(
    job_id: str,
    *,
    status: str | None = None,
    phase: str | None = None,
    progress: int | None = None,
    claims_processed: int | None = None,
    errors: int | None = None,
    result: dict | None = None,
):
    """Update fields on a pipeline job."""
    r = await get_redis()
    updates: dict = {}
    if status is not None:
        updates["status"] = status
    if phase is not None:
        updates["phase"] = phase
    if progress is not None:
        updates["progress"] = progress
    if claims_processed is not None:
        updates["claims_processed"] = claims_processed
    if errors is not None:
        updates["errors"] = errors
    if status == "running" and not updates.get("started_at"):
        updates["started_at"] = datetime.utcnow().isoformat()
    if status in ("completed", "failed"):
        updates["completed_at"] = datetime.utcnow().isoformat()
    if result:
        updates["result"] = json.dumps(result)

    if updates:
        await r.hset(f"{JOB_KEY_PREFIX}{job_id}", mapping=updates)
    await r.aclose()
