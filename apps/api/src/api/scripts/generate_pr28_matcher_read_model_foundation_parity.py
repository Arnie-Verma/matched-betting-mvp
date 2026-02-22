"""Generate PR28 matcher read-model foundation parity evidence."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.database import Base
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
from api.services.matcher_read_model_service import (
    MatcherReadModelBuildConfig,
    build_matcher_read_model,
    run_shadow_parity_check,
)
from api.services.matching_engine import BetType


OUTPUT_PATH = "docs/evidence/phase-a-hardening/2026-02-11/pr28_matcher_read_model_foundation_parity.json"


def _seed_data(session_factory, *, event_count: int = 24) -> None:
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
                clerk_user_id="pr28-user",
                email="pr28@test.local",
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
                        decimal_odds=price + Decimal("0.06"),
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
                        available_amount=Decimal("1200.00"),
                    )
                )
        db.commit()
    finally:
        db.close()


def main(output_path: str = OUTPUT_PATH) -> None:
    with tempfile.TemporaryDirectory(prefix="pr28_matcher_rm_") as tmp_dir:
        db_path = Path(tmp_dir) / "matcher_read_model.sqlite"
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        _seed_data(session_factory, event_count=24)

        db = session_factory()
        try:
            now = datetime.now(timezone.utc)
            config = MatcherReadModelBuildConfig(
                read_model_version="pr28_read_model_v1",
                source_window_start=now,
                source_window_end=now + timedelta(days=14),
                stake=Decimal("100"),
                bet_type=BetType.NORMAL,
                bookmaker_codes=["ladbrokes", "neds", "betfair"],
                event_limit=24,
                event_batch_size=6,
                row_batch_size=25,
            )

            first_build = build_matcher_read_model(db, config=config)
            second_build = build_matcher_read_model(db, config=config)
            parity = run_shadow_parity_check(db, config=config)

            payload = {
                "slice": "PR-M1a",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "first_build": first_build,
                "second_build": second_build,
                "idempotency": {
                    "row_count_equal": int(first_build["row_count"]) == int(second_build["row_count"]),
                    "deleted_stale_rows_on_second_build": int(second_build["deleted_stale_rows"]),
                },
                "parity": parity,
            }
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()

    output = Path(output_path)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "parity_pass": parity["parity_pass"]}, indent=2))


if __name__ == "__main__":
    main()

