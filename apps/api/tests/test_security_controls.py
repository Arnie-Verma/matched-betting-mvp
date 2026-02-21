import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import close_all_sessions, sessionmaker

from api.core.auth import UserClaims, get_current_user, optional_user
from api.core.database import Base, get_db
from api.main import app
from api.models import User


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


def _build_client(tmp_path: Path):
    db_path = tmp_path / "security_controls.sqlite"
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


def test_refresh_status_enforces_owner_or_explicit_shared_access(tmp_path, monkeypatch):
    client, SessionLocal, engine = _build_client(tmp_path)
    fake_redis = _FakeRedis()
    monkeypatch.setattr("redis.from_url", lambda *_args, **_kwargs: fake_redis)

    current_sub = {"value": "owner-user"}

    def override_user():
        sub = current_sub["value"]
        return UserClaims(sub=sub, email=f"{sub}@test.local", email_verified=True)

    app.dependency_overrides[get_current_user] = override_user

    try:
        db = SessionLocal()
        owner = User(
            clerk_user_id="owner-user",
            email="owner@test.local",
            email_verified=True,
            current_plan="free",
            plan_status="active",
        )
        other = User(
            clerk_user_id="other-user",
            email="other@test.local",
            email_verified=True,
            current_plan="free",
            plan_status="active",
        )
        db.add_all([owner, other])
        db.commit()
        db.refresh(owner)
        db.refresh(other)
        db.close()

        fake_redis.set_job(
            "odds_refresh_job:job-owner-only",
            {
                "status": "running",
                "payload": {"requested_by": owner.id},
                "enqueued_at": "2026-02-21T00:00:00+00:00",
            },
        )

        current_sub["value"] = "other-user"
        response = client.get("/odds/refresh/status?job_id=job-owner-only")
        assert response.status_code == 403

        current_sub["value"] = "owner-user"
        response = client.get("/odds/refresh/status?job_id=job-owner-only")
        assert response.status_code == 200
        assert response.json()["job_id"] == "job-owner-only"

        fake_redis.set_job(
            "odds_refresh_job:job-shared",
            {
                "status": "pending",
                "payload": {"requested_by": owner.id, "shared_user_ids": [other.id]},
                "enqueued_at": "2026-02-21T00:00:00+00:00",
            },
        )

        current_sub["value"] = "other-user"
        response = client.get("/odds/refresh/status?job_id=job-shared")
        assert response.status_code == 200
        assert response.json()["job_id"] == "job-shared"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_health_scrapers_requires_authentication(tmp_path, monkeypatch):
    client, SessionLocal, engine = _build_client(tmp_path)
    monkeypatch.delenv("HEALTH_SCRAPERS_INTERNAL_TOKEN", raising=False)

    try:
        response = client.get("/health/scrapers")
        assert response.status_code in (401, 403)
    finally:
        app.dependency_overrides.clear()
        close_all_sessions()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_health_scrapers_allows_authenticated_access(tmp_path):
    client, SessionLocal, engine = _build_client(tmp_path)

    def override_optional_user():
        return UserClaims(sub="ops-user", email="ops@test.local", email_verified=True, raw_claims={})

    app.dependency_overrides[optional_user] = override_optional_user

    try:
        response = client.get("/health/scrapers")
        assert response.status_code == 200
        payload = response.json()
        assert "status" in payload
        assert "bookmakers" in payload
    finally:
        app.dependency_overrides.clear()
        close_all_sessions()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
