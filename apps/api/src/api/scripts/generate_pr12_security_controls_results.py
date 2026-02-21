"""
Generate PR-S1 security controls verification results.

Writes:
  docs/evidence/phase-a-hardening/2026-02-11/pr12_security_controls_results.json
"""

from __future__ import annotations

import json
import os
import tempfile
import logging
from datetime import datetime, timezone

import redis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.auth import UserClaims, get_current_user, optional_user
from api.core.database import Base, get_db
from api.models import User


OUTPUT_PATH = "docs/evidence/phase-a-hardening/2026-02-11/pr12_security_controls_results.json"


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

    def set_job(self, key: str, body: dict):
        self._store[key] = json.dumps(body).encode()


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("api.core.monitoring").setLevel(logging.WARNING)
    from api.main import app

    fake_redis = _FakeRedis()
    original_from_url = redis.from_url

    with tempfile.TemporaryDirectory(prefix="pr12_security_") as tmpdir:
        db_path = os.path.join(tmpdir, "security.sqlite")
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

        current_sub = {"value": "owner-user"}

        def override_current_user():
            sub = current_sub["value"]
            return UserClaims(sub=sub, email=f"{sub}@test.local", email_verified=True)

        def override_optional_user_authorized():
            return UserClaims(sub="ops-user", email="ops@test.local", email_verified=True, raw_claims={})

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_current_user
        redis.from_url = lambda *_args, **_kwargs: fake_redis

        results = {}
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

            client = TestClient(app)

            current_sub["value"] = "other-user"
            cross_user = client.get("/odds/refresh/status?job_id=job-owner-only")
            results["refresh_status_cross_user"] = {
                "status_code": cross_user.status_code,
                "expected": 403,
                "pass": cross_user.status_code == 403,
            }

            current_sub["value"] = "owner-user"
            owner_resp = client.get("/odds/refresh/status?job_id=job-owner-only")
            results["refresh_status_owner"] = {
                "status_code": owner_resp.status_code,
                "expected": 200,
                "pass": owner_resp.status_code == 200,
            }

            app.dependency_overrides.pop(optional_user, None)
            os.environ.pop("HEALTH_SCRAPERS_INTERNAL_TOKEN", None)
            unauth_health = client.get("/health/scrapers")
            results["health_scrapers_unauthenticated"] = {
                "status_code": unauth_health.status_code,
                "expected_any_of": [401, 403],
                "pass": unauth_health.status_code in {401, 403},
            }

            app.dependency_overrides[optional_user] = override_optional_user_authorized
            auth_health = client.get("/health/scrapers")
            results["health_scrapers_authenticated"] = {
                "status_code": auth_health.status_code,
                "expected": 200,
                "pass": auth_health.status_code == 200,
            }

            payload = {
                "slice": "PR-S1",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "checks": results,
                "all_passed": all(item.get("pass") for item in results.values()),
            }

            with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
        finally:
            app.dependency_overrides.clear()
            redis.from_url = original_from_url
            Base.metadata.drop_all(bind=engine)
            engine.dispose()


if __name__ == "__main__":
    main()
