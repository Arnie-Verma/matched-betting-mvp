from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.auth import UserClaims, optional_user
from api.core.database import Base, get_db
from api.main import app
from api.models import Bookmaker, BookmakerLifecycleTransition
from api.services.bookmaker_lifecycle_service import (
    BookmakerLifecycleService,
    LifecycleTransitionError,
)


def _build_session(tmp_path: Path):
    db_path = tmp_path / "bookmaker_lifecycle.sqlite"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal, engine


def _create_bookmaker(db, *, code: str, is_active: bool = False):
    bookmaker = Bookmaker(
        code=code,
        name=code.title(),
        display_name=code.title(),
        website_url=f"https://{code}.example.com",
        is_active=is_active,
        country="AU",
        default_source_type="scrape",
        rate_limit_seconds=5,
        scraping_config={"scraper_class": "entain"},
    )
    db.add(bookmaker)
    db.commit()
    db.refresh(bookmaker)
    return bookmaker


def test_lifecycle_happy_path_transitions_and_is_active_toggle(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        bookmaker = _create_bookmaker(db, code="ladbrokes", is_active=False)
        assert bookmaker.lifecycle_state == "backlog"
        assert bookmaker.is_active is False

        target_sequence = [
            "discovery_complete",
            "adapter_ready",
            "config_ready",
            "validation_passed",
            "canary_active",
            "active",
        ]
        for target in target_sequence:
            result = BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="ladbrokes",
                to_state=target,
                reason=f"move to {target}",
                transitioned_by="ops-user",
                transitioned_by_email="ops@test.local",
                transition_source="test",
                transition_metadata={"target": target},
            )
            assert result.to_state == target

        refreshed = db.query(Bookmaker).filter(Bookmaker.code == "ladbrokes").first()
        assert refreshed.lifecycle_state == "active"
        assert refreshed.is_active is True
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_invalid_lifecycle_transition_is_blocked_with_reason(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="betfair", is_active=False)

        try:
            BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="betfair",
                to_state="active",
                reason="unsafe jump",
                transitioned_by="ops-user",
            )
            assert False, "expected LifecycleTransitionError"
        except LifecycleTransitionError as exc:
            assert exc.reason_code == "invalid_transition"
            assert exc.from_state == "backlog"
            assert exc.to_state == "active"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_transition_audit_metadata_is_persisted(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        bookmaker = _create_bookmaker(db, code="neds", is_active=False)
        BookmakerLifecycleService.transition_bookmaker_state(
            db,
            bookmaker_code=bookmaker.code,
            to_state="discovery_complete",
            reason="discovery signed off",
            transitioned_by="admin-user",
            transitioned_by_email="admin@test.local",
            transition_source="api",
            transition_metadata={"ticket": "PR-L1"},
        )

        history = db.query(BookmakerLifecycleTransition).filter(
            BookmakerLifecycleTransition.bookmaker_id == bookmaker.id
        ).all()
        assert len(history) == 1
        entry = history[0]
        assert entry.from_state == "backlog"
        assert entry.to_state == "discovery_complete"
        assert entry.transition_reason == "discovery signed off"
        assert entry.transitioned_by == "admin-user"
        assert entry.transitioned_by_email == "admin@test.local"
        assert entry.transition_source == "api"
        assert entry.transition_metadata.get("ticket") == "PR-L1"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_unibet_freeze_blocks_live_lifecycle_transition(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOKMAKER_FREEZE_UNIBET", "true")
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="unibet", is_active=False)
        for target in (
            "discovery_complete",
            "adapter_ready",
            "config_ready",
            "validation_passed",
        ):
            BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="unibet",
                to_state=target,
                reason=f"progress {target}",
                transitioned_by="ops-user",
                transition_source="test",
            )

        try:
            BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="unibet",
                to_state="canary_active",
                reason="attempt canary",
                transitioned_by="ops-user",
                transition_source="test",
            )
            assert False, "expected freeze guard to block live state transition"
        except LifecycleTransitionError as exc:
            assert exc.reason_code == "freeze_guard_blocked"

        refreshed = db.query(Bookmaker).filter(Bookmaker.code == "unibet").first()
        assert refreshed.lifecycle_state == "validation_passed"
        assert refreshed.is_active is False
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_lifecycle_endpoint_enforces_role_and_persists_transition(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_LIFECYCLE_INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("BOOKMAKER_LIFECYCLE_ALLOWED_ROLES", raising=False)
    monkeypatch.setenv("BOOKMAKER_FREEZE_UNIBET", "true")

    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    _create_bookmaker(db, code="ladbrokes", is_active=False)
    db.close()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    current_claims = {
        "value": UserClaims(
            sub="member-user",
            email="member@test.local",
            email_verified=True,
            raw_claims={"roles": ["member"]},
        )
    }

    def override_optional_user():
        return current_claims["value"]

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[optional_user] = override_optional_user
    client = TestClient(app)

    try:
        denied = client.post(
            "/admin/bookmakers/ladbrokes/lifecycle",
            json={"to_state": "discovery_complete", "reason": "role denied path"},
        )
        assert denied.status_code == 403

        current_claims["value"] = UserClaims(
            sub="admin-user",
            email="admin@test.local",
            email_verified=True,
            raw_claims={"roles": ["admin"]},
        )
        allowed = client.post(
            "/admin/bookmakers/ladbrokes/lifecycle",
            json={
                "to_state": "discovery_complete",
                "reason": "admin transition",
                "metadata": {"request_id": "abc123"},
            },
        )
        assert allowed.status_code == 200
        payload = allowed.json()
        assert payload["bookmaker_code"] == "ladbrokes"
        assert payload["from_state"] == "backlog"
        assert payload["to_state"] == "discovery_complete"
        assert payload["is_active"] is False
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
