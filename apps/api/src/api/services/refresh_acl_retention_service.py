"""Retention policy service for durable refresh ACL/audit records."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models import RefreshJob, RefreshJobAclEntry, RefreshJobAuditEvent


DEFAULT_REFRESH_AUDIT_RETENTION_DAYS = 30
DEFAULT_REFRESH_TERMINAL_JOB_RETENTION_DAYS = 14
DEFAULT_REFRESH_TERMINAL_STATUSES = (
    "success",
    "failed",
    "cancelled",
    "canceled",
    "expired",
)
DEFAULT_REFRESH_RETENTION_MAX_DELETE_TERMINAL_JOBS = 5000
DEFAULT_REFRESH_RETENTION_MAX_DELETE_AUDIT_ROWS = 200000
DEFAULT_REFRESH_RETENTION_MAX_DELETE_ACL_ROWS = 50000


@dataclass(frozen=True)
class RefreshAclRetentionConfig:
    audit_retention_days: int
    terminal_job_retention_days: int
    terminal_statuses: tuple[str, ...]
    now: datetime

    @property
    def audit_cutoff(self) -> datetime:
        return self.now - timedelta(days=self.audit_retention_days)

    @property
    def terminal_job_cutoff(self) -> datetime:
        return self.now - timedelta(days=self.terminal_job_retention_days)


@dataclass(frozen=True)
class RefreshAclRetentionSummary:
    dry_run: bool
    config: Dict[str, Any]
    before: Dict[str, int]
    candidates: Dict[str, int]
    deleted: Dict[str, int]
    after: Dict[str, int]
    safety: Dict[str, Any]
    generated_at: str
    run_status: str = "success"
    aborted_reason_code: str | None = None
    guardrails: Dict[str, Any] | None = None
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dry_run": bool(self.dry_run),
            "config": dict(self.config),
            "before": dict(self.before),
            "candidates": dict(self.candidates),
            "deleted": dict(self.deleted),
            "after": dict(self.after),
            "safety": dict(self.safety),
            "generated_at": self.generated_at,
            "run_status": self.run_status,
            "aborted_reason_code": self.aborted_reason_code,
            "guardrails": dict(self.guardrails or {}),
            "duration_ms": int(self.duration_ms),
        }


@dataclass(frozen=True)
class RefreshAclRetentionGuardrailConfig:
    max_delete_terminal_jobs: int
    max_delete_audit_rows: int
    max_delete_acl_rows: int
    allow_cap_breach: bool = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return int(default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return int(parsed) if parsed > 0 else int(default)


def _parse_statuses(value: str | None) -> tuple[str, ...]:
    if not value:
        return tuple(DEFAULT_REFRESH_TERMINAL_STATUSES)
    statuses = []
    for item in value.split(","):
        normalized = (item or "").strip().lower()
        if normalized and normalized not in statuses:
            statuses.append(normalized)
    if not statuses:
        return tuple(DEFAULT_REFRESH_TERMINAL_STATUSES)
    return tuple(statuses)


def load_refresh_acl_retention_config_from_env(*, now: datetime | None = None) -> RefreshAclRetentionConfig:
    return RefreshAclRetentionConfig(
        audit_retention_days=_parse_int(
            os.getenv("REFRESH_AUDIT_RETENTION_DAYS"),
            DEFAULT_REFRESH_AUDIT_RETENTION_DAYS,
        ),
        terminal_job_retention_days=_parse_int(
            os.getenv("REFRESH_TERMINAL_JOB_RETENTION_DAYS"),
            DEFAULT_REFRESH_TERMINAL_JOB_RETENTION_DAYS,
        ),
        terminal_statuses=_parse_statuses(os.getenv("REFRESH_TERMINAL_JOB_STATUSES")),
        now=now or _utcnow(),
    )


def load_refresh_acl_retention_guardrail_config_from_env() -> RefreshAclRetentionGuardrailConfig:
    return RefreshAclRetentionGuardrailConfig(
        max_delete_terminal_jobs=_parse_int(
            os.getenv("REFRESH_RETENTION_MAX_DELETE_TERMINAL_JOBS"),
            DEFAULT_REFRESH_RETENTION_MAX_DELETE_TERMINAL_JOBS,
        ),
        max_delete_audit_rows=_parse_int(
            os.getenv("REFRESH_RETENTION_MAX_DELETE_AUDIT_ROWS"),
            DEFAULT_REFRESH_RETENTION_MAX_DELETE_AUDIT_ROWS,
        ),
        max_delete_acl_rows=_parse_int(
            os.getenv("REFRESH_RETENTION_MAX_DELETE_ACL_ROWS"),
            DEFAULT_REFRESH_RETENTION_MAX_DELETE_ACL_ROWS,
        ),
        # Safety invariant: cap-breach override is explicit per-run intent only.
        allow_cap_breach=False,
    )


def _count_before(db: Session, terminal_statuses: Iterable[str]) -> Dict[str, int]:
    status_list = list(terminal_statuses)
    total_jobs = int(db.query(RefreshJob).count())
    terminal_jobs = int(db.query(RefreshJob).filter(RefreshJob.status.in_(status_list)).count())
    non_terminal_jobs = total_jobs - terminal_jobs
    return {
        "total_jobs": total_jobs,
        "terminal_jobs": terminal_jobs,
        "non_terminal_jobs": non_terminal_jobs,
        "total_acl_rows": int(db.query(RefreshJobAclEntry).count()),
        "active_acl_rows": int(db.query(RefreshJobAclEntry).filter(RefreshJobAclEntry.is_active == True).count()),
        "total_audit_rows": int(db.query(RefreshJobAuditEvent).count()),
    }


def _collect_terminal_job_ids(db: Session, config: RefreshAclRetentionConfig) -> list[int]:
    reference_ts = func.coalesce(RefreshJob.completed_at, RefreshJob.updated_at, RefreshJob.created_at)
    rows = (
        db.query(RefreshJob.id)
        .filter(
            RefreshJob.status.in_(list(config.terminal_statuses)),
            reference_ts < config.terminal_job_cutoff,
        )
        .all()
    )
    return [int(row[0]) for row in rows]


def _collect_old_terminal_audit_ids(
    db: Session,
    *,
    config: RefreshAclRetentionConfig,
    excluded_job_ids: list[int],
) -> list[int]:
    query = (
        db.query(RefreshJobAuditEvent.id)
        .join(RefreshJob, RefreshJob.id == RefreshJobAuditEvent.refresh_job_id)
        .filter(
            RefreshJobAuditEvent.created_at < config.audit_cutoff,
            RefreshJob.status.in_(list(config.terminal_statuses)),
        )
    )
    if excluded_job_ids:
        query = query.filter(~RefreshJobAuditEvent.refresh_job_id.in_(excluded_job_ids))
    return [int(row[0]) for row in query.all()]


def run_refresh_acl_retention(
    db: Session,
    *,
    config: RefreshAclRetentionConfig,
    dry_run: bool,
) -> RefreshAclRetentionSummary:
    started_at = _utcnow()
    before = _count_before(db, config.terminal_statuses)
    terminal_job_ids = _collect_terminal_job_ids(db, config)
    aged_audit_ids = _collect_old_terminal_audit_ids(
        db,
        config=config,
        excluded_job_ids=terminal_job_ids,
    )

    terminal_job_audit_count = 0
    terminal_job_acl_count = 0
    if terminal_job_ids:
        terminal_job_audit_count = int(
            db.query(RefreshJobAuditEvent)
            .filter(RefreshJobAuditEvent.refresh_job_id.in_(terminal_job_ids))
            .count()
        )
        terminal_job_acl_count = int(
            db.query(RefreshJobAclEntry)
            .filter(RefreshJobAclEntry.refresh_job_id.in_(terminal_job_ids))
            .count()
        )

    if terminal_job_ids:
        non_terminal_delete_candidates = int(
            db.query(RefreshJob)
            .filter(
                RefreshJob.id.in_(terminal_job_ids),
                ~RefreshJob.status.in_(list(config.terminal_statuses)),
            )
            .count()
        )
    else:
        non_terminal_delete_candidates = 0

    candidates = {
        "terminal_jobs": int(len(terminal_job_ids)),
        "audit_rows_for_terminal_jobs": int(terminal_job_audit_count),
        "acl_rows_for_terminal_jobs": int(terminal_job_acl_count),
        "aged_terminal_audit_rows": int(len(aged_audit_ids)),
    }

    deleted = {
        "terminal_jobs": 0,
        "audit_rows_for_terminal_jobs": 0,
        "acl_rows_for_terminal_jobs": 0,
        "aged_terminal_audit_rows": 0,
    }

    if not dry_run:
        if aged_audit_ids:
            deleted["aged_terminal_audit_rows"] = int(
                db.query(RefreshJobAuditEvent)
                .filter(RefreshJobAuditEvent.id.in_(aged_audit_ids))
                .delete(synchronize_session=False)
            )

        if terminal_job_ids:
            deleted["audit_rows_for_terminal_jobs"] = int(
                db.query(RefreshJobAuditEvent)
                .filter(RefreshJobAuditEvent.refresh_job_id.in_(terminal_job_ids))
                .delete(synchronize_session=False)
            )
            deleted["acl_rows_for_terminal_jobs"] = int(
                db.query(RefreshJobAclEntry)
                .filter(RefreshJobAclEntry.refresh_job_id.in_(terminal_job_ids))
                .delete(synchronize_session=False)
            )
            deleted["terminal_jobs"] = int(
                db.query(RefreshJob)
                .filter(RefreshJob.id.in_(terminal_job_ids))
                .delete(synchronize_session=False)
            )
        db.commit()

    after = _count_before(db, config.terminal_statuses)
    duration_ms = int((_utcnow() - started_at).total_seconds() * 1000)

    return RefreshAclRetentionSummary(
        dry_run=bool(dry_run),
        config={
            "audit_retention_days": int(config.audit_retention_days),
            "terminal_job_retention_days": int(config.terminal_job_retention_days),
            "terminal_statuses": list(config.terminal_statuses),
            "audit_cutoff": config.audit_cutoff.isoformat(),
            "terminal_job_cutoff": config.terminal_job_cutoff.isoformat(),
        },
        before=before,
        candidates=candidates,
        deleted=deleted,
        after=after,
        safety={
            "non_terminal_job_delete_candidates": int(non_terminal_delete_candidates),
            "guards_passed": int(non_terminal_delete_candidates) == 0,
        },
        generated_at=(config.now if config.now.tzinfo else config.now.replace(tzinfo=timezone.utc)).isoformat(),
        run_status="success",
        aborted_reason_code=None,
        guardrails={},
        duration_ms=duration_ms,
    )


def run_refresh_acl_retention_with_guardrails(
    db: Session,
    *,
    config: RefreshAclRetentionConfig,
    dry_run: bool,
    guardrails: RefreshAclRetentionGuardrailConfig,
) -> RefreshAclRetentionSummary:
    started_at = _utcnow()
    precheck = run_refresh_acl_retention(db, config=config, dry_run=True)

    total_audit_delete_candidates = int(precheck.candidates.get("audit_rows_for_terminal_jobs", 0)) + int(
        precheck.candidates.get("aged_terminal_audit_rows", 0)
    )
    candidate_map = {
        "terminal_jobs": int(precheck.candidates.get("terminal_jobs", 0)),
        "audit_rows": int(total_audit_delete_candidates),
        "acl_rows": int(precheck.candidates.get("acl_rows_for_terminal_jobs", 0)),
    }
    cap_map = {
        "terminal_jobs": int(guardrails.max_delete_terminal_jobs),
        "audit_rows": int(guardrails.max_delete_audit_rows),
        "acl_rows": int(guardrails.max_delete_acl_rows),
    }

    cap_exceeded = [
        {
            "name": key,
            "candidate_count": int(candidate_map[key]),
            "max_allowed": int(cap_map[key]),
        }
        for key in ("terminal_jobs", "audit_rows", "acl_rows")
        if int(candidate_map[key]) > int(cap_map[key])
    ]

    non_terminal_risk = int(precheck.safety.get("non_terminal_job_delete_candidates", 0))
    aborted_reason_code: str | None = None
    if non_terminal_risk > 0:
        aborted_reason_code = "non_terminal_delete_risk"
    elif cap_exceeded and not bool(guardrails.allow_cap_breach):
        aborted_reason_code = "delete_cap_exceeded"

    duration_ms = int((_utcnow() - started_at).total_seconds() * 1000)
    guardrail_payload = {
        "allow_cap_breach": bool(guardrails.allow_cap_breach),
        "caps": cap_map,
        "candidate_totals": candidate_map,
        "cap_exceeded": cap_exceeded,
        "non_terminal_job_delete_candidates": non_terminal_risk,
    }

    if aborted_reason_code is not None:
        return RefreshAclRetentionSummary(
            dry_run=bool(dry_run),
            config=dict(precheck.config),
            before=dict(precheck.before),
            candidates=dict(precheck.candidates),
            deleted={
                "terminal_jobs": 0,
                "audit_rows_for_terminal_jobs": 0,
                "acl_rows_for_terminal_jobs": 0,
                "aged_terminal_audit_rows": 0,
            },
            after=dict(precheck.before),
            safety={
                "non_terminal_job_delete_candidates": non_terminal_risk,
                "guards_passed": False,
            },
            generated_at=precheck.generated_at,
            run_status="aborted",
            aborted_reason_code=aborted_reason_code,
            guardrails=guardrail_payload,
            duration_ms=duration_ms,
        )

    if dry_run:
        return RefreshAclRetentionSummary(
            dry_run=True,
            config=dict(precheck.config),
            before=dict(precheck.before),
            candidates=dict(precheck.candidates),
            deleted=dict(precheck.deleted),
            after=dict(precheck.after),
            safety=dict(precheck.safety),
            generated_at=precheck.generated_at,
            run_status="success",
            aborted_reason_code=None,
            guardrails=guardrail_payload,
            duration_ms=duration_ms,
        )

    executed = run_refresh_acl_retention(db, config=config, dry_run=False)
    duration_ms = int((_utcnow() - started_at).total_seconds() * 1000)
    return RefreshAclRetentionSummary(
        dry_run=False,
        config=dict(executed.config),
        before=dict(executed.before),
        candidates=dict(executed.candidates),
        deleted=dict(executed.deleted),
        after=dict(executed.after),
        safety=dict(executed.safety),
        generated_at=executed.generated_at,
        run_status="success",
        aborted_reason_code=None,
        guardrails=guardrail_payload,
        duration_ms=duration_ms,
    )
