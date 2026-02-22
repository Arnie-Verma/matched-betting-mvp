import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.auth import UserClaims, optional_user
from api.core.database import Base, get_db
from api.main import app
from api.models import Bookmaker, BookmakerActivationEvidence, BookmakerLifecycleTransition
from api.services.activation_evidence_registry_service import ActivationEvidenceRegistryService
from api.services.bookmaker_lifecycle_service import (
    BookmakerLifecycleService,
    LifecycleTransitionError,
    REQUIRED_CANARY_GATE_THRESHOLDS,
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


def _write_artifact(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _validation_payload(*, age_seconds: int = 0, in_scope_fail_count: int = 0) -> dict:
    generated_at = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return {
        "generated_at": generated_at.isoformat(),
        "in_scope_fail_count": in_scope_fail_count,
    }


def _canary_payload(
    *,
    age_seconds: int = 0,
    gate_pass: bool = True,
    thresholds: dict | None = None,
    failed_criteria: list[dict] | None = None,
) -> dict:
    ended_at = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    return {
        "ended_at": ended_at.isoformat(),
        "gate": {
            "pass": gate_pass,
            "thresholds": thresholds or dict(REQUIRED_CANARY_GATE_THRESHOLDS),
            "criteria": failed_criteria or [],
            "failure_reasons": [] if gate_pass else ["synthetic gate fail"],
        },
    }


def _register_validation_evidence(
    db,
    tmp_path: Path,
    *,
    bookmaker_code: str,
    age_seconds: int = 0,
    in_scope_fail_count: int = 0,
):
    payload = _validation_payload(
        age_seconds=age_seconds,
        in_scope_fail_count=in_scope_fail_count,
    )
    artifact_path = _write_artifact(
        tmp_path,
        f"validation_{bookmaker_code}_{age_seconds}_{in_scope_fail_count}.json",
        payload,
    )
    return ActivationEvidenceRegistryService.register_from_artifact_path(
        db,
        evidence_type="validation",
        bookmaker_code=bookmaker_code,
        artifact_path=str(artifact_path),
        created_by="ops-user",
        created_by_email="ops@test.local",
    )


def _register_canary_evidence(
    db,
    tmp_path: Path,
    *,
    bookmaker_code: str,
    age_seconds: int = 0,
    gate_pass: bool = True,
    thresholds: dict | None = None,
    failed_criteria: list[dict] | None = None,
):
    payload = _canary_payload(
        age_seconds=age_seconds,
        gate_pass=gate_pass,
        thresholds=thresholds,
        failed_criteria=failed_criteria,
    )
    artifact_path = _write_artifact(
        tmp_path,
        f"canary_{bookmaker_code}_{age_seconds}_{int(gate_pass)}.json",
        payload,
    )
    return ActivationEvidenceRegistryService.register_from_artifact_path(
        db,
        evidence_type="canary",
        bookmaker_code=bookmaker_code,
        artifact_path=str(artifact_path),
        created_by="ops-user",
        created_by_email="ops@test.local",
    )


def _progress_to_validation_passed(db, bookmaker_code: str):
    for target in (
        "discovery_complete",
        "adapter_ready",
        "config_ready",
        "validation_passed",
    ):
        BookmakerLifecycleService.transition_bookmaker_state(
            db,
            bookmaker_code=bookmaker_code,
            to_state=target,
            reason=f"progress to {target}",
            transitioned_by="ops-user",
            transition_source="test",
        )


def _promote_to_canary_with_registry_evidence(db, tmp_path: Path, bookmaker_code: str):
    validation = _register_validation_evidence(
        db,
        tmp_path,
        bookmaker_code=bookmaker_code,
        in_scope_fail_count=0,
    )
    return BookmakerLifecycleService.transition_bookmaker_state(
        db,
        bookmaker_code=bookmaker_code,
        to_state="canary_active",
        reason="promote to canary",
        transitioned_by="ops-user",
        transition_source="test",
        transition_metadata={"validation_evidence_id": validation.evidence_id},
    )


def test_lifecycle_happy_path_transitions_and_is_active_toggle(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        bookmaker = _create_bookmaker(db, code="ladbrokes", is_active=False)
        assert bookmaker.lifecycle_state == "backlog"
        assert bookmaker.is_active is False

        for target in ("discovery_complete", "adapter_ready", "config_ready", "validation_passed"):
            BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="ladbrokes",
                to_state=target,
                reason=f"move to {target}",
                transitioned_by="ops-user",
                transitioned_by_email="ops@test.local",
                transition_source="test",
                transition_metadata={"target": target},
            )

        _promote_to_canary_with_registry_evidence(db, tmp_path, "ladbrokes")
        canary = _register_canary_evidence(db, tmp_path, bookmaker_code="ladbrokes", gate_pass=True)
        result = BookmakerLifecycleService.transition_bookmaker_state(
            db,
            bookmaker_code="ladbrokes",
            to_state="active",
            reason="move to active",
            transitioned_by="ops-user",
            transitioned_by_email="ops@test.local",
            transition_source="test",
            transition_metadata={"canary_evidence_id": canary.evidence_id},
        )
        assert result.to_state == "active"
        assert result.is_active is True
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_validation_to_canary_denied_when_canonical_record_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="mintbet", is_active=False)
        _progress_to_validation_passed(db, "mintbet")

        try:
            BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="mintbet",
                to_state="canary_active",
                reason="promote to canary",
                transitioned_by="ops-user",
                transition_source="test",
                transition_metadata={},
            )
            assert False, "expected missing canonical validation evidence denial"
        except LifecycleTransitionError as exc:
            assert exc.reason_code == "validation_evidence_record_missing"
            assert exc.failed_criteria
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_validation_to_canary_denied_on_bookmaker_mismatch(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="starsports", is_active=False)
        _create_bookmaker(db, code="betreal", is_active=False)
        _progress_to_validation_passed(db, "starsports")

        other = _register_validation_evidence(
            db,
            tmp_path,
            bookmaker_code="betreal",
            in_scope_fail_count=0,
        )
        try:
            BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="starsports",
                to_state="canary_active",
                reason="promote to canary",
                transitioned_by="ops-user",
                transition_source="test",
                transition_metadata={"validation_evidence_id": other.evidence_id},
            )
            assert False, "expected validation evidence bookmaker mismatch denial"
        except LifecycleTransitionError as exc:
            assert exc.reason_code == "validation_evidence_bookmaker_mismatch"
            assert exc.failed_criteria
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_validation_to_canary_denied_when_validation_evidence_stale(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    monkeypatch.setenv("BOOKMAKER_VALIDATION_EVIDENCE_MAX_AGE_SECONDS", "300")
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="topbet", is_active=False)
        _progress_to_validation_passed(db, "topbet")
        record = _register_validation_evidence(
            db,
            tmp_path,
            bookmaker_code="topbet",
            age_seconds=301,
            in_scope_fail_count=0,
        )
        try:
            BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="topbet",
                to_state="canary_active",
                reason="promote to canary",
                transitioned_by="ops-user",
                transition_source="test",
                transition_metadata={"validation_evidence_id": record.evidence_id},
            )
            assert False, "expected stale canonical validation evidence denial"
        except LifecycleTransitionError as exc:
            assert exc.reason_code == "validation_evidence_stale"
            assert exc.failed_criteria
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_validation_to_canary_denied_when_in_scope_fail_detected(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="betvista", is_active=False)
        _progress_to_validation_passed(db, "betvista")
        record = _register_validation_evidence(
            db,
            tmp_path,
            bookmaker_code="betvista",
            in_scope_fail_count=2,
        )
        try:
            BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="betvista",
                to_state="canary_active",
                reason="promote to canary",
                transitioned_by="ops-user",
                transition_source="test",
                transition_metadata={"validation_evidence_id": record.evidence_id},
            )
            assert False, "expected in-scope fail denial"
        except LifecycleTransitionError as exc:
            assert exc.reason_code == "validation_in_scope_fail_detected"
            assert exc.failed_criteria
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_validation_to_canary_allowed_with_fresh_matching_record(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="cashcage", is_active=False)
        _progress_to_validation_passed(db, "cashcage")
        record = _register_validation_evidence(
            db,
            tmp_path,
            bookmaker_code="cashcage",
            in_scope_fail_count=0,
        )
        result = BookmakerLifecycleService.transition_bookmaker_state(
            db,
            bookmaker_code="cashcage",
            to_state="canary_active",
            reason="promote to canary",
            transitioned_by="ops-user",
            transition_source="test",
            transition_metadata={"validation_evidence_id": record.evidence_id},
        )
        assert result.to_state == "canary_active"
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_canary_to_active_denied_when_canonical_record_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="blondebet", is_active=False)
        _progress_to_validation_passed(db, "blondebet")
        _promote_to_canary_with_registry_evidence(db, tmp_path, "blondebet")
        try:
            BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="blondebet",
                to_state="active",
                reason="promote to active",
                transitioned_by="ops-user",
                transition_source="test",
                transition_metadata={},
            )
            assert False, "expected missing canonical canary evidence denial"
        except LifecycleTransitionError as exc:
            assert exc.reason_code == "canary_evidence_record_missing"
            assert exc.failed_criteria
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_canary_to_active_denied_on_bookmaker_mismatch(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="betfocus", is_active=False)
        _create_bookmaker(db, code="truebet", is_active=False)
        _progress_to_validation_passed(db, "betfocus")
        _promote_to_canary_with_registry_evidence(db, tmp_path, "betfocus")
        mismatched = _register_canary_evidence(db, tmp_path, bookmaker_code="truebet", gate_pass=True)
        try:
            BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="betfocus",
                to_state="active",
                reason="promote to active",
                transitioned_by="ops-user",
                transition_source="test",
                transition_metadata={"canary_evidence_id": mismatched.evidence_id},
            )
            assert False, "expected canary evidence bookmaker mismatch denial"
        except LifecycleTransitionError as exc:
            assert exc.reason_code == "canary_evidence_bookmaker_mismatch"
            assert exc.failed_criteria
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_canary_to_active_denied_when_canary_evidence_stale(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    monkeypatch.setenv("BOOKMAKER_CANARY_EVIDENCE_MAX_AGE_SECONDS", "300")
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="ripperbet", is_active=False)
        _progress_to_validation_passed(db, "ripperbet")
        _promote_to_canary_with_registry_evidence(db, tmp_path, "ripperbet")
        stale = _register_canary_evidence(
            db,
            tmp_path,
            bookmaker_code="ripperbet",
            age_seconds=301,
            gate_pass=True,
        )
        try:
            BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="ripperbet",
                to_state="active",
                reason="promote to active",
                transitioned_by="ops-user",
                transition_source="test",
                transition_metadata={"canary_evidence_id": stale.evidence_id},
            )
            assert False, "expected stale canary evidence denial"
        except LifecycleTransitionError as exc:
            assert exc.reason_code == "canary_evidence_stale"
            assert exc.failed_criteria
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_canary_to_active_denied_when_gate_fails(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="teambet", is_active=False)
        _progress_to_validation_passed(db, "teambet")
        _promote_to_canary_with_registry_evidence(db, tmp_path, "teambet")
        failed = _register_canary_evidence(
            db,
            tmp_path,
            bookmaker_code="teambet",
            gate_pass=False,
            failed_criteria=[
                {
                    "name": "max_scrape_p95_seconds",
                    "threshold": 360.0,
                    "observed": 388.5,
                    "pass": False,
                }
            ],
        )
        try:
            BookmakerLifecycleService.transition_bookmaker_state(
                db,
                bookmaker_code="teambet",
                to_state="active",
                reason="promote to active",
                transitioned_by="ops-user",
                transition_source="test",
                transition_metadata={"canary_evidence_id": failed.evidence_id},
            )
            assert False, "expected failed canary gate denial"
        except LifecycleTransitionError as exc:
            assert exc.reason_code == "canary_gate_failed"
            assert exc.failed_criteria
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_canary_to_active_allowed_with_fresh_matching_record(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="wizbet", is_active=False)
        _progress_to_validation_passed(db, "wizbet")
        _promote_to_canary_with_registry_evidence(db, tmp_path, "wizbet")
        record = _register_canary_evidence(db, tmp_path, bookmaker_code="wizbet", gate_pass=True)
        result = BookmakerLifecycleService.transition_bookmaker_state(
            db,
            bookmaker_code="wizbet",
            to_state="active",
            reason="promote to active",
            transitioned_by="ops-user",
            transition_source="test",
            transition_metadata={"canary_evidence_id": record.evidence_id},
        )
        assert result.to_state == "active"
        assert result.is_active is True
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_evidence_registration_persists_artifact_hash_and_path(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_FREEZE_UNIBET", raising=False)
    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    try:
        _create_bookmaker(db, code="mintbet", is_active=False)
        payload = _validation_payload(in_scope_fail_count=0)
        path = _write_artifact(tmp_path, "validation_mintbet_hash_test.json", payload)
        result = ActivationEvidenceRegistryService.register_from_artifact_path(
            db,
            evidence_type="validation",
            bookmaker_code="mintbet",
            artifact_path=str(path),
            created_by="ops-user",
            created_by_email="ops@test.local",
            metadata={"source_test": "hash_check"},
        )

        row = (
            db.query(BookmakerActivationEvidence)
            .filter(BookmakerActivationEvidence.id == result.evidence_id)
            .first()
        )
        assert row is not None
        assert row.artifact_sha256
        assert len(row.artifact_sha256) == 64
        assert row.artifact_path.endswith("validation_mintbet_hash_test.json")
        assert row.created_by == "ops-user"
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
            transition_metadata={"ticket": "PR-L3"},
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
        assert entry.transition_metadata.get("ticket") == "PR-L3"
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
                transition_metadata={},
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


def test_lifecycle_and_registry_endpoints_enforce_role_and_return_structured_denials(tmp_path, monkeypatch):
    monkeypatch.delenv("BOOKMAKER_LIFECYCLE_INTERNAL_TOKEN", raising=False)
    monkeypatch.delenv("BOOKMAKER_LIFECYCLE_ALLOWED_ROLES", raising=False)
    monkeypatch.setenv("BOOKMAKER_FREEZE_UNIBET", "true")

    SessionLocal, engine = _build_session(tmp_path)
    db = SessionLocal()
    _create_bookmaker(db, code="ladbrokes", is_active=False)
    db.close()

    validation_path = _write_artifact(
        tmp_path,
        "validation_ladbrokes_endpoint.json",
        _validation_payload(in_scope_fail_count=0),
    )

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
        denied_register = client.post(
            "/admin/bookmakers/lifecycle-evidence/register",
            json={
                "evidence_type": "validation",
                "bookmaker_code": "ladbrokes",
                "artifact_path": str(validation_path),
            },
        )
        assert denied_register.status_code == 403

        current_claims["value"] = UserClaims(
            sub="admin-user",
            email="admin@test.local",
            email_verified=True,
            raw_claims={"roles": ["admin"]},
        )

        register = client.post(
            "/admin/bookmakers/lifecycle-evidence/register",
            json={
                "evidence_type": "validation",
                "bookmaker_code": "ladbrokes",
                "artifact_path": str(validation_path),
                "metadata": {"request_id": "reg-1"},
            },
        )
        assert register.status_code == 200
        evidence_id = register.json()["evidence_id"]
        assert evidence_id > 0

        # Progress to validation_passed via admin endpoint.
        for target in ("discovery_complete", "adapter_ready", "config_ready", "validation_passed"):
            step = client.post(
                "/admin/bookmakers/ladbrokes/lifecycle",
                json={"to_state": target, "reason": f"step {target}"},
            )
            assert step.status_code == 200

        denied_canary = client.post(
            "/admin/bookmakers/ladbrokes/lifecycle",
            json={
                "to_state": "canary_active",
                "reason": "attempt without canonical evidence id",
                "metadata": {},
            },
        )
        assert denied_canary.status_code == 400
        denied_payload = denied_canary.json().get("detail", {})
        assert denied_payload.get("reason_code") == "validation_evidence_record_missing"
        assert isinstance(denied_payload.get("failed_criteria"), list)
        assert denied_payload.get("failed_criteria")

        allowed_canary = client.post(
            "/admin/bookmakers/ladbrokes/lifecycle",
            json={
                "to_state": "canary_active",
                "reason": "promote with canonical evidence",
                "metadata": {"validation_evidence_id": evidence_id},
            },
        )
        assert allowed_canary.status_code == 200
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
