"""Generate PR26 synthetic automation run evidence for retention guardrails."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.database import Base
from api.models import RefreshJob, RefreshJobAclEntry, RefreshJobAuditEvent, User
from api.services import refresh_acl_retention_service as retention_service_module
from api.services.refresh_acl_retention_automation_service import execute_refresh_acl_retention_automation
from api.services.refresh_acl_retention_service import (
    RefreshAclRetentionConfig,
    RefreshAclRetentionGuardrailConfig,
    RefreshAclRetentionSummary,
)


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


def _seed_users(db):
    owner = User(
        clerk_user_id="owner",
        email="owner@test.local",
        email_verified=True,
        current_plan="free",
        plan_status="active",
    )
    shared = User(
        clerk_user_id="shared",
        email="shared@test.local",
        email_verified=True,
        current_plan="free",
        plan_status="active",
    )
    db.add_all([owner, shared])
    db.commit()
    db.refresh(owner)
    db.refresh(shared)
    return owner, shared


def _add_job(db, *, owner_id: int, shared_id: int, now: datetime, job_id: str, status: str, age_days: int, completed_days: int | None):
    created = now - timedelta(days=age_days)
    completed = (now - timedelta(days=completed_days)) if completed_days is not None else None
    job = RefreshJob(
        job_id=job_id,
        owner_user_id=owner_id,
        status=status,
        source="pr26",
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
    db.add(RefreshJobAclEntry(refresh_job_id=job.id, user_id=owner_id, access_type="read", is_active=True, grant_reason="owner", created_at=created, updated_at=created))
    db.add(RefreshJobAclEntry(refresh_job_id=job.id, user_id=shared_id, access_type="read", is_active=True, grant_reason="shared", created_at=created, updated_at=created))
    db.add(RefreshJobAuditEvent(refresh_job_id=job.id, job_id=job_id, action_type="seed", decision="allow", reason_code="seed", actor_user_id=owner_id, actor_sub="seed", created_at=created))
    db.commit()


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


def main() -> None:
    base_now = datetime(2026, 2, 22, tzinfo=timezone.utc)
    fake_redis = _FakeRedis()

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "pr26_retention_automation.sqlite"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)

        db = SessionLocal()
        owner, shared = _seed_users(db)
        _add_job(db, owner_id=owner.id, shared_id=shared.id, now=base_now, job_id="terminal-old", status="success", age_days=45, completed_days=45)
        _add_job(db, owner_id=owner.id, shared_id=shared.id, now=base_now, job_id="pending-valid", status="pending", age_days=1, completed_days=None)
        db.close()

        retention, guardrails = _base_configs(base_now)

        runs = []

        # 1) Dry-run success.
        runs.append(
            execute_refresh_acl_retention_automation(
                dry_run=True,
                retention_config=retention,
                guardrail_config=guardrails,
                lock_key="pr26:lock",
                redis_client=fake_redis,
                db_factory=SessionLocal,
            ).to_dict()
        )

        # 2) Lock contention abort.
        fake_redis.set("pr26:lock-contention", "held", nx=False)
        runs.append(
            execute_refresh_acl_retention_automation(
                dry_run=True,
                retention_config=retention,
                guardrail_config=guardrails,
                lock_key="pr26:lock-contention",
                redis_client=fake_redis,
                db_factory=SessionLocal,
            ).to_dict()
        )

        # 3) Cap-abort execute.
        strict_caps = RefreshAclRetentionGuardrailConfig(
            max_delete_terminal_jobs=0,
            max_delete_audit_rows=0,
            max_delete_acl_rows=0,
            allow_cap_breach=False,
        )
        runs.append(
            execute_refresh_acl_retention_automation(
                dry_run=False,
                retention_config=retention,
                guardrail_config=strict_caps,
                lock_key="pr26:lock-cap",
                redis_client=fake_redis,
                db_factory=SessionLocal,
            ).to_dict()
        )

        # 4) Non-terminal risk abort (synthetic monkeypatch path).
        original_run = retention_service_module.run_refresh_acl_retention

        def _fake_run(db_session, *, config, dry_run):
            if dry_run:
                return RefreshAclRetentionSummary(
                    dry_run=True,
                    config={"audit_retention_days": 30},
                    before={"total_jobs": 2},
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
                    after={"total_jobs": 2},
                    safety={"non_terminal_job_delete_candidates": 1, "guards_passed": False},
                    generated_at=config.now.isoformat(),
                )
            raise RuntimeError("execute path should not run in non-terminal risk abort scenario")

        retention_service_module.run_refresh_acl_retention = _fake_run
        try:
            runs.append(
                execute_refresh_acl_retention_automation(
                    dry_run=False,
                    retention_config=retention,
                    guardrail_config=guardrails,
                    lock_key="pr26:lock-risk",
                    redis_client=fake_redis,
                    db_factory=SessionLocal,
                ).to_dict()
            )
        finally:
            retention_service_module.run_refresh_acl_retention = original_run

        # 5) Execute success.
        runs.append(
            execute_refresh_acl_retention_automation(
                dry_run=False,
                retention_config=retention,
                guardrail_config=guardrails,
                lock_key="pr26:lock-success",
                redis_client=fake_redis,
                db_factory=SessionLocal,
            ).to_dict()
        )

        output = {
            "generated_at": base_now.isoformat(),
            "scenario": "synthetic_automation_runs",
            "run_count": len(runs),
            "runs": runs,
        }

        out_path = Path("docs/evidence/phase-a-hardening/2026-02-11/pr26_refresh_acl_retention_automation_runs.json")
        out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

        Base.metadata.drop_all(bind=engine)
        engine.dispose()

        print(json.dumps({"output": str(out_path), "run_count": len(runs)}, indent=2))


if __name__ == "__main__":
    main()
