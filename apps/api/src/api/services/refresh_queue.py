"""
Lightweight Redis-backed queue utilities for odds refresh jobs.

Designed to decouple API requests from scraping so the refresh endpoint
can enqueue work and return immediately.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

DEFAULT_QUEUE_KEY = "odds_refresh_jobs"
DEFAULT_JOB_PREFIX = "odds_refresh_job:"


def enqueue_refresh_job(
    redis_client,
    payload: Dict[str, Any],
    *,
    queue_key: str = DEFAULT_QUEUE_KEY,
    job_prefix: str = DEFAULT_JOB_PREFIX,
    ttl_seconds: int = 900,
    max_queue_length: Optional[int] = None,
    merge_if_pending: bool = True,
) -> Dict[str, Any]:
    """
    Push a refresh job onto Redis with simple status metadata.

    Returns dict with {job_id, status, merged: bool}.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Queue guard + merge behavior
    qlen = redis_client.llen(queue_key)
    if max_queue_length is not None and qlen >= max_queue_length:
        # If the queue is already full, merge into the most-recent queued job instead
        # of generating a new job_id that will never run.
        existing = redis_client.lindex(queue_key, -1)
        if existing:
            return {"job_id": existing.decode(), "status": "pending", "merged": True}
        # Fallback: allow a new job (should be rare/impossible if qlen >= max_queue_length)

    if merge_if_pending and qlen > 0:
        # A refresh is already queued - return the existing queued job_id so callers
        # can poll the *real* job that will run.
        existing = redis_client.lindex(queue_key, -1)
        if existing:
            return {"job_id": existing.decode(), "status": "pending", "merged": True}

    job_id = str(uuid.uuid4())
    job_key = f"{job_prefix}{job_id}"
    job_body = {
        "status": "pending",
        "enqueued_at": now,
        "updated_at": now,
        "payload": payload,
        "attempts": 0,
    }

    pipe = redis_client.pipeline()
    pipe.set(job_key, json.dumps(job_body), ex=ttl_seconds)
    pipe.rpush(queue_key, job_id)
    pipe.execute()

    return {"job_id": job_id, "status": "pending", "merged": False}


def get_job_status(
    redis_client,
    job_id: str,
    *,
    job_prefix: str = DEFAULT_JOB_PREFIX,
) -> Optional[Dict[str, Any]]:
    """Fetch job metadata if it exists."""
    job_key = f"{job_prefix}{job_id}"
    data = redis_client.get(job_key)
    if not data:
        return None
    try:
        return json.loads(data)
    except Exception:
        return None
