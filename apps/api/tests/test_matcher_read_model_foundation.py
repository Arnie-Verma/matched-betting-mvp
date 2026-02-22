from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import ceil
from pathlib import Path

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from api.core.database import Base
from api.models import (
    Bookmaker,
    Competition,
    Event,
    Market,
    MatcherReadModelBuild,
    MatcherReadModelRow,
    OddsSnapshot,
    Selection,
    Sport,
    User,
)
from api.routers.odds_matcher import OddsMatchResponse
from api.services.matcher_read_model_service import (
    MatcherReadModelBuildConfig,
    build_matcher_read_model,
    run_shadow_parity_check,
)
from api.services.matching_engine import BetType


def _build_session(tmp_path: Path):
    db_path = tmp_path / "matcher_read_model_foundation.sqlite"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return session_factory, engine


def _seed_data(session_factory, *, event_count: int = 12):
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
                clerk_user_id="matcher-read-model-user",
                email="matcher-read-model@test.local",
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

            for selection, price in ((home, Decimal("2.10")), (away, Decimal("2.30"))):
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
                        decimal_odds=price - Decimal("0.07"),
                        source_type="scrape",
                        timestamp=now,
                        is_current=True,
                        available_amount=Decimal("1000.00"),
                    )
                )
        db.commit()
    finally:
        db.close()


def _build_config(*, version: str, event_limit: int, event_batch_size: int, row_batch_size: int):
    now = datetime.now(timezone.utc)
    return MatcherReadModelBuildConfig(
        read_model_version=version,
        source_window_start=now,
        source_window_end=now + timedelta(days=14),
        stake=Decimal("100"),
        bet_type=BetType.NORMAL,
        bookmaker_codes=["ladbrokes", "neds", "betfair"],
        event_limit=event_limit,
        event_batch_size=event_batch_size,
        row_batch_size=row_batch_size,
    )


def test_builder_is_idempotent_and_persists_freshness_metadata(tmp_path):
    session_factory, engine = _build_session(tmp_path)
    _seed_data(session_factory, event_count=10)
    config = _build_config(
        version="test_rm_idempotent_v1",
        event_limit=10,
        event_batch_size=3,
        row_batch_size=20,
    )

    db = session_factory()
    try:
        first = build_matcher_read_model(db, config=config)
        second = build_matcher_read_model(db, config=config)

        assert first["row_count"] > 0
        assert second["row_count"] == first["row_count"]
        assert second["upserted_rows"] == first["row_count"]

        build_row = (
            db.query(MatcherReadModelBuild)
            .filter(MatcherReadModelBuild.read_model_version == config.read_model_version)
            .one()
        )
        assert build_row.built_at is not None
        assert build_row.source_window_start.replace(tzinfo=timezone.utc) == config.source_window_start
        assert build_row.source_window_end.replace(tzinfo=timezone.utc) == config.source_window_end

        total_rows = (
            db.query(func.count(MatcherReadModelRow.id))
            .filter(MatcherReadModelRow.read_model_version == config.read_model_version)
            .scalar()
        )
        distinct_row_keys = (
            db.query(func.count(func.distinct(MatcherReadModelRow.row_key)))
            .filter(MatcherReadModelRow.read_model_version == config.read_model_version)
            .scalar()
        )
        assert int(total_rows or 0) == int(distinct_row_keys or 0)
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_shadow_parity_matches_runtime_contract_fields(tmp_path):
    session_factory, engine = _build_session(tmp_path)
    _seed_data(session_factory, event_count=8)
    config = _build_config(
        version="test_rm_parity_v1",
        event_limit=8,
        event_batch_size=4,
        row_batch_size=25,
    )

    db = session_factory()
    try:
        summary = build_matcher_read_model(db, config=config)
        assert summary["row_count"] > 0

        parity = run_shadow_parity_check(db, config=config)
        assert parity["parity_pass"] is True
        assert parity["field_mismatch_count"] == 0
        assert parity["only_in_runtime_count"] == 0
        assert parity["only_in_read_model_count"] == 0

        sample_row = (
            db.query(MatcherReadModelRow)
            .filter(MatcherReadModelRow.read_model_version == config.read_model_version)
            .first()
        )
        assert sample_row is not None
        assert set(sample_row.payload.keys()) == set(OddsMatchResponse.model_fields.keys())
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_builder_execution_is_bounded_and_configurable(tmp_path):
    session_factory, engine = _build_session(tmp_path)
    _seed_data(session_factory, event_count=11)
    event_limit = 11
    event_batch_size = 4
    config = _build_config(
        version="test_rm_bounded_v1",
        event_limit=event_limit,
        event_batch_size=event_batch_size,
        row_batch_size=5,
    )

    db = session_factory()
    try:
        summary = build_matcher_read_model(db, config=config)
        assert summary["processed_events"] <= event_limit
        assert summary["event_batch_count"] <= ceil(event_limit / event_batch_size)
        assert summary["event_batch_size"] == event_batch_size
        assert summary["row_batch_size"] == 5
        assert summary["query_round_trip_signal"] >= summary["event_batch_count"]
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
