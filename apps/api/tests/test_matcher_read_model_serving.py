from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.auth import UserClaims, get_current_user
from api.core.database import Base, get_db
from api.main import app
from api.models import Bookmaker, Competition, Event, Market, MatcherReadModelBuild, OddsSnapshot, Selection, Sport, User
from api.routers.odds_matcher import OddsMatchResponse
from api.services.matcher_read_model_service import MatcherReadModelBuildConfig, build_matcher_read_model
from api.services.matching_engine import BetType


def _build_client(tmp_path: Path):
    db_path = tmp_path / "matcher_read_model_serving.sqlite"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_current_user():
        return UserClaims(
            sub="matcher-serving-user",
            email="matcher-serving@test.local",
            email_verified=True,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    client = TestClient(app)
    return client, session_factory, engine


def _seed_data(session_factory, *, event_count: int = 10):
    db = session_factory()
    try:
        sport = Sport(code="soccer", name="Soccer", display_name="Soccer", is_active=True, sort_order=1)
        db.add(sport)
        db.flush()

        competition = Competition(
            sport_id=sport.id,
            name="English Premier League",
            short_name="EPL",
            country="AU",
            is_active=True,
        )
        db.add(competition)
        db.flush()

        db.add(
            User(
                clerk_user_id="matcher-serving-user",
                email="matcher-serving@test.local",
                email_verified=True,
                current_plan="free",
                plan_status="active",
            )
        )

        bookmakers = [
            Bookmaker(
                code="ladbrokes",
                name="Ladbrokes",
                display_name="Ladbrokes",
                website_url="https://www.ladbrokes.com.au",
                is_active=True,
                default_source_type="scrape",
                country="AU",
            ),
            Bookmaker(
                code="neds",
                name="Neds",
                display_name="Neds",
                website_url="https://www.neds.com.au",
                is_active=True,
                default_source_type="scrape",
                country="AU",
            ),
            Bookmaker(
                code="betfair",
                name="Betfair",
                display_name="Betfair",
                website_url="https://www.betfair.com.au",
                is_active=True,
                default_source_type="scrape",
                country="AU",
            ),
        ]
        db.add_all(bookmakers)
        db.flush()

        now = datetime.now(timezone.utc)
        for idx in range(event_count):
            event_row = Event(
                competition_id=competition.id,
                name=f"Team {idx} vs Opponent {idx}",
                start_time=now + timedelta(hours=24 + idx),
                status="scheduled",
            )
            db.add(event_row)
            db.flush()

            market = Market(
                event_id=event_row.id,
                market_type="match_winner",
                name="Match Result",
                is_active=True,
            )
            db.add(market)
            db.flush()

            home = Selection(market_id=market.id, name=f"Team {idx}", selection_key="home")
            away = Selection(market_id=market.id, name=f"Opponent {idx}", selection_key="away")
            db.add_all([home, away])
            db.flush()

            for selection, price in ((home, Decimal("2.05")), (away, Decimal("2.35"))):
                db.add(
                    OddsSnapshot(
                        selection_id=selection.id,
                        bookmaker_id=bookmakers[0].id,
                        decimal_odds=price,
                        source_type="scrape",
                        timestamp=now,
                        is_current=True,
                    )
                )
                db.add(
                    OddsSnapshot(
                        selection_id=selection.id,
                        bookmaker_id=bookmakers[1].id,
                        decimal_odds=price + Decimal("0.05"),
                        source_type="scrape",
                        timestamp=now,
                        is_current=True,
                    )
                )
                db.add(
                    OddsSnapshot(
                        selection_id=selection.id,
                        bookmaker_id=bookmakers[2].id,
                        decimal_odds=price - Decimal("0.08"),
                        source_type="scrape",
                        timestamp=now,
                        is_current=True,
                        available_amount=Decimal("1100.00"),
                    )
                )
        db.commit()
    finally:
        db.close()


def _build_read_model(session_factory, *, version: str):
    now = datetime.now(timezone.utc)
    cfg = MatcherReadModelBuildConfig(
        read_model_version=version,
        source_window_start=now,
        source_window_end=now + timedelta(days=14),
        stake=Decimal("100"),
        bet_type=BetType.NORMAL,
        bookmaker_codes=["ladbrokes", "neds", "betfair"],
        event_limit=100,
        event_batch_size=20,
        row_batch_size=50,
    )
    db = session_factory()
    try:
        return build_matcher_read_model(db, config=cfg)
    finally:
        db.close()


def test_flag_off_uses_runtime_serving_path(tmp_path, monkeypatch):
    client, session_factory, engine = _build_client(tmp_path)
    _seed_data(session_factory)
    _build_read_model(session_factory, version="serving_runtime_default_v1")

    emitted = []
    monkeypatch.setattr(
        "api.routers.odds_matcher.emit_observability_event",
        lambda **kwargs: emitted.append(kwargs) or "1-1",
    )
    monkeypatch.setenv("MATCHER_READ_MODEL_SERVING_ENABLED", "0")
    monkeypatch.setenv("MATCHER_READ_MODEL_VERSION", "serving_runtime_default_v1")

    try:
        response = client.get("/odds/matcher?limit=20&offset=0")
        assert response.status_code == 200
        assert response.headers.get("x-matcher-serving-source") == "runtime"
        body = response.json()
        assert body["items"]
        assert set(body["items"][0].keys()) == set(OddsMatchResponse.model_fields.keys())

        matcher_events = [event for event in emitted if event.get("metric_name") == "matcher_request"]
        assert matcher_events
        assert matcher_events[-1]["payload"]["serving_source"] == "runtime"
        assert matcher_events[-1]["payload"]["fallback_reason_code"] is None
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_flag_on_with_fresh_read_model_serves_from_read_model(tmp_path, monkeypatch):
    client, session_factory, engine = _build_client(tmp_path)
    _seed_data(session_factory)
    _build_read_model(session_factory, version="serving_read_model_v1")

    emitted = []
    monkeypatch.setattr(
        "api.routers.odds_matcher.emit_observability_event",
        lambda **kwargs: emitted.append(kwargs) or "1-1",
    )
    monkeypatch.setenv("MATCHER_READ_MODEL_SERVING_ENABLED", "1")
    monkeypatch.setenv("MATCHER_READ_MODEL_VERSION", "serving_read_model_v1")
    monkeypatch.setenv("MATCHER_READ_MODEL_MAX_AGE_SECONDS", "600")

    try:
        response = client.get("/odds/matcher?limit=20&offset=0")
        assert response.status_code == 200
        assert response.headers.get("x-matcher-serving-source") == "read_model"
        body = response.json()
        assert body["items"]
        assert set(body["items"][0].keys()) == set(OddsMatchResponse.model_fields.keys())

        matcher_events = [event for event in emitted if event.get("metric_name") == "matcher_request"]
        assert matcher_events
        assert matcher_events[-1]["payload"]["serving_source"] == "read_model"
        assert matcher_events[-1]["payload"]["fallback_reason_code"] is None
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_flag_on_missing_or_stale_read_model_falls_back_to_runtime(tmp_path, monkeypatch):
    client, session_factory, engine = _build_client(tmp_path)
    _seed_data(session_factory)
    _build_read_model(session_factory, version="serving_stale_v1")

    emitted = []
    monkeypatch.setattr(
        "api.routers.odds_matcher.emit_observability_event",
        lambda **kwargs: emitted.append(kwargs) or "1-1",
    )
    monkeypatch.setenv("MATCHER_READ_MODEL_SERVING_ENABLED", "1")
    monkeypatch.setenv("MATCHER_READ_MODEL_VERSION", "serving_missing_v1")
    monkeypatch.setenv("MATCHER_READ_MODEL_MAX_AGE_SECONDS", "600")

    try:
        missing = client.get("/odds/matcher?limit=20&offset=0")
        assert missing.status_code == 200
        assert missing.headers.get("x-matcher-serving-source") == "runtime_fallback"
        assert missing.headers.get("x-matcher-fallback-reason") == "read_model_missing_build"
        missing_body = missing.json()
        assert missing_body["items"]
        assert set(missing_body["items"][0].keys()) == set(OddsMatchResponse.model_fields.keys())

        db = session_factory()
        try:
            build = (
                db.query(MatcherReadModelBuild)
                .filter(MatcherReadModelBuild.read_model_version == "serving_stale_v1")
                .one()
            )
            build.built_at = datetime.now(timezone.utc) - timedelta(hours=2)
            db.commit()
        finally:
            db.close()

        monkeypatch.setenv("MATCHER_READ_MODEL_VERSION", "serving_stale_v1")
        monkeypatch.setenv("MATCHER_READ_MODEL_MAX_AGE_SECONDS", "1")
        stale = client.get("/odds/matcher?limit=20&offset=0")
        assert stale.status_code == 200
        assert stale.headers.get("x-matcher-serving-source") == "runtime_fallback"
        assert stale.headers.get("x-matcher-fallback-reason") == "read_model_stale"

        matcher_events = [event for event in emitted if event.get("metric_name") == "matcher_request"]
        assert matcher_events
        assert matcher_events[-1]["payload"]["serving_source"] == "runtime_fallback"
        assert matcher_events[-1]["payload"]["fallback_reason_code"] == "read_model_stale"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_flag_on_unsupported_stake_uses_runtime_fallback(tmp_path, monkeypatch):
    client, session_factory, engine = _build_client(tmp_path)
    _seed_data(session_factory)
    _build_read_model(session_factory, version="serving_unsupported_stake_v1")

    emitted = []
    monkeypatch.setattr(
        "api.routers.odds_matcher.emit_observability_event",
        lambda **kwargs: emitted.append(kwargs) or "1-1",
    )
    monkeypatch.setenv("MATCHER_READ_MODEL_SERVING_ENABLED", "1")
    monkeypatch.setenv("MATCHER_READ_MODEL_VERSION", "serving_unsupported_stake_v1")
    monkeypatch.setenv("MATCHER_READ_MODEL_MAX_AGE_SECONDS", "600")

    try:
        response = client.get("/odds/matcher?limit=20&offset=0&stake=150")
        assert response.status_code == 200
        assert response.headers.get("x-matcher-serving-source") == "runtime_fallback"
        assert response.headers.get("x-matcher-fallback-reason") == "read_model_unsupported_stake"
        body = response.json()
        assert body["items"]
        assert set(body["items"][0].keys()) == set(OddsMatchResponse.model_fields.keys())

        matcher_events = [event for event in emitted if event.get("metric_name") == "matcher_request"]
        assert matcher_events
        assert matcher_events[-1]["payload"]["serving_source"] == "runtime_fallback"
        assert matcher_events[-1]["payload"]["fallback_reason_code"] == "read_model_unsupported_stake"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_read_model_response_parity_matches_runtime_contract(tmp_path, monkeypatch):
    client, session_factory, engine = _build_client(tmp_path)
    _seed_data(session_factory, event_count=14)
    _build_read_model(session_factory, version="serving_parity_v1")

    try:
        monkeypatch.setenv("MATCHER_READ_MODEL_SERVING_ENABLED", "0")
        monkeypatch.setenv("MATCHER_READ_MODEL_VERSION", "serving_parity_v1")
        runtime_response = client.get("/odds/matcher?limit=100&offset=0")
        assert runtime_response.status_code == 200
        assert runtime_response.headers.get("x-matcher-serving-source") == "runtime"
        runtime_payload = runtime_response.json()

        monkeypatch.setenv("MATCHER_READ_MODEL_SERVING_ENABLED", "1")
        monkeypatch.setenv("MATCHER_READ_MODEL_VERSION", "serving_parity_v1")
        monkeypatch.setenv("MATCHER_READ_MODEL_MAX_AGE_SECONDS", "600")
        read_model_response = client.get("/odds/matcher?limit=100&offset=0")
        assert read_model_response.status_code == 200
        assert read_model_response.headers.get("x-matcher-serving-source") == "read_model"
        read_model_payload = read_model_response.json()

        def _canonical_rows(payload):
            rows = []
            for row in payload["items"]:
                rows.append(
                    (
                        int(row["event_id"]),
                        int(row["market_id"]),
                        int(row["selection_id"]),
                        str(row["back_bookmaker_code"]),
                        str(row["bet_type"]),
                        round(float(row["pnl_percentage"]), 6),
                        round(float(row["rating"]), 6),
                    )
                )
            return sorted(rows)

        assert runtime_payload["total"] == read_model_payload["total"]
        assert runtime_payload["offset"] == read_model_payload["offset"]
        assert runtime_payload["limit"] == read_model_payload["limit"]
        assert runtime_payload["has_more"] == read_model_payload["has_more"]
        assert _canonical_rows(runtime_payload) == _canonical_rows(read_model_payload)
        assert set(read_model_payload["items"][0].keys()) == set(OddsMatchResponse.model_fields.keys())
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
