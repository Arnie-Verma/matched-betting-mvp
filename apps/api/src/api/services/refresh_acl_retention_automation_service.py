"""Automation + lock orchestration for refresh ACL retention cleanup."""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import redis

from api.core.database import SessionLocal
from api.services.observability_service import emit_observability_event
from api.services.refresh_acl_retention_service import (
    RefreshAclRetentionConfig,
    RefreshAclRetentionGuardrailConfig,
    load_refresh_acl_retention_config_from_env,
    load_refresh_acl_retention_guardrail_config_from_env,
    run_refresh_acl_retention_with_guardrails,
)


DEFAULT_REFRESH_RETENTION_LOCK_KEY = "maintenance:refresh_acl_retention:lock"
DEFAULT_REFRESH_RETENTION_LOCK_TTL_SECONDS = 900
_LOCK_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


@dataclass(frozen=True)
class RefreshAclRetentionAutomationResult:
    run_id: str
    run_status: str
    reason_code: str
    dry_run: bool
    lock_key: str
    lock_acquired: bool
    lock_ttl_seconds: int
    started_at: str
    completed_at: str
    duration_ms: int
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_status": self.run_status,
            "reason_code": self.reason_code,
            "dry_run": self.dry_run,
            "lock_key": self.lock_key,
            "lock_acquired": self.lock_acquired,
            "lock_ttl_seconds": self.lock_ttl_seconds,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "summary": dict(self.summary),
        }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_int(value: Optional[str], fallback: int) -> int:
    if value is None or value == "":
        return int(fallback)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(fallback)
    return int(parsed) if parsed > 0 else int(fallback)


def _get_redis_client(redis_client=None):
    if redis_client is not None:
        return redis_client
    redis_url = os.getenv("REFRESH_RETENTION_REDIS_URL") or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url, socket_connect_timeout=0.5, socket_timeout=0.5)


def _acquire_lock(redis_client, *, lock_key: str, lock_token: str, lock_ttl_seconds: int) -> bool:
    try:
        result = redis_client.set(lock_key, lock_token, nx=True, ex=int(lock_ttl_seconds))
    except Exception:
        return False
    return bool(result)


def _release_lock(redis_client, *, lock_key: str, lock_token: str) -> None:
    try:
        redis_client.eval(_LOCK_RELEASE_SCRIPT, 1, lock_key, str(lock_token))
    except Exception:
        return


def _emit_retention_observability(result: RefreshAclRetentionAutomationResult) -> None:
    summary = result.summary or {}
    deleted = summary.get("deleted") or {}
    candidates = summary.get("candidates") or {}
    emit_observability_event(
        category="maintenance",
        metric_name="refresh_acl_retention_run",
        source="api",
        endpoint="maintenance/refresh_acl_retention",
        action_type=f"refresh_acl_retention_{result.run_status}",
        payload={
            "run_id": result.run_id,
            "reason_code": result.reason_code,
            "dry_run": bool(result.dry_run),
            "lock_acquired": bool(result.lock_acquired),
            "duration_ms": int(result.duration_ms),
            "candidates": candidates,
            "deleted": deleted,
            "aborted_reason_code": summary.get("aborted_reason_code"),
            "guardrails": summary.get("guardrails") or {},
        },
    )


def execute_refresh_acl_retention_automation(
    *,
    dry_run: bool,
    retention_config: Optional[RefreshAclRetentionConfig] = None,
    guardrail_config: Optional[RefreshAclRetentionGuardrailConfig] = None,
    allow_cap_breach_override: bool = False,
    lock_key: Optional[str] = None,
    lock_ttl_seconds: Optional[int] = None,
    redis_client=None,
    db_factory: Callable[[], Any] = SessionLocal,
) -> RefreshAclRetentionAutomationResult:
    started_at = _utcnow()
    run_id = str(uuid.uuid4())
    resolved_lock_key = (lock_key or os.getenv("REFRESH_RETENTION_LOCK_KEY") or DEFAULT_REFRESH_RETENTION_LOCK_KEY).strip()
    resolved_lock_ttl = (
        int(lock_ttl_seconds)
        if isinstance(lock_ttl_seconds, int) and int(lock_ttl_seconds) > 0
        else _parse_int(os.getenv("REFRESH_RETENTION_LOCK_TTL_SECONDS"), DEFAULT_REFRESH_RETENTION_LOCK_TTL_SECONDS)
    )

    config = retention_config or load_refresh_acl_retention_config_from_env(now=started_at)
    guardrails = guardrail_config or load_refresh_acl_retention_guardrail_config_from_env()
    # Cap-breach override must always be explicit per run; env/config cannot force-enable it.
    guardrails = RefreshAclRetentionGuardrailConfig(
        max_delete_terminal_jobs=int(guardrails.max_delete_terminal_jobs),
        max_delete_audit_rows=int(guardrails.max_delete_audit_rows),
        max_delete_acl_rows=int(guardrails.max_delete_acl_rows),
        allow_cap_breach=bool(allow_cap_breach_override),
    )

    lock_token = f"{run_id}:{int(started_at.timestamp())}"
    try:
        client = _get_redis_client(redis_client=redis_client)
    except Exception:
        completed_at = _utcnow()
        result = RefreshAclRetentionAutomationResult(
            run_id=run_id,
            run_status="failure",
            reason_code="lock_client_unavailable",
            dry_run=bool(dry_run),
            lock_key=resolved_lock_key,
            lock_acquired=False,
            lock_ttl_seconds=int(resolved_lock_ttl),
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            summary={},
        )
        _emit_retention_observability(result)
        return result

    lock_acquired = _acquire_lock(
        client,
        lock_key=resolved_lock_key,
        lock_token=lock_token,
        lock_ttl_seconds=resolved_lock_ttl,
    )
    if not lock_acquired:
        completed_at = _utcnow()
        result = RefreshAclRetentionAutomationResult(
            run_id=run_id,
            run_status="aborted",
            reason_code="lock_not_acquired",
            dry_run=bool(dry_run),
            lock_key=resolved_lock_key,
            lock_acquired=False,
            lock_ttl_seconds=int(resolved_lock_ttl),
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            summary={
                "run_status": "aborted",
                "aborted_reason_code": "lock_not_acquired",
                "guardrails": {
                    "allow_cap_breach": bool(guardrails.allow_cap_breach),
                },
            },
        )
        _emit_retention_observability(result)
        return result

    try:
        db = db_factory()
    except Exception:
        _release_lock(client, lock_key=resolved_lock_key, lock_token=lock_token)
        completed_at = _utcnow()
        result = RefreshAclRetentionAutomationResult(
            run_id=run_id,
            run_status="failure",
            reason_code="db_session_unavailable",
            dry_run=bool(dry_run),
            lock_key=resolved_lock_key,
            lock_acquired=True,
            lock_ttl_seconds=int(resolved_lock_ttl),
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            summary={},
        )
        _emit_retention_observability(result)
        return result

    try:
        retention_summary = run_refresh_acl_retention_with_guardrails(
            db,
            config=config,
            dry_run=bool(dry_run),
            guardrails=guardrails,
        )
        completed_at = _utcnow()
        run_status = retention_summary.run_status or "success"
        reason_code = (
            retention_summary.aborted_reason_code
            if run_status == "aborted"
            else "success"
        )
        result = RefreshAclRetentionAutomationResult(
            run_id=run_id,
            run_status=run_status,
            reason_code=str(reason_code),
            dry_run=bool(dry_run),
            lock_key=resolved_lock_key,
            lock_acquired=True,
            lock_ttl_seconds=int(resolved_lock_ttl),
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            summary=retention_summary.to_dict(),
        )
    except Exception as exc:  # noqa: BLE001
        completed_at = _utcnow()
        result = RefreshAclRetentionAutomationResult(
            run_id=run_id,
            run_status="failure",
            reason_code="retention_run_failed",
            dry_run=bool(dry_run),
            lock_key=resolved_lock_key,
            lock_acquired=True,
            lock_ttl_seconds=int(resolved_lock_ttl),
            started_at=started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            duration_ms=int((completed_at - started_at).total_seconds() * 1000),
            summary={
                "run_status": "failure",
                "error": str(exc),
            },
        )
    finally:
        try:
            db.close()
        except Exception:
            pass
        _release_lock(client, lock_key=resolved_lock_key, lock_token=lock_token)

    _emit_retention_observability(result)
    return result


def run_refresh_acl_retention_schedule(
    *,
    max_runs: int,
    interval_seconds: int,
    runner: Callable[..., RefreshAclRetentionAutomationResult] = execute_refresh_acl_retention_automation,
    sleep_fn: Callable[[float], None] = time.sleep,
    dry_run: bool,
    runner_kwargs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    started_at = _utcnow()
    effective_runs = max(1, int(max_runs))
    effective_interval = max(0, int(interval_seconds))
    outputs = []
    kwargs = dict(runner_kwargs or {})

    for idx in range(effective_runs):
        result = runner(dry_run=bool(dry_run), **kwargs)
        outputs.append(result.to_dict())
        if idx < (effective_runs - 1) and effective_interval > 0:
            sleep_fn(float(effective_interval))

    completed_at = _utcnow()
    return {
        "run_count": len(outputs),
        "dry_run": bool(dry_run),
        "interval_seconds": int(effective_interval),
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_ms": int((completed_at - started_at).total_seconds() * 1000),
        "runs": outputs,
    }
