from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.auth import UserClaims, optional_user
from api.core.database import Base, get_db
from api.main import app
from api.models import Bookmaker
from api.services.rollout_control_service import RolloutControlService


def _build_session(tmp_path: Path):
    db_path = tmp_path / "rollout_control.sqlite"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal, engine


def _create_bookmaker(
    db,
    *,
    code: str,
    scraper_class: str,
    lifecycle_state: str = "active",
    is_active: bool = True,
):
    bookmaker = Bookmaker(
        code=code,
        name=code.title(),
        display_name=code.title(),
        website_url=f"https://{code}.example.com",
        is_active=is_active,
        lifecycle_state=lifecycle_state,
        country="AU",
        default_source_type="scrape",
        rate_limit_seconds=5,
        scraping_config={"scraper_class": scraper_class},
    )
    db.add(bookmaker)
    db.commit()
    db.refresh(bookmaker)
    return bookmaker


def _decision_map(decisions):
    return {row["bookmaker_code"]: row for row in decisions}


def test_rollout_selection_cohort_and_kill_switch_controls(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="ladbrokes", scraper_class="entain")
        _create_bookmaker(db, code="neds", scraper_class="entain")
        _create_bookmaker(db, code="mintbet", scraper_class="punterstech")

        RolloutControlService.upsert_platform_policy(
            db,
            platform_code="entain",
            rollout_mode="canary",
            sport_cohort=["soccer"],
            competition_cohort=["epl"],
            bookmaker_cohort=["ladbrokes"],
            updated_by="ops-user",
        )

        rows = db.query(Bookmaker).all()
        selected = RolloutControlService.resolve_runnable_bookmakers(
            db,
            bookmaker_rows=rows,
            requested_sport="soccer",
            requested_competition="epl",
        )
        decisions = _decision_map(selected.decisions)
        assert {cfg["code"] for cfg in selected.runnable_configs} == {"ladbrokes", "mintbet"}
        assert decisions["neds"]["runnable"] is False
        assert "platform_bookmaker_cohort_excluded" in decisions["neds"]["reasons"]

        RolloutControlService.upsert_bookmaker_policy(
            db,
            bookmaker_code="mintbet",
            kill_switch_enabled=True,
            updated_by="ops-user",
        )
        selected_with_kill = RolloutControlService.resolve_runnable_bookmakers(
            db,
            bookmaker_rows=rows,
            requested_sport="soccer",
            requested_competition="epl",
        )
        decisions_kill = _decision_map(selected_with_kill.decisions)
        assert decisions_kill["mintbet"]["runnable"] is False
        assert "bookmaker_kill_switch_enabled" in decisions_kill["mintbet"]["reasons"]

        RolloutControlService.upsert_bookmaker_policy(
            db,
            bookmaker_code="mintbet",
            kill_switch_enabled=False,
            updated_by="ops-user",
        )
        selected_after_bookmaker_rollback = RolloutControlService.resolve_runnable_bookmakers(
            db,
            bookmaker_rows=rows,
            requested_sport="soccer",
            requested_competition="epl",
        )
        assert "mintbet" in {cfg["code"] for cfg in selected_after_bookmaker_rollback.runnable_configs}

        RolloutControlService.upsert_platform_policy(
            db,
            platform_code="entain",
            kill_switch_enabled=True,
            updated_by="ops-user",
        )
        selected_platform_kill = RolloutControlService.resolve_runnable_bookmakers(
            db,
            bookmaker_rows=rows,
            requested_sport="soccer",
            requested_competition="epl",
        )
        decisions_platform_kill = _decision_map(selected_platform_kill.decisions)
        assert decisions_platform_kill["ladbrokes"]["runnable"] is False
        assert decisions_platform_kill["neds"]["runnable"] is False
        assert "platform_kill_switch_enabled" in decisions_platform_kill["ladbrokes"]["reasons"]

        RolloutControlService.upsert_platform_policy(
            db,
            platform_code="entain",
            rollout_mode="disabled",
            kill_switch_enabled=False,
            updated_by="ops-user",
        )
        selected_disabled = RolloutControlService.resolve_runnable_bookmakers(
            db,
            bookmaker_rows=rows,
            requested_sport="soccer",
            requested_competition="epl",
        )
        decisions_disabled = _decision_map(selected_disabled.decisions)
        assert decisions_disabled["ladbrokes"]["runnable"] is False
        assert "platform_rollout_disabled" in decisions_disabled["ladbrokes"]["reasons"]

        RolloutControlService.upsert_platform_policy(
            db,
            platform_code="entain",
            rollout_mode="full",
            kill_switch_enabled=False,
            sport_cohort=[],
            competition_cohort=[],
            bookmaker_cohort=[],
            updated_by="ops-user",
        )
        selected_rollback = RolloutControlService.resolve_runnable_bookmakers(
            db,
            bookmaker_rows=rows,
            requested_sport="soccer",
            requested_competition="epl",
        )
        runnable_codes = {cfg["code"] for cfg in selected_rollback.runnable_configs}
        assert "ladbrokes" in runnable_codes
        assert "neds" in runnable_codes
        assert "mintbet" in runnable_codes
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_rollout_endpoints_enforce_access_and_support_internal_token(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    monkeypatch.setenv("BOOKMAKER_ROLLOUT_INTERNAL_TOKEN", "rollout-secret")

    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="ladbrokes", scraper_class="entain")
    finally:
        db.close()

    def override_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db

    try:
        app.dependency_overrides[optional_user] = lambda: None
        client = TestClient(app)
        unauthorized = client.get("/admin/rollout/status")
        assert unauthorized.status_code == 401

        app.dependency_overrides[optional_user] = lambda: UserClaims(
            sub="user-1",
            email="user@test.local",
            raw_claims={"roles": ["member"]},
        )
        forbidden = client.get("/admin/rollout/status")
        assert forbidden.status_code == 403

        app.dependency_overrides[optional_user] = lambda: UserClaims(
            sub="ops-user",
            email="ops@test.local",
            raw_claims={"roles": ["ops"]},
        )

        set_policy = client.put(
            "/admin/rollout/platforms/entain/policy",
            json={
                "rollout_mode": "canary",
                "sport_cohort": ["soccer"],
                "competition_cohort": ["epl"],
                "bookmaker_cohort": ["ladbrokes"],
            },
        )
        assert set_policy.status_code == 200
        assert set_policy.json()["rollout_mode"] == "canary"

        set_kill = client.put(
            "/admin/rollout/bookmakers/ladbrokes/kill-switch",
            json={"enabled": True},
        )
        assert set_kill.status_code == 200
        assert set_kill.json()["kill_switch_enabled"] is True

        status_response = client.get("/admin/rollout/status?sport=soccer&competition=epl")
        assert status_response.status_code == 200
        payload = status_response.json()
        assert "bookmakers" in payload
        assert payload["excluded_count"] >= 1

        app.dependency_overrides[optional_user] = lambda: None
        internal = client.get(
            "/admin/rollout/platforms/entain/policy",
            headers={"x-internal-rollout-token": "rollout-secret"},
        )
        assert internal.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(optional_user, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
