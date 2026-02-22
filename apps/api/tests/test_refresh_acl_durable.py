import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import close_all_sessions, sessionmaker

from api.core.auth import UserClaims, get_current_user
from api.core.database import Base, get_db
from api.main import app
from api.models import RefreshJob, RefreshJobAuditEvent, User
from api.services.refresh_job_acl_service import RefreshJobAclService


class _FakeRedis:
    def __init__(self):
        self._store = {}

    def get(self, key):
        return self._store.get(key)

    def setex(self, key, _ttl_seconds, value):
        if isinstance(value, str):
            self._store[key] = value.encode()
        else:
            self._store[key] = value

    def set_job(self, key, body):
        self._store[key] = json.dumps(body).encode()

    def delete(self, key):
        self._store.pop(key, None)


def _build_client(tmp_path: Path):
    db_path = tmp_path / "refresh_acl_durable.sqlite"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return client, SessionLocal, engine


def _seed_users(session_local):
    db = session_local()
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
    db.close()
    return owner, shared, outsider


def _set_current_user(current_sub):
    def override_user():
        sub = current_sub["value"]
        return UserClaims(sub=sub, email=f"{sub}@test.local", email_verified=True)

    app.dependency_overrides[get_current_user] = override_user


def test_durable_acl_enforces_owner_and_shared_and_writes_access_audit(tmp_path, monkeypatch):
    client, SessionLocal, engine = _build_client(tmp_path)
    fake_redis = _FakeRedis()
    monkeypatch.setattr("redis.from_url", lambda *_args, **_kwargs: fake_redis)

    owner, shared, outsider = _seed_users(SessionLocal)
    db = SessionLocal()
    try:
        job = RefreshJobAclService.create_job(
            db,
            job_id="durable-job-1",
            owner_user_id=owner.id,
            payload={"requested_by": owner.id, "requested_at": "2026-02-22T00:00:00+00:00"},
            actor_user_id=owner.id,
            actor_sub="owner-user",
        )
        RefreshJobAclService.share_job_with_user(
            db,
            job=job,
            user_id=shared.id,
            actor_user_id=owner.id,
            actor_sub="owner-user",
            reason_code="test-share",
        )
    finally:
        db.close()

    current_sub = {"value": "owner-user"}
    _set_current_user(current_sub)

    try:
        owner_resp = client.get("/odds/refresh/status?job_id=durable-job-1")
        assert owner_resp.status_code == 200

        current_sub["value"] = "shared-user"
        shared_resp = client.get("/odds/refresh/status?job_id=durable-job-1")
        assert shared_resp.status_code == 200

        current_sub["value"] = "outsider-user"
        denied_resp = client.get("/odds/refresh/status?job_id=durable-job-1")
        assert denied_resp.status_code == 403

        db = SessionLocal()
        try:
            events = (
                db.query(RefreshJobAuditEvent)
                .filter(RefreshJobAuditEvent.job_id == "durable-job-1")
                .all()
            )
            action_types = {event.action_type for event in events}
            assert "status_access_allow" in action_types
            assert "status_access_deny" in action_types
        finally:
            db.close()
    finally:
        app.dependency_overrides.clear()
        close_all_sessions()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_durable_acl_precedence_blocks_redis_payload_bypass(tmp_path, monkeypatch):
    client, SessionLocal, engine = _build_client(tmp_path)
    fake_redis = _FakeRedis()
    monkeypatch.setattr("redis.from_url", lambda *_args, **_kwargs: fake_redis)

    owner, shared, _outsider = _seed_users(SessionLocal)

    db = SessionLocal()
    try:
        RefreshJobAclService.create_job(
            db,
            job_id="durable-job-2",
            owner_user_id=owner.id,
            payload={"requested_by": owner.id},
            actor_user_id=owner.id,
            actor_sub="owner-user",
        )
    finally:
        db.close()

    # Legacy payload claims shared user access, but durable ACL is source of truth.
    fake_redis.set_job(
        "odds_refresh_job:durable-job-2",
        {
            "status": "running",
            "payload": {"requested_by": owner.id, "shared_user_ids": [shared.id]},
        },
    )

    current_sub = {"value": "shared-user"}
    _set_current_user(current_sub)

    try:
        response = client.get("/odds/refresh/status?job_id=durable-job-2")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
        close_all_sessions()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_legacy_pre_migration_fallback_allows_shared_and_denies_non_shared(tmp_path, monkeypatch):
    client, SessionLocal, engine = _build_client(tmp_path)
    fake_redis = _FakeRedis()
    monkeypatch.setattr("redis.from_url", lambda *_args, **_kwargs: fake_redis)

    owner, shared, outsider = _seed_users(SessionLocal)

    fake_redis.set_job(
        "odds_refresh_job:legacy-job-1",
        {
            "status": "running",
            "payload": {"requested_by": owner.id, "shared_user_ids": [shared.id]},
            "enqueued_at": "2026-02-22T00:00:00+00:00",
        },
    )

    current_sub = {"value": "shared-user"}
    _set_current_user(current_sub)

    try:
        allowed = client.get("/odds/refresh/status?job_id=legacy-job-1")
        assert allowed.status_code == 200

        current_sub["value"] = "outsider-user"
        denied = client.get("/odds/refresh/status?job_id=legacy-job-1")
        assert denied.status_code == 403

        db = SessionLocal()
        try:
            durable = RefreshJobAclService.get_job_by_job_id(db, job_id="legacy-job-1")
            assert durable is not None
            assert durable.owner_user_id == owner.id
        finally:
            db.close()
    finally:
        app.dependency_overrides.clear()
        close_all_sessions()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_durable_acl_survives_redis_expiry_for_backfilled_jobs(tmp_path, monkeypatch):
    client, SessionLocal, engine = _build_client(tmp_path)
    fake_redis = _FakeRedis()
    monkeypatch.setattr("redis.from_url", lambda *_args, **_kwargs: fake_redis)

    owner, shared, _outsider = _seed_users(SessionLocal)

    fake_redis.set_job(
        "odds_refresh_job:legacy-job-expire",
        {
            "status": "success",
            "payload": {"requested_by": owner.id, "shared_user_ids": [shared.id]},
            "enqueued_at": "2026-02-22T00:00:00+00:00",
            "completed_at": "2026-02-22T00:02:00+00:00",
            "message": "done",
        },
    )

    current_sub = {"value": "owner-user"}
    _set_current_user(current_sub)

    try:
        first = client.get("/odds/refresh/status?job_id=legacy-job-expire")
        assert first.status_code == 200

        fake_redis.delete("odds_refresh_job:legacy-job-expire")

        current_sub["value"] = "shared-user"
        after_expiry = client.get("/odds/refresh/status?job_id=legacy-job-expire")
        assert after_expiry.status_code == 200
        assert after_expiry.json()["status"] == "success"
    finally:
        app.dependency_overrides.clear()
        close_all_sessions()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_service_records_acl_share_and_unshare_audit_events(tmp_path):
    _client, SessionLocal, engine = _build_client(tmp_path)
    owner, shared, _outsider = _seed_users(SessionLocal)

    db = SessionLocal()
    try:
        job = RefreshJobAclService.create_job(
            db,
            job_id="audit-job-1",
            owner_user_id=owner.id,
            payload={"requested_by": owner.id},
            actor_user_id=owner.id,
            actor_sub="owner-user",
        )
        changed = RefreshJobAclService.share_job_with_user(
            db,
            job=job,
            user_id=shared.id,
            actor_user_id=owner.id,
            actor_sub="owner-user",
            reason_code="manual-share",
        )
        assert changed is True

        refreshed = RefreshJobAclService.get_job_by_job_id(db, job_id="audit-job-1")
        assert refreshed is not None
        removed = RefreshJobAclService.unshare_job_with_user(
            db,
            job=refreshed,
            user_id=shared.id,
            actor_user_id=owner.id,
            actor_sub="owner-user",
            reason_code="manual-unshare",
        )
        assert removed is True

        events = (
            db.query(RefreshJobAuditEvent)
            .filter(RefreshJobAuditEvent.job_id == "audit-job-1")
            .all()
        )
        action_types = [event.action_type for event in events]
        assert "acl_share_update" in action_types
        assert "acl_unshare_update" in action_types
    finally:
        db.close()
        app.dependency_overrides.clear()
        close_all_sessions()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
