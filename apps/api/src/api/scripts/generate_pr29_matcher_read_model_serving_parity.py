"""Generate PR29 matcher read-model serving parity evidence."""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.core.auth import UserClaims, get_current_user
from api.core.database import Base, get_db
from api.main import app
from api.models import (
    Bookmaker,
    Competition,
    Event,
    Market,
    MatcherReadModelBuild,
    OddsSnapshot,
    Selection,
    Sport,
    User,
)
from api.routers.odds_matcher import OddsMatchResponse
from api.services.matcher_read_model_service import MatcherReadModelBuildConfig, build_matcher_read_model
from api.services.matching_engine import BetType


OUTPUT_PATH = (
    "docs/evidence/phase-a-hardening/2026-02-11/"
    "pr29_matcher_read_model_serving_parity.json"
)


def _seed_data(session_factory, *, event_count: int = 14) -> None:
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
                clerk_user_id="pr29-user",
                email="pr29@test.local",
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


def _build_read_model(session_factory, *, version: str) -> Dict[str, Any]:
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


@contextmanager
def _set_env(values: Dict[str, str]) -> Iterator[None]:
    previous: Dict[str, str | None] = {}
    for key, value in values.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _canonical_rows(payload: Dict[str, Any]) -> list[tuple[Any, ...]]:
    rows = []
    for row in payload.get("items", []):
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


def _run_request(client: TestClient, *, path: str) -> Dict[str, Any]:
    emitted: list[Dict[str, Any]] = []
    import api.routers.odds_matcher as odds_matcher_router

    original_emit = odds_matcher_router.emit_observability_event

    def _fake_emit(**kwargs):
        emitted.append(kwargs)
        return "1-1"

    odds_matcher_router.emit_observability_event = _fake_emit
    try:
        response = client.get(path)
    finally:
        odds_matcher_router.emit_observability_event = original_emit

    payload = response.json()
    matcher_event_payload: Dict[str, Any] = {}
    for event in emitted:
        if event.get("metric_name") == "matcher_request":
            matcher_event_payload = dict(event.get("payload") or {})
    return {
        "status_code": int(response.status_code),
        "serving_source_header": response.headers.get("x-matcher-serving-source"),
        "fallback_reason_header": response.headers.get("x-matcher-fallback-reason"),
        "total": int(payload.get("total", 0)),
        "schema_fields_match": (
            bool(payload.get("items"))
            and set(payload["items"][0].keys()) == set(OddsMatchResponse.model_fields.keys())
        ),
        "matcher_metric_payload": matcher_event_payload,
        "payload": payload,
    }


def main(output_path: str = OUTPUT_PATH) -> None:
    with tempfile.TemporaryDirectory(prefix="pr29_matcher_rm_serving_") as tmp_dir:
        db_path = Path(tmp_dir) / "matcher_read_model_serving.sqlite"
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        _seed_data(session_factory, event_count=14)
        build_summary = _build_read_model(session_factory, version="pr29_serving_v1")

        def _override_get_db():
            db = session_factory()
            try:
                yield db
            finally:
                db.close()

        def _override_current_user():
            return UserClaims(
                sub="pr29-user",
                email="pr29@test.local",
                email_verified=True,
            )

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user] = _override_current_user

        client = TestClient(app)
        try:
            with _set_env(
                {
                    "MATCHER_READ_MODEL_SERVING_ENABLED": "0",
                    "MATCHER_READ_MODEL_VERSION": "pr29_serving_v1",
                    "MATCHER_READ_MODEL_MAX_AGE_SECONDS": "600",
                }
            ):
                runtime_result = _run_request(client, path="/odds/matcher?limit=100&offset=0")

            with _set_env(
                {
                    "MATCHER_READ_MODEL_SERVING_ENABLED": "1",
                    "MATCHER_READ_MODEL_VERSION": "pr29_serving_v1",
                    "MATCHER_READ_MODEL_MAX_AGE_SECONDS": "600",
                }
            ):
                read_model_result = _run_request(client, path="/odds/matcher?limit=100&offset=0")

            with _set_env(
                {
                    "MATCHER_READ_MODEL_SERVING_ENABLED": "1",
                    "MATCHER_READ_MODEL_VERSION": "pr29_missing_version_v1",
                    "MATCHER_READ_MODEL_MAX_AGE_SECONDS": "600",
                }
            ):
                missing_result = _run_request(client, path="/odds/matcher?limit=100&offset=0")

            db = session_factory()
            try:
                build = (
                    db.query(MatcherReadModelBuild)
                    .filter(MatcherReadModelBuild.read_model_version == "pr29_serving_v1")
                    .one()
                )
                build.built_at = datetime.now(timezone.utc) - timedelta(hours=2)
                db.commit()
            finally:
                db.close()

            with _set_env(
                {
                    "MATCHER_READ_MODEL_SERVING_ENABLED": "1",
                    "MATCHER_READ_MODEL_VERSION": "pr29_serving_v1",
                    "MATCHER_READ_MODEL_MAX_AGE_SECONDS": "1",
                }
            ):
                stale_result = _run_request(client, path="/odds/matcher?limit=100&offset=0")

        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()

    runtime_payload = runtime_result.pop("payload")
    read_model_payload = read_model_result.pop("payload")
    missing_result.pop("payload")
    stale_result.pop("payload")

    output_payload = {
        "slice": "PR-M1b",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build_summary": build_summary,
        "scenarios": {
            "flag_off_runtime": runtime_result,
            "flag_on_fresh_read_model": read_model_result,
            "flag_on_missing_fallback": missing_result,
            "flag_on_stale_fallback": stale_result,
        },
        "parity": {
            "top_level_equal": (
                runtime_payload.get("total") == read_model_payload.get("total")
                and runtime_payload.get("offset") == read_model_payload.get("offset")
                and runtime_payload.get("limit") == read_model_payload.get("limit")
                and runtime_payload.get("has_more") == read_model_payload.get("has_more")
            ),
            "canonical_rows_equal": _canonical_rows(runtime_payload) == _canonical_rows(read_model_payload),
            "schema_fields_match": (
                bool(read_model_payload.get("items"))
                and set(read_model_payload["items"][0].keys()) == set(OddsMatchResponse.model_fields.keys())
            ),
        },
    }

    output = Path(output_path)
    output.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "parity": output_payload["parity"]}, indent=2))


if __name__ == "__main__":
    main()
