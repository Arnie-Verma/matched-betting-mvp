from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api.core.auth import UserClaims, get_current_user
from api.core.database import Base, get_db
from api.main import app
from api.models import (
    Bookmaker,
    Competition,
    Event,
    Market,
    OddsSnapshot,
    Selection,
    Sport,
    User,
)
from api.routers.odds_matcher import OddsMatchResponse


@pytest.fixture()
def matcher_fixture(tmp_path: Path):
    db_path = tmp_path / "matcher_hot_path.sqlite"
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

    def override_current_user():
        return UserClaims(
            sub="matcher-test-user",
            email="matcher@test.local",
            email_verified=True,
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    client = TestClient(app)
    try:
        yield {
            "engine": engine,
            "session_factory": SessionLocal,
            "client": client,
        }
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _seed_matcher_data(session_factory, event_count: int = 20) -> None:
    db = session_factory()
    try:
        sport = Sport(
            code="soccer",
            name="Soccer",
            display_name="Soccer",
            is_active=True,
            sort_order=1,
        )
        db.add(sport)
        db.flush()

        comp = Competition(
            sport_id=sport.id,
            name="English Premier League",
            short_name="EPL",
            country="AU",
            is_active=True,
        )
        db.add(comp)
        db.flush()

        user = User(
            clerk_user_id="matcher-test-user",
            email="matcher@test.local",
            email_verified=True,
            current_plan="free",
            plan_status="active",
        )
        db.add(user)

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
                competition_id=comp.id,
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

            home = Selection(
                market_id=market.id,
                name=f"Team {idx}",
                selection_key="home",
            )
            away = Selection(
                market_id=market.id,
                name=f"Opponent {idx}",
                selection_key="away",
            )
            db.add_all([home, away])
            db.flush()

            for selection, ladder in ((home, Decimal("2.10")), (away, Decimal("2.40"))):
                db.add(
                    OddsSnapshot(
                        selection_id=selection.id,
                        bookmaker_id=bookmakers[0].id,
                        decimal_odds=ladder,
                        source_type="scrape",
                        timestamp=now,
                        is_current=True,
                    )
                )
                db.add(
                    OddsSnapshot(
                        selection_id=selection.id,
                        bookmaker_id=bookmakers[1].id,
                        decimal_odds=ladder + Decimal("0.05"),
                        source_type="scrape",
                        timestamp=now,
                        is_current=True,
                    )
                )
                db.add(
                    OddsSnapshot(
                        selection_id=selection.id,
                        bookmaker_id=bookmakers[2].id,
                        decimal_odds=ladder - Decimal("0.08"),
                        source_type="scrape",
                        timestamp=now,
                        is_current=True,
                        available_amount=Decimal("1000.00"),
                    )
                )

        db.commit()
    finally:
        db.close()


def test_matcher_response_contract_unchanged_and_no_debug_prints(matcher_fixture, monkeypatch):
    _seed_matcher_data(matcher_fixture["session_factory"], event_count=8)

    def fail_print(*_args, **_kwargs):
        raise AssertionError("matcher endpoint should not call print() in request path")

    monkeypatch.setattr("builtins.print", fail_print)

    response = matcher_fixture["client"].get("/odds/matcher?limit=20&offset=0")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] > 0
    assert payload["items"]

    expected_fields = set(OddsMatchResponse.model_fields.keys())
    observed_fields = set(payload["items"][0].keys())
    assert observed_fields == expected_fields


def test_matcher_hot_path_query_count_is_bounded(matcher_fixture):
    _seed_matcher_data(matcher_fixture["session_factory"], event_count=40)
    statements: list[str] = []

    def _before_cursor_execute(_conn, _cursor, statement, _params, _context, _executemany):
        sql = statement.strip().upper()
        if sql.startswith(("SELECT", "INSERT", "UPDATE", "DELETE")):
            statements.append(statement)

    event.listen(matcher_fixture["engine"], "before_cursor_execute", _before_cursor_execute)
    try:
        response = matcher_fixture["client"].get("/odds/matcher?limit=30&offset=0")
    finally:
        event.remove(matcher_fixture["engine"], "before_cursor_execute", _before_cursor_execute)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] > 0
    # With preloading we expect fixed query behavior, not per-event/per-market growth.
    assert len(statements) <= 12
