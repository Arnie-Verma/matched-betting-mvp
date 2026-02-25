from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api.core.auth import UserClaims, get_current_user
from api.core.database import Base, get_db
from api.main import app
from api.models import Bookmaker, Competition, Event, Market, OddsSnapshot, Selection, Sport, User
from api.routers.odds_matcher import BetType, _read_model_request_supported
from api.services.matcher_read_model_service import (
    MatcherReadModelBuildConfig,
    build_matcher_read_model,
    get_read_model_serving_snapshot,
)


def _build_client(tmp_path: Path):
    db_path = tmp_path / "matcher_read_model_scalability.sqlite"
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
            sub="matcher-scalability-user",
            email="matcher-scalability@test.local",
            email_verified=True,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user
    client = TestClient(app)
    return client, session_factory, engine


def _seed_data(session_factory, *, event_count: int = 120):
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
                clerk_user_id="matcher-scalability-user",
                email="matcher-scalability@test.local",
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

            for selection, price in ((home, Decimal("2.04")), (away, Decimal("2.29"))):
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
                        available_amount=Decimal("1250.00"),
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
        event_limit=500,
        event_batch_size=100,
        row_batch_size=200,
    )
    db = session_factory()
    try:
        return build_matcher_read_model(db, config=cfg)
    finally:
        db.close()


def test_read_model_serving_snapshot_uses_limit_offset_pushdown(tmp_path):
    client, session_factory, engine = _build_client(tmp_path)
    _seed_data(session_factory, event_count=80)
    _build_read_model(session_factory, version="scalable_snapshot_v1")

    sql_rows: list[str] = []

    def _before_cursor_execute(_conn, _cursor, statement, _params, _context, _executemany):
        sql_rows.append(str(statement))

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    db = session_factory()
    try:
        snapshot = get_read_model_serving_snapshot(
            db,
            read_model_version="scalable_snapshot_v1",
            max_age_seconds=600,
            limit=30,
            offset=30,
            bookmaker_codes=["ladbrokes", "neds"],
            min_rating=Decimal("0"),
            now=datetime.now(timezone.utc),
        )
    finally:
        db.close()
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        client.close()

    assert snapshot["ok"] is True
    assert snapshot["query_round_trip_signal"] <= 3
    assert snapshot["materialized_row_count"] <= 30
    assert len(snapshot["payloads"]) <= 30
    assert snapshot["materialized_row_count"] == len(snapshot["payloads"])
    assert snapshot["total_count"] >= len(snapshot["payloads"])

    row_selects = [
        stmt.lower()
        for stmt in sql_rows
        if stmt.strip().lower().startswith("select")
        and "from matcher_read_model_rows" in stmt.lower()
    ]
    assert row_selects
    page_fetches = [stmt for stmt in row_selects if "count(" not in stmt]
    assert page_fetches
    assert all(" limit " in stmt for stmt in page_fetches)
    assert all(" offset " in stmt for stmt in page_fetches)


def test_read_model_request_shape_guardrails_reject_non_scalable_filters():
    supported, reason = _read_model_request_supported(
        stake=Decimal("100"),
        bet_type=BetType.NORMAL,
        sport_filter=None,
        competition_filter=None,
        competition_code_filter=["epl"],
        search=None,
    )
    assert supported is False
    assert reason == "read_model_unsupported_competition_codes_filter"

    supported, reason = _read_model_request_supported(
        stake=Decimal("100"),
        bet_type=BetType.NORMAL,
        sport_filter=None,
        competition_filter=None,
        competition_code_filter=None,
        search="arsenal",
    )
    assert supported is False
    assert reason == "read_model_unsupported_search_filter"


def test_matcher_read_model_serves_page_1_and_2_with_sql_pagination(tmp_path, monkeypatch):
    client, session_factory, engine = _build_client(tmp_path)
    _seed_data(session_factory, event_count=90)
    _build_read_model(session_factory, version="scalable_serving_v1")

    sql_rows: list[str] = []
    emitted = []

    def _before_cursor_execute(_conn, _cursor, statement, _params, _context, _executemany):
        sql_rows.append(str(statement))

    monkeypatch.setattr(
        "api.routers.odds_matcher.emit_observability_event",
        lambda **kwargs: emitted.append(kwargs) or "1-1",
    )
    monkeypatch.setenv("MATCHER_READ_MODEL_SERVING_ENABLED", "1")
    monkeypatch.setenv("MATCHER_READ_MODEL_VERSION", "scalable_serving_v1")
    monkeypatch.setenv("MATCHER_READ_MODEL_MAX_AGE_SECONDS", "600")
    event.listen(engine, "before_cursor_execute", _before_cursor_execute)

    try:
        page_one = client.get("/odds/matcher?limit=30&offset=0")
        page_two = client.get("/odds/matcher?limit=30&offset=30")
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    assert page_one.status_code == 200
    assert page_two.status_code == 200
    assert page_one.headers.get("x-matcher-serving-source") == "read_model"
    assert page_two.headers.get("x-matcher-serving-source") == "read_model"
    assert page_one.headers.get("x-matcher-fallback-reason") is None
    assert page_two.headers.get("x-matcher-fallback-reason") is None

    body_one = page_one.json()
    body_two = page_two.json()
    assert body_one["offset"] == 0
    assert body_two["offset"] == 30
    assert body_one["limit"] == 30
    assert body_two["limit"] == 30
    assert body_one["total"] == body_two["total"]
    assert len(body_one["items"]) <= 30
    assert len(body_two["items"]) <= 30
    assert len(body_one["items"]) > 0
    assert len(body_two["items"]) > 0
    assert body_one["items"][0] != body_two["items"][0]

    matcher_events = [evt for evt in emitted if evt.get("metric_name") == "matcher_request"]
    assert len(matcher_events) >= 2
    for payload in [matcher_events[-1]["payload"], matcher_events[-2]["payload"]]:
        assert payload["serving_source"] == "read_model"
        assert payload["fallback_reason_code"] is None
        assert payload["read_model_query_mode"] == "sql_limit_offset"
        assert payload["read_model_materialized_rows"] <= 30
        assert payload["read_model_total_rows"] >= payload["read_model_materialized_rows"]
        assert payload["read_model_query_round_trip_signal"] <= 3

    row_selects = [
        stmt.lower()
        for stmt in sql_rows
        if stmt.strip().lower().startswith("select")
        and "from matcher_read_model_rows" in stmt.lower()
    ]
    assert row_selects
    page_fetches = [stmt for stmt in row_selects if "count(" not in stmt]
    assert page_fetches
    assert all(" limit " in stmt for stmt in page_fetches)
    assert all(" offset " in stmt for stmt in page_fetches)


def test_matcher_read_model_unsupported_shapes_runtime_fallback_reason_codes(tmp_path, monkeypatch):
    client, session_factory, engine = _build_client(tmp_path)
    _seed_data(session_factory, event_count=40)
    _build_read_model(session_factory, version="scalable_unsupported_v1")

    emitted = []
    monkeypatch.setattr(
        "api.routers.odds_matcher.emit_observability_event",
        lambda **kwargs: emitted.append(kwargs) or "1-1",
    )
    monkeypatch.setenv("MATCHER_READ_MODEL_SERVING_ENABLED", "1")
    monkeypatch.setenv("MATCHER_READ_MODEL_VERSION", "scalable_unsupported_v1")
    monkeypatch.setenv("MATCHER_READ_MODEL_MAX_AGE_SECONDS", "600")

    try:
        by_competition_code = client.get("/odds/matcher?limit=20&offset=0&competition_codes=epl")
        by_search = client.get("/odds/matcher?limit=20&offset=0&search=team")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    assert by_competition_code.status_code == 200
    assert by_competition_code.headers.get("x-matcher-serving-source") == "runtime_fallback"
    assert by_competition_code.headers.get("x-matcher-fallback-reason") == "read_model_unsupported_competition_codes_filter"

    assert by_search.status_code == 200
    assert by_search.headers.get("x-matcher-serving-source") == "runtime_fallback"
    assert by_search.headers.get("x-matcher-fallback-reason") == "read_model_unsupported_search_filter"

    matcher_events = [evt for evt in emitted if evt.get("metric_name") == "matcher_request"]
    assert len(matcher_events) >= 2
    assert matcher_events[-2]["payload"]["fallback_reason_code"] == "read_model_unsupported_competition_codes_filter"
    assert matcher_events[-1]["payload"]["fallback_reason_code"] == "read_model_unsupported_search_filter"
    assert matcher_events[-2]["payload"]["read_model_query_mode"] == "unsupported_shape_runtime_fallback"
    assert matcher_events[-1]["payload"]["read_model_query_mode"] == "unsupported_shape_runtime_fallback"
