"""
Simple Redis-backed worker to consume odds refresh jobs.

This is a lightweight consumer to bridge the API enqueue step and the
existing scraping pipeline without introducing Celery/RQ yet.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

import redis
import random

# Ensure imports work when running from repo root
sys.path.insert(0, "apps/api/src")
sys.path.insert(0, "apps/worker/src")

from api.services.refresh_queue import DEFAULT_JOB_PREFIX, DEFAULT_QUEUE_KEY, get_job_status  # type: ignore
from jobs.scrape_service import trigger_scrape  # type: ignore


def _update_job(
    redis_client,
    job_id: str,
    data: dict,
    *,
    job_prefix: str,
    ttl_seconds: int,
) -> None:
    job_key = f"{job_prefix}{job_id}"
    redis_client.set(job_key, json.dumps(data), ex=ttl_seconds)


def _load_job(redis_client, job_id: str, *, job_prefix: str) -> Optional[dict]:
    job = get_job_status(redis_client, job_id, job_prefix=job_prefix)
    if not job:
        return None
    return job


def _set_status(job: dict, status: str, message: Optional[str] = None) -> dict:
    job["status"] = status
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    if message:
        job["message"] = message
    return job


async def _process_job(
    redis_client,
    job_id: str,
    *,
    global_cache_key: str,
    job_prefix: str,
    queue_key: str,
    fast_ttl_seconds: int,
    slow_ttl_seconds: int,
    max_retries: int,
    backoff_base: float,
    backoff_jitter: float,
    active_bookmakers: list[str],
    concurrency_cap: int,
    dlq_key: str,
    slow_bookmakers: set[str],
) -> None:
    logger = logging.getLogger(__name__)
    job = _load_job(redis_client, job_id, job_prefix=job_prefix)
    if not job:
        logger.warning(f"[refresh-worker] Job {job_id} not found or expired")
        return

    job.setdefault("payload", {})
    job.setdefault("errors", [])
    attempts = int(job.get("attempts", 0))
    job["started_at"] = datetime.now(timezone.utc).isoformat()
    job = _set_status(job, "running", "Scrape started")
    _update_job(redis_client, job_id, job, job_prefix=job_prefix, ttl_seconds=slow_ttl_seconds)

    try:
        # Concurrency guard (global per bookmaker)
        acquired = []
        for bm in active_bookmakers:
            running_key = f"odds_refresh_running:{bm}"
            count = redis_client.incr(running_key)
            if count > concurrency_cap:
                redis_client.decr(running_key)
                raise RuntimeError(f"Bookmaker {bm} over concurrency cap {concurrency_cap}")
            redis_client.expire(running_key, slow_ttl_seconds)
            acquired.append(running_key)

        # Currently always scrape all sports/all bookmakers; can later use payload fields
        result = await trigger_scrape(sport="all", limit=None)

        now = datetime.now(timezone.utc)
        job["completed_at"] = now.isoformat()
        job["result"] = {
            "success": result.get("success"),
            "bookmakers_scraped": result.get("bookmakers_scraped"),
            "odds_saved": result.get("odds_saved"),
            "errors": result.get("errors"),
        }

        success = result.get("success", False)
        status = "success" if success else "failed"
        msg = "Scrape completed" if success else "Scrape completed with errors"
        job = _set_status(job, status, msg)

        # On success, refresh cache timestamps (global + per bookmaker)
        redis_client.setex(global_cache_key, fast_ttl_seconds, now.isoformat())
        for res in result.get("results", []):
            bm_code = res.get("bookmaker")
            if not bm_code:
                continue
            ttl = slow_ttl_seconds if bm_code in slow_bookmakers else fast_ttl_seconds
            redis_client.setex(f"odds_last_refresh:{bm_code}", ttl, now.isoformat())

    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[refresh-worker] Job {job_id} failed: {exc}")
        job.setdefault("errors", []).append(str(exc))
        job["completed_at"] = datetime.now(timezone.utc).isoformat()
        attempts += 1
        job["attempts"] = attempts
        if attempts > max_retries:
            job = _set_status(job, "failed", "Scrape failed; moved to DLQ")
            _update_job(redis_client, job_id, job, job_prefix=job_prefix, ttl_seconds=slow_ttl_seconds)
            redis_client.lpush(dlq_key, json.dumps(job))
            return

        # Requeue with backoff + jitter
        delay = backoff_base * (2 ** (attempts - 1)) + random.random() * backoff_jitter
        job = _set_status(job, "pending", f"Retrying in {delay:.1f}s")
        _update_job(redis_client, job_id, job, job_prefix=job_prefix, ttl_seconds=slow_ttl_seconds)
        await asyncio.sleep(delay)
        redis_client.rpush(queue_key, job_id)
        return

    finally:
        # Release concurrency counters
        for bm in active_bookmakers:
            running_key = f"odds_refresh_running:{bm}"
            try:
                redis_client.decr(running_key)
            except Exception:
                pass

    _update_job(redis_client, job_id, job, job_prefix=job_prefix, ttl_seconds=slow_ttl_seconds)


async def run_worker_once(
    *,
    redis_url: str = None,
    queue_key: str = DEFAULT_QUEUE_KEY,
    job_prefix: str = DEFAULT_JOB_PREFIX,
    global_cache_key: str = "odds_last_refresh_global",
    fast_ttl_seconds: int = 60,
    slow_ttl_seconds: int = 300,
    max_retries: int = 3,
    backoff_base: float = 1.5,
    backoff_jitter: float = 1.0,
    active_bookmakers: Optional[list[str]] = None,
    concurrency_cap: int = 1,
    dlq_key: str = "odds_refresh_jobs_dead",
    slow_bookmakers: Optional[set[str]] = None,
) -> bool:
    """
    Process a single job if available. Returns True if a job was handled.
    """
    redis_client = redis.from_url(redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    item = redis_client.brpop(queue_key, timeout=1)
    if not item:
        return False

    _, raw_job_id = item
    job_id = raw_job_id.decode()
    await _process_job(
        redis_client,
        job_id,
        global_cache_key=global_cache_key,
        job_prefix=job_prefix,
        queue_key=queue_key,
        fast_ttl_seconds=fast_ttl_seconds,
        slow_ttl_seconds=slow_ttl_seconds,
        max_retries=max_retries,
        backoff_base=backoff_base,
        backoff_jitter=backoff_jitter,
        active_bookmakers=active_bookmakers or [],
        concurrency_cap=concurrency_cap,
        dlq_key=dlq_key,
        slow_bookmakers=slow_bookmakers or set(),
    )
    return True


def run_worker_forever() -> None:
    """Blocking worker loop for simple deployment."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    queue_key = os.getenv("ODDS_REFRESH_QUEUE_KEY", DEFAULT_QUEUE_KEY)
    job_prefix = os.getenv("ODDS_REFRESH_JOB_PREFIX", DEFAULT_JOB_PREFIX)
    global_cache_key = os.getenv("ODDS_REFRESH_GLOBAL_KEY", "odds_last_refresh_global")
    fast_ttl_seconds = int(os.getenv("ODDS_CACHE_TTL_FAST_SECONDS", "60"))
    slow_ttl_seconds = int(os.getenv("ODDS_CACHE_TTL_SLOW_SECONDS", "300"))
    max_retries = int(os.getenv("ODDS_REFRESH_MAX_RETRIES", "3"))
    backoff_base = float(os.getenv("ODDS_REFRESH_BACKOFF_BASE", "1.5"))
    backoff_jitter = float(os.getenv("ODDS_REFRESH_BACKOFF_JITTER", "1.0"))
    concurrency_cap = int(os.getenv("BOOKMAKER_CONCURRENCY_CAP", "1"))
    dlq_key = os.getenv("ODDS_REFRESH_DLQ_KEY", "odds_refresh_jobs_dead")
    active_bookmakers_env = os.getenv("ACTIVE_BOOKMAKERS", "betfair,ladbrokes")
    active_bookmakers = [b.strip() for b in active_bookmakers_env.split(",") if b.strip()]
    slow_bookmakers_env = os.getenv("SLOW_BOOKMAKERS", "")
    slow_bookmakers = {b.strip() for b in slow_bookmakers_env.split(",") if b.strip()}

    logger.info(
        f"[refresh-worker] Starting with queue={queue_key}, job_prefix={job_prefix}, redis={redis_url}"
    )

    while True:
        try:
            handled = asyncio.run(
                run_worker_once(
                    redis_url=redis_url,
                    queue_key=queue_key,
                    job_prefix=job_prefix,
                    global_cache_key=global_cache_key,
                    fast_ttl_seconds=fast_ttl_seconds,
                    slow_ttl_seconds=slow_ttl_seconds,
                    max_retries=max_retries,
                    backoff_base=backoff_base,
                    backoff_jitter=backoff_jitter,
                    active_bookmakers=active_bookmakers,
                    concurrency_cap=concurrency_cap,
                    dlq_key=dlq_key,
                    slow_bookmakers=slow_bookmakers,
                )
            )
            if not handled:
                # idle pause to avoid busy loop when queue is empty
                import time
                time.sleep(1)
                continue
        except KeyboardInterrupt:
            logger.info("[refresh-worker] Stopping worker (KeyboardInterrupt)")
            break
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"[refresh-worker] Unhandled error: {exc}")


if __name__ == "__main__":
    run_worker_forever()
