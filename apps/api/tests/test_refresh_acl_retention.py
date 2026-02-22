from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.database import Base
from api.models import RefreshJob, RefreshJobAclEntry, RefreshJobAuditEvent, User
from api.services.refresh_acl_retention_service import RefreshAclRetentionConfig, run_refresh_acl_retention
from api.services.refresh_job_acl_service import RefreshJobAclService


def _build_session(tmp_path: Path):
    db_path = tmp_path / "refresh_acl_retention.sqlite"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal, engine


def _seed_users(db):
    owner = User(
        clerk_user_id="owner-user",
        email="owner@test.local",
        email_verified=True,
        current_plan="free",
        plan_status="active",
    )
    shared = User(
        clerk_user_id="shared-user",
        email="shared@test.local",
        email_verified=True,
        current_plan="free",
        plan_status="active",
    )
    outsider = User(
        clerk_user_id="outsider-user",
        email="outsider@test.local",
        email_verified=True,
        current_plan="free",
        plan_status="active",
    )
    db.add_all([owner, shared, outsider])
    db.commit()
    db.refresh(owner)
    db.refresh(shared)
    db.refresh(outsider)
    return owner, shared, outsider


def _create_refresh_job_with_rows(
    db,
    *,
    job_id: str,
    owner_user_id: int,
    shared_user_id: int | None,
    status: str,
    created_at: datetime,
    updated_at: datetime,
    completed_at: datetime | None,
    audit_timestamps: list[datetime],
):
    job = RefreshJob(
        job_id=job_id,
        owner_user_id=owner_user_id,
        status=status,
        source="retention-test",
        requested_at=created_at,
        enqueued_at=created_at,
        started_at=created_at,
        completed_at=completed_at,
        message=f"{job_id}:{status}",
        payload={"requested_by": owner_user_id},
        created_at=created_at,
        updated_at=updated_at,
    )
    db.add(job)
    db.flush()

    owner_acl = RefreshJobAclEntry(
        refresh_job_id=job.id,
        user_id=owner_user_id,
        access_type="read",
        is_active=True,
        grant_reason="owner",
        created_at=created_at,
        updated_at=updated_at,
    )
    db.add(owner_acl)

    if shared_user_id is not None:
        shared_acl = RefreshJobAclEntry(
            refresh_job_id=job.id,
            user_id=shared_user_id,
            access_type="read",
            is_active=True,
            grant_reason="shared",
            created_at=created_at,
            updated_at=updated_at,
        )
        db.add(shared_acl)

    for index, ts in enumerate(audit_timestamps):
        db.add(
            RefreshJobAuditEvent(
                refresh_job_id=job.id,
                job_id=job_id,
                action_type=f"audit_{index}",
                decision="allow",
                reason_code="synthetic",
                actor_user_id=owner_user_id,
                actor_sub="owner-user",
                event_metadata={"index": index},
                created_at=ts,
            )
        )
    db.commit()
    return job.id


def _retention_config(base_now: datetime) -> RefreshAclRetentionConfig:
    return RefreshAclRetentionConfig(
        audit_retention_days=30,
        terminal_job_retention_days=14,
        terminal_statuses=("success", "failed"),
        now=base_now,
    )


def test_refresh_acl_retention_dry_run_reports_candidates_without_deletes(tmp_path):
    SessionLocal, engine = _build_session(tmp_path)
    base_now = datetime(2026, 2, 22, tzinfo=timezone.utc)
    db = SessionLocal()
    try:
        owner, shared, _ = _seed_users(db)

        _create_refresh_job_with_rows(
            db,
            job_id="terminal-old",
            owner_user_id=owner.id,
            shared_user_id=shared.id,
            status="success",
            created_at=base_now - timedelta(days=40),
            updated_at=base_now - timedelta(days=40),
            completed_at=base_now - timedelta(days=40),
            audit_timestamps=[base_now - timedelta(days=40)],
        )
        _create_refresh_job_with_rows(
            db,
            job_id="terminal-recent-with-old-audit",
            owner_user_id=owner.id,
            shared_user_id=None,
            status="failed",
            created_at=base_now - timedelta(days=3),
            updated_at=base_now - timedelta(days=3),
            completed_at=base_now - timedelta(days=3),
            audit_timestamps=[base_now - timedelta(days=35), base_now - timedelta(days=1)],
        )
        _create_refresh_job_with_rows(
            db,
            job_id="running-old",
            owner_user_id=owner.id,
            shared_user_id=shared.id,
            status="running",
            created_at=base_now - timedelta(days=60),
            updated_at=base_now - timedelta(days=60),
            completed_at=None,
            audit_timestamps=[base_now - timedelta(days=60)],
        )

        summary = run_refresh_acl_retention(
            db,
            config=_retention_config(base_now),
            dry_run=True,
        )

        assert summary.dry_run is True
        assert summary.candidates["terminal_jobs"] == 1
        assert summary.candidates["audit_rows_for_terminal_jobs"] == 1
        assert summary.candidates["acl_rows_for_terminal_jobs"] == 2
        assert summary.candidates["aged_terminal_audit_rows"] == 1
        assert summary.deleted["terminal_jobs"] == 0
        assert summary.deleted["aged_terminal_audit_rows"] == 0
        assert summary.before == summary.after
        assert summary.safety["guards_passed"] is True
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_refresh_acl_retention_execute_deletes_only_old_terminal_data(tmp_path):
    SessionLocal, engine = _build_session(tmp_path)
    base_now = datetime(2026, 2, 22, tzinfo=timezone.utc)
    db = SessionLocal()
    try:
        owner, shared, _ = _seed_users(db)

        old_terminal_id = _create_refresh_job_with_rows(
            db,
            job_id="terminal-old",
            owner_user_id=owner.id,
            shared_user_id=shared.id,
            status="success",
            created_at=base_now - timedelta(days=45),
            updated_at=base_now - timedelta(days=45),
            completed_at=base_now - timedelta(days=45),
            audit_timestamps=[base_now - timedelta(days=45)],
        )
        recent_terminal_id = _create_refresh_job_with_rows(
            db,
            job_id="terminal-recent-with-old-audit",
            owner_user_id=owner.id,
            shared_user_id=None,
            status="failed",
            created_at=base_now - timedelta(days=4),
            updated_at=base_now - timedelta(days=4),
            completed_at=base_now - timedelta(days=4),
            audit_timestamps=[base_now - timedelta(days=35), base_now - timedelta(days=2)],
        )
        running_old_id = _create_refresh_job_with_rows(
            db,
            job_id="running-old",
            owner_user_id=owner.id,
            shared_user_id=shared.id,
            status="running",
            created_at=base_now - timedelta(days=70),
            updated_at=base_now - timedelta(days=70),
            completed_at=None,
            audit_timestamps=[base_now - timedelta(days=70)],
        )

        summary = run_refresh_acl_retention(
            db,
            config=_retention_config(base_now),
            dry_run=False,
        )

        assert summary.deleted["terminal_jobs"] == 1
        assert summary.deleted["acl_rows_for_terminal_jobs"] == 2
        assert summary.deleted["audit_rows_for_terminal_jobs"] == 1
        assert summary.deleted["aged_terminal_audit_rows"] == 1
        assert summary.safety["guards_passed"] is True

        assert db.query(RefreshJob).filter(RefreshJob.id == old_terminal_id).first() is None
        assert db.query(RefreshJob).filter(RefreshJob.id == recent_terminal_id).first() is not None
        assert db.query(RefreshJob).filter(RefreshJob.id == running_old_id).first() is not None

        # Old non-terminal audit must remain (safety guard).
        non_terminal_audits = (
            db.query(RefreshJobAuditEvent)
            .filter(RefreshJobAuditEvent.refresh_job_id == running_old_id)
            .count()
        )
        assert non_terminal_audits == 1

        # Recent terminal job keeps recent audit row after age-based pruning.
        remaining_recent_terminal_audits = (
            db.query(RefreshJobAuditEvent)
            .filter(RefreshJobAuditEvent.refresh_job_id == recent_terminal_id)
            .count()
        )
        assert remaining_recent_terminal_audits == 1
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_refresh_acl_retention_preserves_active_acl_authority_for_valid_jobs(tmp_path):
    SessionLocal, engine = _build_session(tmp_path)
    base_now = datetime(2026, 2, 22, tzinfo=timezone.utc)
    db = SessionLocal()
    try:
        owner, shared, outsider = _seed_users(db)

        _create_refresh_job_with_rows(
            db,
            job_id="pending-valid",
            owner_user_id=owner.id,
            shared_user_id=shared.id,
            status="pending",
            created_at=base_now - timedelta(days=1),
            updated_at=base_now - timedelta(days=1),
            completed_at=None,
            audit_timestamps=[base_now - timedelta(days=1)],
        )

        run_refresh_acl_retention(
            db,
            config=_retention_config(base_now),
            dry_run=False,
        )

        refreshed = RefreshJobAclService.get_job_by_job_id(db, job_id="pending-valid")
        assert refreshed is not None

        shared_decision = RefreshJobAclService.access_decision(
            db,
            job=refreshed,
            actor_user_id=shared.id,
            actor_sub="shared-user",
        )
        outsider_decision = RefreshJobAclService.access_decision(
            db,
            job=refreshed,
            actor_user_id=outsider.id,
            actor_sub="outsider-user",
        )

        assert shared_decision.allowed is True
        assert outsider_decision.allowed is False
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
