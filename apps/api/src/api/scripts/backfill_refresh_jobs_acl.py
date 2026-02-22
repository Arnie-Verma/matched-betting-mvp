"""Backfill durable refresh ACL records from legacy Redis refresh-job payloads."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import redis

from api.core.database import SessionLocal
from api.services.refresh_job_acl_service import RefreshJobAclService


DEFAULT_JOB_PREFIX = os.getenv("ODDS_REFRESH_JOB_PREFIX", "odds_refresh_job:")


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _is_recent(job_payload: Dict[str, Any], cutoff: datetime) -> bool:
    for key in ("updated_at", "completed_at", "started_at", "enqueued_at"):
        ts = _parse_dt(job_payload.get(key))
        if ts and ts >= cutoff:
            return True
    return False


def run_backfill(*, hours: int, redis_url: str, job_prefix: str) -> Dict[str, Any]:
    redis_client = redis.from_url(redis_url)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    scanned = 0
    eligible = 0
    created = 0
    skipped = 0
    errors: list[dict[str, Any]] = []

    db = SessionLocal()
    try:
        for key in redis_client.scan_iter(f"{job_prefix}*"):
            scanned += 1
            key_text = key.decode() if isinstance(key, bytes) else str(key)
            job_id = key_text.replace(job_prefix, "", 1)
            raw = redis_client.get(key)
            if not raw:
                skipped += 1
                continue
            try:
                payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            except json.JSONDecodeError:
                skipped += 1
                continue

            if not isinstance(payload, dict) or not _is_recent(payload, cutoff):
                skipped += 1
                continue

            eligible += 1
            try:
                record = RefreshJobAclService.backfill_job_from_legacy_payload(
                    db,
                    job_id=job_id,
                    legacy_job_status=payload,
                    actor_sub="script:backfill_refresh_jobs_acl",
                )
                if record:
                    created += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                errors.append({"job_id": job_id, "error": str(exc)})

    finally:
        db.close()

    return {
        "hours": hours,
        "job_prefix": job_prefix,
        "scanned": scanned,
        "eligible": eligible,
        "backfilled_or_existing": created,
        "skipped": skipped,
        "errors": errors,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill durable refresh ACL records from Redis jobs")
    parser.add_argument("--hours", type=int, default=24, help="Trailing hours window to backfill")
    parser.add_argument("--redis-url", default=os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    parser.add_argument("--job-prefix", default=DEFAULT_JOB_PREFIX)
    args = parser.parse_args()

    summary = run_backfill(
        hours=max(1, int(args.hours)),
        redis_url=args.redis_url,
        job_prefix=args.job_prefix,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
