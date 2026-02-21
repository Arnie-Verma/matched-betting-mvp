"""
Generate PR-R3 matcher hot-path performance metrics.

Compares:
- legacy N+1 matcher query strategy
- optimized preloaded/set-based matcher strategy
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import mean, median
from typing import Any, Callable

from sqlalchemy import and_, create_engine, event
from sqlalchemy.orm import joinedload, sessionmaker

from api.core.database import Base
from api.models import Bookmaker, Competition, Event, Market, OddsSnapshot, Selection, Sport, User
from api.routers import odds_matcher


DEFAULT_OUTPUT = "docs/evidence/phase-a-hardening/2026-02-11/pr11_matcher_perf_metrics.json"


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = max(0.0, min(float(len(ordered) - 1), p * float(len(ordered) - 1)))
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    weight = idx - lo
    return float(ordered[lo] * (1.0 - weight) + ordered[hi] * weight)


def seed_data(session_factory, event_count: int = 80) -> None:
    db = session_factory()
    try:
        sport = Sport(code="soccer", name="Soccer", display_name="Soccer", is_active=True, sort_order=1)
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

        db.add(
            User(
                clerk_user_id="perf-user",
                email="perf@test.local",
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

            home = Selection(market_id=market.id, name=f"Team {idx}", selection_key="home")
            away = Selection(market_id=market.id, name=f"Opponent {idx}", selection_key="away")
            db.add_all([home, away])
            db.flush()

            for selection, price in ((home, Decimal("2.10")), (away, Decimal("2.40"))):
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
                        available_amount=Decimal("1000.00"),
                    )
                )

        db.commit()
    finally:
        db.close()


def run_legacy_matcher(db) -> int:
    now = datetime.now(timezone.utc)
    events = (
        db.query(Event)
        .join(Competition)
        .join(Sport)
        .filter(
            and_(
                Event.start_time >= now,
                Event.start_time <= now + timedelta(days=14),
                Event.status == "scheduled",
            )
        )
        .limit(500)
        .all()
    )

    grouped = defaultdict(list)
    for event in events:
        key = (
            f"{odds_matcher.normalize_event_name(event.name)}_"
            f"{odds_matcher.normalize_competition_name(event.competition.name if event.competition else '')}"
        )
        grouped[key].append(event)

    opportunities = 0
    for events_in_group in grouped.values():
        event_ids = [row.id for row in events_in_group]
        markets = (
            db.query(Market)
            .filter(
                and_(
                    Market.event_id.in_(event_ids),
                    Market.is_active == True,
                    odds_matcher._matcher_market_filter_clause(),
                )
            )
            .all()
        )

        all_selections = []
        for market in markets:
            all_selections.extend(db.query(Selection).filter(Selection.market_id == market.id).all())

        selection_groups = defaultdict(list)
        for selection in all_selections:
            key = (selection.selection_key or "").strip().lower() or (selection.name or "").lower().strip()
            selection_groups[key].append(selection.id)

        for selection_ids in selection_groups.values():
            back = (
                db.query(OddsSnapshot)
                .join(Bookmaker)
                .filter(
                    and_(
                        OddsSnapshot.selection_id.in_(selection_ids),
                        OddsSnapshot.is_current == True,
                        Bookmaker.code.in_(["ladbrokes", "neds"]),
                    )
                )
                .all()
            )
            lay = (
                db.query(OddsSnapshot)
                .join(Bookmaker)
                .filter(
                    and_(
                        OddsSnapshot.selection_id.in_(selection_ids),
                        OddsSnapshot.is_current == True,
                        Bookmaker.code == "betfair",
                    )
                )
                .all()
            )
            if back and lay:
                opportunities += 1

    return opportunities


def run_optimized_matcher(db) -> int:
    now = datetime.now(timezone.utc)
    events = (
        db.query(Event)
        .options(joinedload(Event.competition).joinedload(Competition.sport))
        .join(Competition)
        .join(Sport)
        .filter(
            and_(
                Event.start_time >= now,
                Event.start_time <= now + timedelta(days=14),
                Event.status == "scheduled",
            )
        )
        .limit(500)
        .all()
    )

    event_groups = odds_matcher._group_events(events)
    preloaded = odds_matcher._load_precomputed_matcher_data(
        db,
        event_ids=[event.id for event in events],
        bookmaker_filter=["ladbrokes", "neds", "betfair"],
    )
    markets_by_event_id = preloaded["markets_by_event_id"]
    selections_by_market_id = preloaded["selections_by_market_id"]
    odds_by_selection_id = preloaded["odds_by_selection_id"]

    opportunities = 0
    for events_in_group in event_groups.values():
        group_markets = []
        for event_row in events_in_group:
            group_markets.extend(markets_by_event_id.get(event_row.id, []))

        all_selections = []
        for market in group_markets:
            all_selections.extend(selections_by_market_id.get(market.id, []))

        selection_groups = defaultdict(list)
        for selection in all_selections:
            key = (selection.selection_key or "").strip().lower() or (selection.name or "").lower().strip()
            selection_groups[key].append(selection.id)

        for selection_ids in selection_groups.values():
            group_odds = []
            for selection_id in selection_ids:
                group_odds.extend(odds_by_selection_id.get(selection_id, []))
            back = [o for o in group_odds if o.bookmaker and o.bookmaker.code in {"ladbrokes", "neds"}]
            lay = [o for o in group_odds if o.bookmaker and o.bookmaker.code == "betfair"]
            if back and lay:
                opportunities += 1

    return opportunities


def measure(session_factory, engine, fn: Callable[[Any], int], iterations: int) -> dict[str, Any]:
    query_counts: list[int] = []
    durations_ms: list[float] = []
    opportunities: list[int] = []

    for _ in range(iterations):
        db = session_factory()
        counter = {"count": 0}

        def before_cursor_execute(_conn, _cursor, statement, _params, _context, _executemany):
            sql = statement.strip().upper()
            if sql.startswith(("SELECT", "INSERT", "UPDATE", "DELETE")):
                counter["count"] += 1

        event.listen(engine, "before_cursor_execute", before_cursor_execute)
        started = time.perf_counter()
        try:
            opportunities_found = fn(db)
        finally:
            elapsed = (time.perf_counter() - started) * 1000.0
            event.remove(engine, "before_cursor_execute", before_cursor_execute)
            db.close()

        query_counts.append(counter["count"])
        durations_ms.append(elapsed)
        opportunities.append(opportunities_found)

    return {
        "iterations": iterations,
        "query_count_min": min(query_counts),
        "query_count_median": median(query_counts),
        "query_count_p95": percentile(query_counts, 0.95),
        "latency_ms_mean": round(mean(durations_ms), 3),
        "latency_ms_p95": round(percentile(durations_ms, 0.95), 3),
        "opportunities_mean": round(mean(opportunities), 3),
    }


def main(output_path: str = DEFAULT_OUTPUT) -> None:
    with tempfile.TemporaryDirectory(prefix="pr11_matcher_") as tmpdir:
        db_path = os.path.join(tmpdir, "perf.sqlite")
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        seed_data(SessionLocal, event_count=80)

        legacy = measure(SessionLocal, engine, run_legacy_matcher, iterations=20)
        optimized = measure(SessionLocal, engine, run_optimized_matcher, iterations=20)

        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    payload = {
        "slice": "PR-R3",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scenario": {
            "events_seeded": 80,
            "bookmakers": ["ladbrokes", "neds", "betfair"],
            "window_days": 14,
        },
        "baseline_legacy_n_plus_one": legacy,
        "optimized_preloaded_set_based": optimized,
        "improvement": {
            "query_count_median_delta": legacy["query_count_median"] - optimized["query_count_median"],
            "query_count_median_reduction_pct": round(
                ((legacy["query_count_median"] - optimized["query_count_median"]) / legacy["query_count_median"]) * 100.0,
                2,
            )
            if legacy["query_count_median"]
            else 0.0,
            "latency_p95_ms_delta": round(
                legacy["latency_ms_p95"] - optimized["latency_ms_p95"],
                3,
            ),
            "latency_p95_reduction_pct": round(
                ((legacy["latency_ms_p95"] - optimized["latency_ms_p95"]) / legacy["latency_ms_p95"]) * 100.0,
                2,
            )
            if legacy["latency_ms_p95"]
            else 0.0,
        },
    }

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


if __name__ == "__main__":
    main()
