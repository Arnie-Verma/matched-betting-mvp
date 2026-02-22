"""Generate PR25 synthetic before/after retention evidence."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.database import Base
from api.models import RefreshJob, RefreshJobAclEntry, RefreshJobAuditEvent, User
from api.services.refresh_acl_retention_service import RefreshAclRetentionConfig, run_refresh_acl_retention


def _seed_fixture(db, *, now: datetime) -> None:
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

    def add_job(job_id: str, status: str, age_days: int, completed_days: int | None, audit_days: list[int], *, shared_acl: bool) -> None:
        created = now - timedelta(days=age_days)
        completed = (now - timedelta(days=completed_days)) if completed_days is not None else None
        job = RefreshJob(
            job_id=job_id,
            owner_user_id=owner.id,
            status=status,
            source="artifact",
            requested_at=created,
            enqueued_at=created,
            started_at=created,
            completed_at=completed,
            payload={"requested_by": owner.id},
            created_at=created,
            updated_at=created,
        )
        db.add(job)
        db.flush()

        db.add(
            RefreshJobAclEntry(
                refresh_job_id=job.id,
                user_id=owner.id,
                access_type="read",
                is_active=True,
                grant_reason="owner",
                created_at=created,
                updated_at=created,
            )
        )
        if shared_acl:
            db.add(
                RefreshJobAclEntry(
                    refresh_job_id=job.id,
                    user_id=shared.id,
                    access_type="read",
                    is_active=True,
                    grant_reason="shared",
                    created_at=created,
                    updated_at=created,
                )
            )

        for idx, days in enumerate(audit_days):
            ts = now - timedelta(days=days)
            db.add(
                RefreshJobAuditEvent(
                    refresh_job_id=job.id,
                    job_id=job_id,
                    action_type=f"a{idx}",
                    decision="allow",
                    reason_code="seed",
                    actor_user_id=owner.id,
                    actor_sub="seed",
                    created_at=ts,
                )
            )
        db.commit()

    add_job("terminal-old", "success", 45, 45, [45], shared_acl=True)
    add_job("terminal-recent", "failed", 5, 5, [35, 2], shared_acl=False)
    add_job("running-old", "running", 60, None, [60], shared_acl=True)


def main() -> None:
    base_now = datetime(2026, 2, 22, tzinfo=timezone.utc)

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "pr25_retention.sqlite"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            _seed_fixture(db, now=base_now)

            cfg = RefreshAclRetentionConfig(
                audit_retention_days=30,
                terminal_job_retention_days=14,
                terminal_statuses=("success", "failed"),
                now=base_now,
            )

            dry = run_refresh_acl_retention(db, config=cfg, dry_run=True)
            execute = run_refresh_acl_retention(db, config=cfg, dry_run=False)

            payload = {
                "scenario": "synthetic_fixture",
                "generated_at": base_now.isoformat(),
                "config": dry.config,
                "dry_run": dry.to_dict(),
                "execute": execute.to_dict(),
            }

            out_path = Path("docs/evidence/phase-a-hardening/2026-02-11/pr25_refresh_acl_retention_before_after.json")
            out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(json.dumps({"output": str(out_path), "terminal_jobs_deleted": execute.deleted["terminal_jobs"]}, indent=2))
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()


if __name__ == "__main__":
    main()
