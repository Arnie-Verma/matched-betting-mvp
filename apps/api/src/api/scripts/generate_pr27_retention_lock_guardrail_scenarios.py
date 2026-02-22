"""Generate PR27 lock/guardrail remediation scenarios."""
from __future__ import annotations

import json
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.database import Base
from api.models import RefreshJob, RefreshJobAclEntry, RefreshJobAuditEvent, User
from api.services.refresh_acl_retention_automation_service import (
    _release_lock,
    execute_refresh_acl_retention_automation,
)
from api.services.refresh_acl_retention_service import (
    RefreshAclRetentionConfig,
    RefreshAclRetentionGuardrailConfig,
)


class _FakeRedis:
    def __init__(self):
        self._store: dict[str, str] = {}
        self._lock = threading.Lock()

    def set(self, key, value, nx=False, ex=None):
        with self._lock:
            if nx and key in self._store:
                return None
            self._store[key] = value
            return True

    def get(self, key):
        with self._lock:
            return self._store.get(key)

    def delete(self, key):
        with self._lock:
            existed = key in self._store
            self._store.pop(key, None)
            return 1 if existed else 0

    def eval(self, script, numkeys, lock_key, lock_token):
        with self._lock:
            current = self._store.get(lock_key)
            if current == lock_token:
                self._store.pop(lock_key, None)
                return 1
            return 0


def _seed_users(db):
    owner = User(
        clerk_user_id="owner-pr27",
        email="owner-pr27@test.local",
        email_verified=True,
        current_plan="free",
        plan_status="active",
    )
    shared = User(
        clerk_user_id="shared-pr27",
        email="shared-pr27@test.local",
        email_verified=True,
        current_plan="free",
        plan_status="active",
    )
    db.add_all([owner, shared])
    db.commit()
    db.refresh(owner)
    db.refresh(shared)
    return owner, shared


def _add_terminal_job(db, *, owner_id: int, shared_id: int, now: datetime):
    created = now - timedelta(days=45)
    job = RefreshJob(
        job_id="pr27-terminal-old",
        owner_user_id=owner_id,
        status="success",
        source="pr27",
        requested_at=created,
        enqueued_at=created,
        started_at=created,
        completed_at=created,
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
            job_id="pr27-terminal-old",
            action_type="seed",
            decision="allow",
            reason_code="seed",
            actor_user_id=owner_id,
            actor_sub="seed",
            created_at=created,
        )
    )
    db.commit()


def main() -> None:
    base_now = datetime(2026, 2, 22, tzinfo=timezone.utc)
    retention = RefreshAclRetentionConfig(
        audit_retention_days=30,
        terminal_job_retention_days=14,
        terminal_statuses=("success", "failed"),
        now=base_now,
    )
    strict_guardrails = RefreshAclRetentionGuardrailConfig(
        max_delete_terminal_jobs=0,
        max_delete_audit_rows=0,
        max_delete_acl_rows=0,
        allow_cap_breach=True,
    )
    fake_redis = _FakeRedis()
    scenarios: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "pr27_retention_lock_guardrail.sqlite"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)

        db = session_factory()
        owner, shared = _seed_users(db)
        _add_terminal_job(db, owner_id=owner.id, shared_id=shared.id, now=base_now)
        db.close()

        # Scenario 1: stale owner release cannot delete newer lock owner.
        race_key = "pr27:lock-race"
        stale_token = "stale-owner"
        new_token = "new-owner"
        fake_redis.set(race_key, stale_token, nx=True, ex=60)
        fake_redis.set(race_key, new_token, nx=False, ex=60)
        _release_lock(fake_redis, lock_key=race_key, lock_token=stale_token)
        scenarios.append(
            {
                "name": "lock_release_race_safety",
                "expected": "new owner lock remains",
                "observed_lock_value": fake_redis.get(race_key),
                "pass": fake_redis.get(race_key) == new_token,
            }
        )

        # Scenario 2: lock contention aborts second run.
        fake_redis.set("pr27:contention", "held-by-other", nx=False, ex=60)
        contended = execute_refresh_acl_retention_automation(
            dry_run=True,
            retention_config=retention,
            guardrail_config=strict_guardrails,
            allow_cap_breach_override=False,
            lock_key="pr27:contention",
            redis_client=fake_redis,
            db_factory=session_factory,
        ).to_dict()
        scenarios.append(
            {
                "name": "lock_contention_aborts",
                "expected_reason_code": "lock_not_acquired",
                "observed_reason_code": contended.get("reason_code"),
                "pass": contended.get("reason_code") == "lock_not_acquired",
            }
        )

        # Scenario 3: cap breach denied without explicit override.
        denied = execute_refresh_acl_retention_automation(
            dry_run=False,
            retention_config=retention,
            guardrail_config=strict_guardrails,
            allow_cap_breach_override=False,
            lock_key="pr27:cap-denied",
            redis_client=fake_redis,
            db_factory=session_factory,
        ).to_dict()
        scenarios.append(
            {
                "name": "cap_breach_denied_without_override",
                "expected_reason_code": "delete_cap_exceeded",
                "observed_reason_code": denied.get("reason_code"),
                "observed_allow_cap_breach": (denied.get("summary") or {}).get("guardrails", {}).get("allow_cap_breach"),
                "pass": denied.get("reason_code") == "delete_cap_exceeded",
            }
        )

        # Scenario 4: explicit per-run override allows execute.
        allowed = execute_refresh_acl_retention_automation(
            dry_run=False,
            retention_config=retention,
            guardrail_config=strict_guardrails,
            allow_cap_breach_override=True,
            lock_key="pr27:cap-allowed",
            redis_client=fake_redis,
            db_factory=session_factory,
        ).to_dict()
        scenarios.append(
            {
                "name": "cap_breach_allowed_with_explicit_override",
                "expected_reason_code": "success",
                "observed_reason_code": allowed.get("reason_code"),
                "observed_allow_cap_breach": (allowed.get("summary") or {}).get("guardrails", {}).get("allow_cap_breach"),
                "terminal_jobs_deleted": (allowed.get("summary") or {}).get("deleted", {}).get("terminal_jobs"),
                "pass": allowed.get("reason_code") == "success",
            }
        )

        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    output = {
        "generated_at": base_now.isoformat(),
        "slice": "PR-A2c",
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }
    output_path = Path("docs/evidence/phase-a-hardening/2026-02-11/pr27_retention_lock_guardrail_scenarios.json")
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "scenario_count": len(scenarios)}, indent=2))


if __name__ == "__main__":
    main()

