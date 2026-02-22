from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.database import Base
from api.models import RefreshJob, RefreshJobAclEntry, RefreshJobAuditEvent, User
from api.services import refresh_acl_retention_service as retention_service_module
from api.services.refresh_acl_retention_automation_service import (
    execute_refresh_acl_retention_automation,
    run_refresh_acl_retention_schedule,
)
from api.services.refresh_acl_retention_service import (
    RefreshAclRetentionConfig,
    RefreshAclRetentionGuardrailConfig,
    RefreshAclRetentionSummary,
)
from api.services.refresh_job_acl_service import RefreshJobAclService


class _FakeRedis:
    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def delete(self, key):
        self.store.pop(key, None)
        return 1


def _build_session(tmp_path: Path):
    db_path = tmp_path / "refresh_acl_retention_automation.sqlite"
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


def _add_job(
    db,
    *,
    job_id: str,
    owner_id: int,
    shared_id: int | None,
    status: str,
    now: datetime,
    age_days: int,
    completed_days: int | None,
):
    created = now - timedelta(days=age_days)
    completed = (now - timedelta(days=completed_days)) if completed_days is not None else None
    job = RefreshJob(
        job_id=job_id,
        owner_user_id=owner_id,
        status=status,
        source="automation-test",
        requested_at=created,
        enqueued_at=created,
        started_at=created,
        completed_at=completed,
        payload={"requested_by": owner_id},
        created_at=created,
        updated_at=created,
    )
    db.add(job)
    db.flush()

    db.add(
        RefreshJobAclEntry(
            refresh_job_id=job.id,
            user_id=owner_id,
            access_type="read",
            is_active=True,
            grant_reason="owner",
            created_at=created,
            updated_at=created,
        )
    )
    if shared_id is not None:
        db.add(
            RefreshJobAclEntry(
                refresh_job_id=job.id,
                user_id=shared_id,
                access_type="read",
                is_active=True,
                grant_reason="shared",
                created_at=created,
                updated_at=created,
            )
        )
    db.add(
        RefreshJobAuditEvent(
            refresh_job_id=job.id,
            job_id=job_id,
            action_type="seed",
            decision="allow",
            reason_code="seed",
            actor_user_id=owner_id,
            actor_sub="seed",
            created_at=created,
        )
    )
    db.commit()
    return job.id


def _base_configs(now: datetime):
    retention = RefreshAclRetentionConfig(
        audit_retention_days=30,
        terminal_job_retention_days=14,
        terminal_statuses=("success", "failed"),
        now=now,
    )
    guardrails = RefreshAclRetentionGuardrailConfig(
        max_delete_terminal_jobs=100,
        max_delete_audit_rows=1000,
        max_delete_acl_rows=500,
        allow_cap_breach=False,
    )
    return retention, guardrails


def test_schedule_path_runs_multiple_iterations_with_structured_output():
    class _Result:
        def __init__(self, idx: int):
            self.idx = idx

        def to_dict(self):
            return {"idx": self.idx, "run_status": "success"}

    calls = []

    def _runner(*, dry_run, **_kwargs):
        calls.append(bool(dry_run))
        return _Result(len(calls))

    report = run_refresh_acl_retention_schedule(
        max_runs=2,
        interval_seconds=0,
        runner=_runner,
        dry_run=True,
        sleep_fn=lambda _seconds: None,
    )

    assert report["run_count"] == 2
    assert report["dry_run"] is True
    assert calls == [True, True]
    assert report["runs"][0]["idx"] == 1
    assert report["runs"][1]["idx"] == 2


def test_automation_lock_guard_aborts_when_lock_not_acquired(tmp_path, monkeypatch):
    SessionLocal, engine = _build_session(tmp_path)
    fake_redis = _FakeRedis()
    fake_redis.set("maintenance:lock", "held", nx=False)
    emitted = []
    monkeypatch.setattr(
        "api.services.refresh_acl_retention_automation_service.emit_observability_event",
        lambda **kwargs: emitted.append(kwargs) or "1-1",
    )

    now = datetime(2026, 2, 22, tzinfo=timezone.utc)
    retention, guardrails = _base_configs(now)

    try:
        result = execute_refresh_acl_retention_automation(
            dry_run=True,
            retention_config=retention,
            guardrail_config=guardrails,
            lock_key="maintenance:lock",
            redis_client=fake_redis,
            db_factory=SessionLocal,
        )
        assert result.run_status == "aborted"
        assert result.reason_code == "lock_not_acquired"
        assert result.lock_acquired is False
        assert result.summary.get("aborted_reason_code") == "lock_not_acquired"
        assert emitted and emitted[-1]["action_type"] == "refresh_acl_retention_aborted"
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_automation_non_terminal_risk_guard_aborts_without_delete(tmp_path, monkeypatch):
    SessionLocal, engine = _build_session(tmp_path)
    fake_redis = _FakeRedis()
    monkeypatch.setattr(
        "api.services.refresh_acl_retention_automation_service.emit_observability_event",
        lambda **_kwargs: "1-1",
    )

    now = datetime(2026, 2, 22, tzinfo=timezone.utc)
    retention, guardrails = _base_configs(now)

    original_run = retention_service_module.run_refresh_acl_retention

    def _fake_run(db, *, config, dry_run):
        if dry_run:
            return RefreshAclRetentionSummary(
                dry_run=True,
                config={"audit_retention_days": 30},
                before={"total_jobs": 1},
                candidates={
                    "terminal_jobs": 1,
                    "audit_rows_for_terminal_jobs": 1,
                    "acl_rows_for_terminal_jobs": 1,
                    "aged_terminal_audit_rows": 0,
                },
                deleted={
                    "terminal_jobs": 0,
                    "audit_rows_for_terminal_jobs": 0,
                    "acl_rows_for_terminal_jobs": 0,
                    "aged_terminal_audit_rows": 0,
                },
                after={"total_jobs": 1},
                safety={"non_terminal_job_delete_candidates": 1, "guards_passed": False},
                generated_at=config.now.isoformat(),
            )
        raise AssertionError("execute path must not run when non-terminal risk guard aborts")

    monkeypatch.setattr(retention_service_module, "run_refresh_acl_retention", _fake_run)

    try:
        result = execute_refresh_acl_retention_automation(
            dry_run=False,
            retention_config=retention,
            guardrail_config=guardrails,
            lock_key="maintenance:non-terminal",
            redis_client=fake_redis,
            db_factory=SessionLocal,
        )
        assert result.run_status == "aborted"
        assert result.reason_code == "non_terminal_delete_risk"
        assert result.summary.get("deleted", {}).get("terminal_jobs") == 0
    finally:
        monkeypatch.setattr(retention_service_module, "run_refresh_acl_retention", original_run)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_automation_delete_cap_guard_aborts_without_override(tmp_path, monkeypatch):
    SessionLocal, engine = _build_session(tmp_path)
    fake_redis = _FakeRedis()
    monkeypatch.setattr(
        "api.services.refresh_acl_retention_automation_service.emit_observability_event",
        lambda **_kwargs: "1-1",
    )

    now = datetime(2026, 2, 22, tzinfo=timezone.utc)
    retention, _guardrails = _base_configs(now)
    guardrails = RefreshAclRetentionGuardrailConfig(
        max_delete_terminal_jobs=0,
        max_delete_audit_rows=0,
        max_delete_acl_rows=0,
        allow_cap_breach=False,
    )

    db = SessionLocal()
    try:
        owner, shared, _ = _seed_users(db)
        _add_job(
            db,
            job_id="terminal-old",
            owner_id=owner.id,
            shared_id=shared.id,
            status="success",
            now=now,
            age_days=40,
            completed_days=40,
        )
    finally:
        db.close()

    try:
        result = execute_refresh_acl_retention_automation(
            dry_run=False,
            retention_config=retention,
            guardrail_config=guardrails,
            lock_key="maintenance:cap-guard",
            redis_client=fake_redis,
            db_factory=SessionLocal,
        )
        assert result.run_status == "aborted"
        assert result.reason_code == "delete_cap_exceeded"
        assert result.summary.get("deleted", {}).get("terminal_jobs") == 0

        db = SessionLocal()
        try:
            still_exists = db.query(RefreshJob).filter(RefreshJob.job_id == "terminal-old").first()
            assert still_exists is not None
        finally:
            db.close()
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_automation_execute_success_preserves_non_terminal_acl_authority(tmp_path, monkeypatch):
    SessionLocal, engine = _build_session(tmp_path)
    fake_redis = _FakeRedis()
    monkeypatch.setattr(
        "api.services.refresh_acl_retention_automation_service.emit_observability_event",
        lambda **_kwargs: "1-1",
    )

    now = datetime(2026, 2, 22, tzinfo=timezone.utc)
    retention, guardrails = _base_configs(now)

    db = SessionLocal()
    try:
        owner, shared, outsider = _seed_users(db)
        shared_id = shared.id
        outsider_id = outsider.id
        _add_job(
            db,
            job_id="terminal-old",
            owner_id=owner.id,
            shared_id=shared.id,
            status="success",
            now=now,
            age_days=45,
            completed_days=45,
        )
        _add_job(
            db,
            job_id="pending-valid",
            owner_id=owner.id,
            shared_id=shared.id,
            status="pending",
            now=now,
            age_days=1,
            completed_days=None,
        )
    finally:
        db.close()

    try:
        result = execute_refresh_acl_retention_automation(
            dry_run=False,
            retention_config=retention,
            guardrail_config=guardrails,
            lock_key="maintenance:success",
            redis_client=fake_redis,
            db_factory=SessionLocal,
        )
        assert result.run_status == "success"
        assert result.reason_code == "success"
        assert result.summary.get("deleted", {}).get("terminal_jobs") == 1

        db = SessionLocal()
        try:
            pending = RefreshJobAclService.get_job_by_job_id(db, job_id="pending-valid")
            assert pending is not None
            terminal = RefreshJobAclService.get_job_by_job_id(db, job_id="terminal-old")
            assert terminal is None

            shared_decision = RefreshJobAclService.access_decision(
                db,
                job=pending,
                actor_user_id=shared_id,
                actor_sub="shared-user",
            )
            outsider_decision = RefreshJobAclService.access_decision(
                db,
                job=pending,
                actor_user_id=outsider_id,
                actor_sub="outsider-user",
            )
            assert shared_decision.allowed is True
            assert outsider_decision.allowed is False
        finally:
            db.close()
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
