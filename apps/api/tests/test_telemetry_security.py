from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import close_all_sessions, sessionmaker

from api.core.auth import UserClaims, optional_user
from api.core.database import Base, get_db
from api.main import app


def _build_client(tmp_path: Path):
    db_path = tmp_path / "telemetry_security.sqlite"
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
    return client, engine


def _fake_report():
    return {
        "schema_version": "observability.v1",
        "window_hours": 24,
        "events_analyzed": 2,
        "summary": {
            "schema_version": "observability.v1",
            "security": {
                "allowed_count": 1,
                "denied_count": 1,
                "denied_counts_by_action": {"refresh_status_acl_denied": 1},
                "acl_denied_rate": 0.5,
            },
            "sample_events": [
                {
                    "category": "security",
                    "payload": {
                        "user_id": 42,
                        "owner_user_id": 12,
                        "sub": "clerk_sensitive",
                    },
                }
            ],
        },
        "sample_metric_records": [{"category": "security"}],
        "threshold_evaluation": {"overall_pass": True},
    }


def test_health_telemetry_unauthenticated_denied(tmp_path):
    client, engine = _build_client(tmp_path)
    try:
        response = client.get("/health/telemetry")
        assert response.status_code in (401, 403)
    finally:
        app.dependency_overrides.clear()
        close_all_sessions()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_health_telemetry_denies_non_ops_and_matches_health_endpoints(tmp_path):
    client, engine = _build_client(tmp_path)

    def override_optional_user():
        return UserClaims(
            sub="member-user",
            email="member@test.local",
            email_verified=True,
            raw_claims={"roles": ["member"]},
        )

    app.dependency_overrides[optional_user] = override_optional_user

    try:
        telemetry = client.get("/health/telemetry")
        scrapers = client.get("/health/scrapers")
        detailed = client.get("/health/detailed")
        assert telemetry.status_code == 403
        assert scrapers.status_code == 403
        assert detailed.status_code == 403
    finally:
        app.dependency_overrides.clear()
        close_all_sessions()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_health_telemetry_allows_ops_role_and_sanitizes_response(tmp_path, monkeypatch):
    client, engine = _build_client(tmp_path)

    def override_optional_user():
        return UserClaims(
            sub="ops-user",
            email="ops@test.local",
            email_verified=True,
            raw_claims={"roles": ["ops"]},
        )

    app.dependency_overrides[optional_user] = override_optional_user
    monkeypatch.setattr("api.routers.health.build_observability_report", lambda **_kwargs: _fake_report())

    try:
        response = client.get("/health/telemetry")
        assert response.status_code == 200
        payload = response.json()
        assert "sample_metric_records" not in payload
        assert "sample_events" not in payload.get("summary", {})
    finally:
        app.dependency_overrides.clear()
        close_all_sessions()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_health_telemetry_allows_internal_token(tmp_path, monkeypatch):
    client, engine = _build_client(tmp_path)
    monkeypatch.setenv("HEALTH_SCRAPERS_INTERNAL_TOKEN", "s2-secret")
    monkeypatch.setattr("api.routers.health.build_observability_report", lambda **_kwargs: _fake_report())

    try:
        response = client.get(
            "/health/telemetry",
            headers={"X-Internal-Health-Token": "s2-secret"},
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
        close_all_sessions()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_health_telemetry_rejects_out_of_range_query_params(tmp_path):
    client, engine = _build_client(tmp_path)

    def override_optional_user():
        return UserClaims(
            sub="ops-user",
            email="ops@test.local",
            email_verified=True,
            raw_claims={"roles": ["ops"]},
        )

    app.dependency_overrides[optional_user] = override_optional_user

    try:
        response_hours = client.get("/health/telemetry?hours=25")
        response_limit = client.get("/health/telemetry?limit=2001")
        response_min = client.get("/health/telemetry?hours=0")
        assert response_hours.status_code == 422
        assert response_limit.status_code == 422
        assert response_min.status_code == 422
    finally:
        app.dependency_overrides.clear()
        close_all_sessions()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

