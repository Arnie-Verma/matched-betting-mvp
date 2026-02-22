"""Durable refresh job ACL + audit persistence service."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from api.models import RefreshJob, RefreshJobAclEntry, RefreshJobAuditEvent


class RefreshJobAclError(ValueError):
    """Raised when refresh-job ACL policy checks fail."""

    def __init__(self, *, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class RefreshJobAccessDecision:
    allowed: bool
    reason_code: str
    owner_user_id: Optional[int]
    shared_user_count: int
    source: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return dict(payload)


def _shared_user_ids_from_payload(payload: Dict[str, Any]) -> set[int]:
    raw = payload.get("shared_user_ids")
    if not isinstance(raw, list):
        return set()
    shared: set[int] = set()
    for item in raw:
        value = _as_int(item)
        if value is not None:
            shared.add(value)
    return shared


class RefreshJobAclService:
    """Durable source of truth for refresh ownership, sharing, and status access audit."""

    @staticmethod
    def _record_event(
        db: Session,
        *,
        job: RefreshJob,
        action_type: str,
        decision: Optional[str],
        reason_code: Optional[str],
        actor_user_id: Optional[int],
        actor_sub: Optional[str],
        event_metadata: Optional[Dict[str, Any]] = None,
    ) -> RefreshJobAuditEvent:
        event = RefreshJobAuditEvent(
            refresh_job_id=int(job.id),
            job_id=job.job_id,
            action_type=action_type,
            decision=decision,
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            actor_sub=actor_sub,
            event_metadata=dict(event_metadata or {}),
            created_at=_utcnow(),
        )
        db.add(event)
        return event

    @classmethod
    def get_job_by_job_id(cls, db: Session, *, job_id: str) -> Optional[RefreshJob]:
        return (
            db.query(RefreshJob)
            .options(joinedload(RefreshJob.acl_entries))
            .filter(RefreshJob.job_id == (job_id or "").strip())
            .first()
        )

    @staticmethod
    def _effective_shared_user_count(job: RefreshJob) -> int:
        owner_id = int(job.owner_user_id)
        shared_ids = {
            int(entry.user_id)
            for entry in (job.acl_entries or [])
            if bool(entry.is_active) and int(entry.user_id) != owner_id
        }
        return len(shared_ids)

    @classmethod
    def create_job(
        cls,
        db: Session,
        *,
        job_id: str,
        owner_user_id: int,
        payload: Optional[Dict[str, Any]],
        actor_user_id: Optional[int],
        actor_sub: Optional[str],
        source: str = "redis_queue_v1",
    ) -> RefreshJob:
        normalized_job_id = (job_id or "").strip()
        if not normalized_job_id:
            raise RefreshJobAclError(
                reason_code="invalid_job_id",
                message="refresh job id is required",
            )

        existing = cls.get_job_by_job_id(db, job_id=normalized_job_id)
        if existing:
            return existing

        normalized_payload = _normalize_payload(payload)
        requested_at = _parse_dt(normalized_payload.get("requested_at")) or _utcnow()
        enqueued_at = _parse_dt(normalized_payload.get("enqueued_at")) or _utcnow()

        job = RefreshJob(
            job_id=normalized_job_id,
            owner_user_id=int(owner_user_id),
            status="pending",
            source=(source or "redis_queue_v1").strip() or "redis_queue_v1",
            requested_at=requested_at,
            enqueued_at=enqueued_at,
            payload=normalized_payload,
            attempts=0,
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.add(job)
        db.flush()

        owner_acl = RefreshJobAclEntry(
            refresh_job_id=int(job.id),
            user_id=int(owner_user_id),
            access_type="read",
            is_active=True,
            granted_by_user_id=actor_user_id,
            grant_reason="owner",
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        db.add(owner_acl)

        cls._record_event(
            db,
            job=job,
            action_type="job_create",
            decision="allow",
            reason_code="created",
            actor_user_id=actor_user_id,
            actor_sub=actor_sub,
            event_metadata={
                "owner_user_id": int(owner_user_id),
                "source": job.source,
            },
        )

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = cls.get_job_by_job_id(db, job_id=normalized_job_id)
            if existing:
                return existing
            raise

        refreshed = cls.get_job_by_job_id(db, job_id=normalized_job_id)
        if refreshed is None:
            raise RefreshJobAclError(
                reason_code="refresh_job_create_failed",
                message=f"Refresh job '{normalized_job_id}' create failed",
            )
        return refreshed

    @classmethod
    def share_job_with_user(
        cls,
        db: Session,
        *,
        job: RefreshJob,
        user_id: int,
        actor_user_id: Optional[int],
        actor_sub: Optional[str],
        reason_code: str,
    ) -> bool:
        target_user_id = int(user_id)
        now = _utcnow()
        changed = False

        entry = next(
            (
                item
                for item in (job.acl_entries or [])
                if int(item.user_id) == target_user_id and item.access_type == "read"
            ),
            None,
        )
        if entry is None:
            db.add(
                RefreshJobAclEntry(
                    refresh_job_id=int(job.id),
                    user_id=target_user_id,
                    access_type="read",
                    is_active=True,
                    granted_by_user_id=actor_user_id,
                    grant_reason=reason_code,
                    created_at=now,
                    updated_at=now,
                )
            )
            changed = True
        elif not bool(entry.is_active):
            entry.is_active = True
            entry.granted_by_user_id = actor_user_id
            entry.grant_reason = reason_code
            entry.revoked_at = None
            entry.updated_at = now
            db.add(entry)
            changed = True

        if changed:
            cls._record_event(
                db,
                job=job,
                action_type="acl_share_update",
                decision="allow",
                reason_code=reason_code,
                actor_user_id=actor_user_id,
                actor_sub=actor_sub,
                event_metadata={
                    "shared_user_id": target_user_id,
                },
            )
            job.updated_at = now
            db.add(job)
            db.commit()
        return changed

    @classmethod
    def unshare_job_with_user(
        cls,
        db: Session,
        *,
        job: RefreshJob,
        user_id: int,
        actor_user_id: Optional[int],
        actor_sub: Optional[str],
        reason_code: str,
    ) -> bool:
        target_user_id = int(user_id)
        entry = next(
            (
                item
                for item in (job.acl_entries or [])
                if int(item.user_id) == target_user_id and item.access_type == "read"
            ),
            None,
        )
        if entry is None or not bool(entry.is_active):
            return False

        now = _utcnow()
        entry.is_active = False
        entry.revoked_at = now
        entry.updated_at = now
        db.add(entry)

        cls._record_event(
            db,
            job=job,
            action_type="acl_unshare_update",
            decision="allow",
            reason_code=reason_code,
            actor_user_id=actor_user_id,
            actor_sub=actor_sub,
            event_metadata={
                "unshared_user_id": target_user_id,
            },
        )
        job.updated_at = now
        db.add(job)
        db.commit()
        return True

    @classmethod
    def share_job_with_user_if_exists(
        cls,
        db: Session,
        *,
        job_id: str,
        user_id: int,
        actor_user_id: Optional[int],
        actor_sub: Optional[str],
        reason_code: str,
    ) -> bool:
        job = cls.get_job_by_job_id(db, job_id=job_id)
        if not job:
            return False
        return cls.share_job_with_user(
            db,
            job=job,
            user_id=user_id,
            actor_user_id=actor_user_id,
            actor_sub=actor_sub,
            reason_code=reason_code,
        )

    @classmethod
    def access_decision(
        cls,
        db: Session,
        *,
        job: RefreshJob,
        actor_user_id: int,
        actor_sub: Optional[str],
    ) -> RefreshJobAccessDecision:
        user_id = int(actor_user_id)
        owner_user_id = int(job.owner_user_id)
        allowed_user_ids = {
            int(entry.user_id)
            for entry in (job.acl_entries or [])
            if bool(entry.is_active)
        }

        reason_code = "owner"
        allowed = user_id == owner_user_id
        if not allowed:
            if user_id in allowed_user_ids:
                allowed = True
                reason_code = "shared_acl"
            else:
                reason_code = "not_shared"

        shared_user_count = cls._effective_shared_user_count(job)
        cls._record_event(
            db,
            job=job,
            action_type="status_access_allow" if allowed else "status_access_deny",
            decision="allow" if allowed else "deny",
            reason_code=reason_code,
            actor_user_id=user_id,
            actor_sub=actor_sub,
            event_metadata={
                "owner_user_id": owner_user_id,
                "shared_user_count": shared_user_count,
            },
        )
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()

        return RefreshJobAccessDecision(
            allowed=allowed,
            reason_code=reason_code,
            owner_user_id=owner_user_id,
            shared_user_count=shared_user_count,
            source="durable_acl",
        )

    @classmethod
    def backfill_job_from_legacy_payload(
        cls,
        db: Session,
        *,
        job_id: str,
        legacy_job_status: Dict[str, Any],
        actor_sub: Optional[str],
    ) -> Optional[RefreshJob]:
        existing = cls.get_job_by_job_id(db, job_id=job_id)
        if existing:
            return existing

        payload = _normalize_payload((legacy_job_status or {}).get("payload") or {})
        owner_user_id = _as_int(payload.get("requested_by"))
        if owner_user_id is None:
            return None

        job = cls.create_job(
            db,
            job_id=job_id,
            owner_user_id=owner_user_id,
            payload=payload,
            actor_user_id=owner_user_id,
            actor_sub=actor_sub or "legacy-backfill",
            source="legacy_redis_payload_backfill",
        )

        # Promote runtime fields from legacy payload snapshot.
        cls.update_runtime_state(
            db,
            job_id=job_id,
            status=(legacy_job_status or {}).get("status"),
            enqueued_at=(legacy_job_status or {}).get("enqueued_at"),
            started_at=(legacy_job_status or {}).get("started_at"),
            completed_at=(legacy_job_status or {}).get("completed_at"),
            message=(legacy_job_status or {}).get("message"),
            errors=(legacy_job_status or {}).get("errors"),
            result=(legacy_job_status or {}).get("result"),
            attempts=(legacy_job_status or {}).get("attempts"),
            payload=payload,
        )

        for shared_user_id in sorted(_shared_user_ids_from_payload(payload)):
            if shared_user_id == owner_user_id:
                continue
            cls.share_job_with_user_if_exists(
                db,
                job_id=job_id,
                user_id=shared_user_id,
                actor_user_id=owner_user_id,
                actor_sub=actor_sub or "legacy-backfill",
                reason_code="legacy_shared_payload_backfill",
            )

        job = cls.get_job_by_job_id(db, job_id=job_id)
        if not job:
            return None

        cls._record_event(
            db,
            job=job,
            action_type="job_backfill",
            decision="allow",
            reason_code="legacy_payload_backfill",
            actor_user_id=owner_user_id,
            actor_sub=actor_sub or "legacy-backfill",
            event_metadata={
                "shared_user_count": cls._effective_shared_user_count(job),
            },
        )
        job.updated_at = _utcnow()
        db.add(job)
        db.commit()
        return cls.get_job_by_job_id(db, job_id=job_id)

    @classmethod
    def update_runtime_state(
        cls,
        db: Session,
        *,
        job_id: str,
        status: Optional[str] = None,
        enqueued_at: Any = None,
        started_at: Any = None,
        completed_at: Any = None,
        message: Optional[str] = None,
        errors: Any = None,
        result: Any = None,
        attempts: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[RefreshJob]:
        job = cls.get_job_by_job_id(db, job_id=job_id)
        if not job:
            return None

        if status:
            job.status = str(status)
        parsed_enqueued = _parse_dt(enqueued_at)
        parsed_started = _parse_dt(started_at)
        parsed_completed = _parse_dt(completed_at)
        if parsed_enqueued:
            job.enqueued_at = parsed_enqueued
        if parsed_started:
            job.started_at = parsed_started
        if parsed_completed:
            job.completed_at = parsed_completed
        if message is not None:
            job.message = str(message)
        if errors is not None:
            job.errors = errors
        if result is not None:
            job.result = result
        if attempts is not None:
            job.attempts = int(attempts)
        if payload is not None:
            job.payload = _normalize_payload(payload)

        job.updated_at = _utcnow()
        db.add(job)
        db.commit()
        return cls.get_job_by_job_id(db, job_id=job_id)

    @classmethod
    def status_payload_from_durable_job(cls, job: RefreshJob) -> Dict[str, Any]:
        return {
            "status": job.status,
            "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "message": job.message,
            "errors": job.errors,
            "result": job.result,
            "payload": job.payload or {},
            "attempts": job.attempts,
            "source": "durable_refresh_job",
        }
