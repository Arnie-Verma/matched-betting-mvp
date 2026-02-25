"""Matcher read-model builder and shadow parity utilities."""
from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

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
)
from api.routers import odds_matcher as matcher_router
from api.services.matching_engine import BackBet, BetType, LayBet, MatchingEngine


DEFAULT_MATCHER_READ_MODEL_VERSION = "matcher_read_model_v1"
DEFAULT_MATCHER_EVENT_LIMIT = 500
DEFAULT_MATCHER_EVENT_BATCH_SIZE = 100
DEFAULT_MATCHER_ROW_BATCH_SIZE = 250
DEFAULT_MATCHER_READ_MODEL_SERVING_ENABLED = False
DEFAULT_MATCHER_READ_MODEL_MAX_AGE_SECONDS = 300


@dataclass(frozen=True)
class MatcherReadModelBuildConfig:
    read_model_version: str
    source_window_start: datetime
    source_window_end: datetime
    stake: Decimal = Decimal("100")
    bet_type: BetType = BetType.NORMAL
    min_rating: Optional[Decimal] = None
    bookmaker_codes: Optional[List[str]] = None
    sport_codes: Optional[List[str]] = None
    competition_codes: Optional[List[str]] = None
    competition_ids: Optional[List[int]] = None
    search: Optional[str] = None
    event_limit: int = DEFAULT_MATCHER_EVENT_LIMIT
    event_batch_size: int = DEFAULT_MATCHER_EVENT_BATCH_SIZE
    row_batch_size: int = DEFAULT_MATCHER_ROW_BATCH_SIZE


@dataclass(frozen=True)
class MatcherReadModelServingConfig:
    enabled: bool
    read_model_version: str
    max_age_seconds: int


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return bool(default)
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: Optional[str], fallback: int) -> int:
    if value is None or value == "":
        return int(fallback)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(fallback)
    return int(parsed) if parsed > 0 else int(fallback)


def load_matcher_read_model_serving_config_from_env() -> MatcherReadModelServingConfig:
    return MatcherReadModelServingConfig(
        enabled=_parse_bool(
            os.getenv("MATCHER_READ_MODEL_SERVING_ENABLED"),
            DEFAULT_MATCHER_READ_MODEL_SERVING_ENABLED,
        ),
        read_model_version=(os.getenv("MATCHER_READ_MODEL_VERSION") or DEFAULT_MATCHER_READ_MODEL_VERSION).strip()
        or DEFAULT_MATCHER_READ_MODEL_VERSION,
        max_age_seconds=_parse_int(
            os.getenv("MATCHER_READ_MODEL_MAX_AGE_SECONDS"),
            DEFAULT_MATCHER_READ_MODEL_MAX_AGE_SECONDS,
        ),
    )


def _coerce_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _normalized_list(values: Optional[Iterable[str]]) -> Optional[List[str]]:
    if values is None:
        return None
    output: list[str] = []
    for item in values:
        normalized = (item or "").strip().lower()
        if normalized and normalized not in output:
            output.append(normalized)
    return output or None


def _normalize_config(config: MatcherReadModelBuildConfig) -> MatcherReadModelBuildConfig:
    event_limit = max(1, int(config.event_limit))
    event_batch_size = max(1, int(config.event_batch_size))
    row_batch_size = max(1, int(config.row_batch_size))
    source_start = config.source_window_start
    source_end = config.source_window_end
    if source_start.tzinfo is None:
        source_start = source_start.replace(tzinfo=timezone.utc)
    if source_end.tzinfo is None:
        source_end = source_end.replace(tzinfo=timezone.utc)
    if source_start > source_end:
        raise ValueError("source_window_start must be <= source_window_end")
    read_model_version = (config.read_model_version or DEFAULT_MATCHER_READ_MODEL_VERSION).strip()
    if not read_model_version:
        read_model_version = DEFAULT_MATCHER_READ_MODEL_VERSION
    return MatcherReadModelBuildConfig(
        read_model_version=read_model_version,
        source_window_start=source_start,
        source_window_end=source_end,
        stake=Decimal(config.stake),
        bet_type=config.bet_type,
        min_rating=Decimal(config.min_rating) if config.min_rating is not None else None,
        bookmaker_codes=_normalized_list(config.bookmaker_codes),
        sport_codes=_normalized_list(config.sport_codes),
        competition_codes=_normalized_list(config.competition_codes),
        competition_ids=[int(item) for item in (config.competition_ids or [])],
        search=(config.search or None),
        event_limit=event_limit,
        event_batch_size=event_batch_size,
        row_batch_size=row_batch_size,
    )


def _resolve_bookmaker_codes(db: Session, codes: Optional[List[str]]) -> List[str]:
    if codes:
        return sorted(set(codes))
    rows = db.query(Bookmaker.code).filter(Bookmaker.is_active == True).all()  # noqa: E712
    return sorted({str(row[0]).strip().lower() for row in rows if row and row[0]})


def _fetch_events_in_batches(
    db: Session,
    *,
    source_window_start: datetime,
    source_window_end: datetime,
    sport_codes: Optional[List[str]],
    competition_ids: Optional[List[int]],
    search: Optional[str],
    event_limit: int,
    event_batch_size: int,
) -> Dict[str, Any]:
    query = (
        db.query(Event)
        .options(joinedload(Event.competition).joinedload(Competition.sport))
        .join(Competition)
        .join(Sport)
        .filter(
            and_(
                Event.start_time >= source_window_start,
                Event.start_time <= source_window_end,
                Event.status == "scheduled",
            )
        )
        .order_by(Event.start_time.asc(), Event.id.asc())
    )

    if sport_codes:
        query = query.filter(Sport.code.in_(sport_codes))
    if competition_ids:
        query = query.filter(Event.competition_id.in_(competition_ids))
    if search:
        query = query.filter(Event.name.ilike(f"%{search}%"))

    events: list[Event] = []
    event_batch_count = 0
    query_round_trip_signal = 0
    offset = 0
    while len(events) < event_limit:
        remaining = int(event_limit) - len(events)
        fetch_size = min(int(event_batch_size), remaining)
        batch = query.offset(offset).limit(fetch_size).all()
        query_round_trip_signal += 1
        event_batch_count += 1
        if not batch:
            break
        events.extend(batch)
        offset += len(batch)
        if len(batch) < fetch_size:
            break

    return {
        "events": events,
        "event_batch_count": int(event_batch_count),
        "query_round_trip_signal": int(query_round_trip_signal),
    }


def compute_runtime_matcher_opportunities(
    db: Session,
    *,
    config: MatcherReadModelBuildConfig,
) -> Dict[str, Any]:
    """Compute matcher opportunities from canonical source tables."""
    cfg = _normalize_config(config)
    bookmaker_filter = _resolve_bookmaker_codes(db, cfg.bookmaker_codes)
    if not bookmaker_filter:
        return {
            "opportunities": [],
            "bookmaker_codes": [],
            "processed_events": 0,
            "event_batch_count": 0,
            "query_round_trip_signal": 0,
            "source_max_odds_timestamp": None,
        }

    events_result = _fetch_events_in_batches(
        db,
        source_window_start=cfg.source_window_start,
        source_window_end=cfg.source_window_end,
        sport_codes=cfg.sport_codes,
        competition_ids=cfg.competition_ids,
        search=cfg.search,
        event_limit=cfg.event_limit,
        event_batch_size=cfg.event_batch_size,
    )
    events: list[Event] = events_result["events"]
    query_round_trip_signal = int(events_result["query_round_trip_signal"])

    # Apply normalized competition filter after retrieval to keep matcher semantics.
    if cfg.competition_codes:
        normalized_codes = {
            matcher_router.normalize_competition_name(code)
            for code in cfg.competition_codes
            if code
        }
        if normalized_codes:
            filtered: list[Event] = []
            for event in events:
                comp_name = ""
                if event.competition:
                    comp_name = event.competition.name or event.competition.short_name or ""
                if matcher_router.normalize_competition_name(comp_name) in normalized_codes:
                    filtered.append(event)
            events = filtered

    if not events:
        return {
            "opportunities": [],
            "bookmaker_codes": bookmaker_filter,
            "processed_events": 0,
            "event_batch_count": int(events_result["event_batch_count"]),
            "query_round_trip_signal": int(query_round_trip_signal),
            "source_max_odds_timestamp": None,
        }

    event_groups = matcher_router._group_events(events)
    preloaded = matcher_router._load_precomputed_matcher_data(
        db,
        event_ids=[event.id for event in events],
        bookmaker_filter=bookmaker_filter,
    )
    query_round_trip_signal += int(preloaded.get("query_round_trip_signal", 0) or 0)
    markets_by_event_id: Dict[int, List[Market]] = preloaded["markets_by_event_id"]
    selections_by_market_id: Dict[int, List[Selection]] = preloaded["selections_by_market_id"]
    odds_by_selection_id: Dict[int, List[OddsSnapshot]] = preloaded["odds_by_selection_id"]

    opportunities: list[matcher_router.OddsMatchResponse] = []
    matching_engine = MatchingEngine()
    back_bookmakers = [code for code in bookmaker_filter if code != "betfair"]
    source_max_odds_timestamp: Optional[datetime] = None

    for events_in_group in event_groups.values():
        representative_event = events_in_group[0]
        sport_code = (
            representative_event.competition.sport.code
            if representative_event.competition and representative_event.competition.sport
            else ""
        )

        group_markets: list[Market] = []
        for event in events_in_group:
            group_markets.extend(markets_by_event_id.get(event.id, []))
        if not group_markets:
            continue

        all_selections: list[Selection] = []
        for market in group_markets:
            all_selections.extend(selections_by_market_id.get(market.id, []))
        if not all_selections:
            continue

        selection_groups: Dict[str, Dict[str, Any]] = {}
        for selection in all_selections:
            selection_group_key = (selection.selection_key or "").strip().lower()
            if not selection_group_key:
                selection_group_key = matcher_router.normalize_selection_name(selection.name)
            if not selection_group_key:
                selection_group_key = (selection.name or "").lower().strip()

            if selection_group_key not in selection_groups:
                selection_groups[selection_group_key] = {
                    "selections": [],
                    "selection_ids": [],
                }
            selection_groups[selection_group_key]["selections"].append(selection)
            selection_groups[selection_group_key]["selection_ids"].append(selection.id)

        for group in selection_groups.values():
            selection_ids = group["selection_ids"]
            selection_by_id = {s.id: s for s in group.get("selections", [])}

            group_odds: list[OddsSnapshot] = []
            for selection_id in selection_ids:
                group_odds.extend(odds_by_selection_id.get(selection_id, []))

            back_odds_list = [
                odds_row
                for odds_row in group_odds
                if odds_row.bookmaker and odds_row.bookmaker.code in back_bookmakers
            ]
            lay_odds = [
                odds_row
                for odds_row in group_odds
                if odds_row.bookmaker
                and odds_row.bookmaker.code == "betfair"
                and odds_row.decimal_odds < Decimal("100")
            ]
            if not back_odds_list or not lay_odds:
                continue

            selection = group["selections"][0]

            def market_rank_for_snapshot(snapshot: OddsSnapshot) -> int:
                sel = selection_by_id.get(snapshot.selection_id)
                market_name = sel.market.name if sel and sel.market else ""
                return matcher_router._market_preference_rank(sport_code, market_name)

            lay_by_rank: Dict[int, List[OddsSnapshot]] = {}
            for lay_row in lay_odds:
                rank = market_rank_for_snapshot(lay_row)
                lay_by_rank.setdefault(rank, []).append(lay_row)

            best_lay_by_rank: Dict[int, OddsSnapshot] = {}
            for rank, items in lay_by_rank.items():
                best_lay_by_rank[rank] = min(items, key=lambda x: x.decimal_odds)

            bookmaker_best_odds: Dict[str, OddsSnapshot] = {}
            for back_odds in back_odds_list:
                bookmaker = back_odds.bookmaker
                if not bookmaker:
                    continue
                bm_code = bookmaker.code
                existing = bookmaker_best_odds.get(bm_code)
                if not existing:
                    bookmaker_best_odds[bm_code] = back_odds
                    continue
                existing_rank = market_rank_for_snapshot(existing)
                candidate_rank = market_rank_for_snapshot(back_odds)
                if candidate_rank < existing_rank:
                    bookmaker_best_odds[bm_code] = back_odds
                elif candidate_rank == existing_rank and back_odds.decimal_odds > existing.decimal_odds:
                    bookmaker_best_odds[bm_code] = back_odds

            for best_back in bookmaker_best_odds.values():
                back_rank = market_rank_for_snapshot(best_back)
                best_lay = best_lay_by_rank.get(back_rank)
                if not best_lay:
                    continue

                back_selection = selection_by_id.get(best_back.selection_id, selection)
                lay_selection = selection_by_id.get(best_lay.selection_id)
                if lay_selection and back_selection:
                    back_key = (back_selection.selection_key or "").strip().lower()
                    lay_key = (lay_selection.selection_key or "").strip().lower()
                    if not (back_key and lay_key and back_key == lay_key):
                        score = matcher_router.fuzzy_match_score(back_selection.name, lay_selection.name)
                        if score < 0.75:
                            continue

                back_bet = BackBet(
                    bookmaker_code=best_back.bookmaker.code,
                    bookmaker_name=best_back.bookmaker.display_name,
                    back_odds=best_back.decimal_odds,
                    stake=cfg.stake,
                )
                lay_bet = LayBet(
                    lay_odds=best_lay.decimal_odds,
                    commission=Decimal("0.06"),
                    liquidity=best_lay.available_amount,
                )
                calculation = matching_engine.calculate_matched_bet(back_bet, lay_bet, cfg.bet_type)
                if cfg.min_rating is not None and calculation.rating < cfg.min_rating:
                    continue

                pnl_pct = matching_engine.calculate_pnl_percentage(calculation)
                market = back_selection.market if back_selection else selection.market
                response_selection = back_selection if back_selection else selection
                opportunities.append(
                    matcher_router.OddsMatchResponse(
                        event_id=representative_event.id,
                        event_name=representative_event.name,
                        event_start_time=representative_event.start_time,
                        sport_name=(
                            representative_event.competition.sport.display_name
                            if representative_event.competition and representative_event.competition.sport
                            else ""
                        ),
                        competition_name=matcher_router.get_competition_display_name(
                            representative_event.competition.name if representative_event.competition else ""
                        ),
                        market_id=market.id,
                        market_name=market.name,
                        market_type=market.market_type,
                        selection_id=response_selection.id,
                        selection_name=response_selection.name,
                        back_bookmaker_code=calculation.back_bet.bookmaker_code,
                        back_bookmaker_name=calculation.back_bet.bookmaker_name,
                        back_odds=float(calculation.back_bet.back_odds),
                        back_stake=float(calculation.back_stake),
                        lay_odds=float(calculation.lay_bet.lay_odds),
                        lay_stake=float(calculation.lay_stake),
                        lay_liability=float(calculation.lay_liability),
                        lay_commission=float(calculation.lay_bet.commission),
                        lay_liquidity=float(calculation.lay_bet.liquidity) if calculation.lay_bet.liquidity else None,
                        profit_if_back_wins=float(calculation.profit_if_back_wins),
                        profit_if_lay_wins=float(calculation.profit_if_lay_wins),
                        qualifying_loss=float(calculation.qualifying_loss),
                        pnl_percentage=float(pnl_pct),
                        bet_type=calculation.bet_type,
                        rating=float(calculation.rating),
                        last_updated=best_back.timestamp,
                    )
                )
                if source_max_odds_timestamp is None or best_back.timestamp > source_max_odds_timestamp:
                    source_max_odds_timestamp = best_back.timestamp

    opportunities.sort(
        key=lambda x: (
            x.pnl_percentage,
            x.event_start_time.timestamp() if x.event_start_time else 0.0,
            x.event_id,
            x.selection_id,
            x.back_bookmaker_code,
        ),
        reverse=True,
    )
    return {
        "opportunities": opportunities,
        "bookmaker_codes": bookmaker_filter,
        "processed_events": len(events),
        "event_batch_count": int(events_result["event_batch_count"]),
        "query_round_trip_signal": int(query_round_trip_signal),
        "source_max_odds_timestamp": source_max_odds_timestamp,
    }


def _row_key_for_payload(payload: Dict[str, Any]) -> str:
    seed = "|".join(
        [
            str(payload.get("event_id")),
            str(payload.get("market_id")),
            str(payload.get("selection_id")),
            str(payload.get("back_bookmaker_code")),
            str(payload.get("bet_type")),
        ]
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def build_matcher_read_model(
    db: Session,
    *,
    config: MatcherReadModelBuildConfig,
) -> Dict[str, Any]:
    cfg = _normalize_config(config)
    started_at = _utcnow()
    run_id = str(uuid.uuid4())

    runtime = compute_runtime_matcher_opportunities(db, config=cfg)
    opportunities: list[matcher_router.OddsMatchResponse] = runtime["opportunities"]
    built_at = _utcnow()

    build = (
        db.query(MatcherReadModelBuild)
        .filter(MatcherReadModelBuild.read_model_version == cfg.read_model_version)
        .first()
    )
    if build is None:
        build = MatcherReadModelBuild(
            read_model_version=cfg.read_model_version,
            builder_run_id=run_id,
            built_at=built_at,
            source_window_start=cfg.source_window_start,
            source_window_end=cfg.source_window_end,
            source_max_odds_timestamp=runtime.get("source_max_odds_timestamp"),
            event_limit=cfg.event_limit,
            event_batch_size=cfg.event_batch_size,
            row_batch_size=cfg.row_batch_size,
            processed_events=int(runtime.get("processed_events", 0)),
            upserted_rows=0,
            deleted_stale_rows=0,
            build_summary={},
            created_at=built_at,
            updated_at=built_at,
        )
        db.add(build)
        db.flush()
    else:
        build.builder_run_id = run_id
        build.built_at = built_at
        build.source_window_start = cfg.source_window_start
        build.source_window_end = cfg.source_window_end
        build.source_max_odds_timestamp = runtime.get("source_max_odds_timestamp")
        build.event_limit = cfg.event_limit
        build.event_batch_size = cfg.event_batch_size
        build.row_batch_size = cfg.row_batch_size
        build.processed_events = int(runtime.get("processed_events", 0))
        build.updated_at = built_at
        db.flush()

    payloads = [opp.model_dump(mode="json") for opp in opportunities]
    upserted_rows = 0
    for idx in range(0, len(payloads), int(cfg.row_batch_size)):
        chunk = payloads[idx : idx + int(cfg.row_batch_size)]
        row_keys = [_row_key_for_payload(payload) for payload in chunk]
        existing = (
            db.query(MatcherReadModelRow)
            .filter(
                MatcherReadModelRow.read_model_version == cfg.read_model_version,
                MatcherReadModelRow.row_key.in_(row_keys),
            )
            .all()
        )
        existing_by_key = {row.row_key: row for row in existing}

        for payload in chunk:
            row_key = _row_key_for_payload(payload)
            row = existing_by_key.get(row_key)
            if row is None:
                row = MatcherReadModelRow(
                    build_id=build.id,
                    read_model_version=cfg.read_model_version,
                    row_key=row_key,
                    builder_run_id=run_id,
                    built_at=built_at,
                    source_window_start=cfg.source_window_start,
                    source_window_end=cfg.source_window_end,
                    event_id=int(payload["event_id"]),
                    market_id=int(payload["market_id"]),
                    selection_id=int(payload["selection_id"]),
                    back_bookmaker_code=str(payload["back_bookmaker_code"]),
                    rating=Decimal(str(payload["rating"])),
                    pnl_percentage=Decimal(str(payload["pnl_percentage"])),
                    last_updated=datetime.fromisoformat(str(payload["last_updated"])),
                    payload=payload,
                    created_at=built_at,
                    updated_at=built_at,
                )
                db.add(row)
            else:
                row.build_id = build.id
                row.builder_run_id = run_id
                row.built_at = built_at
                row.source_window_start = cfg.source_window_start
                row.source_window_end = cfg.source_window_end
                row.event_id = int(payload["event_id"])
                row.market_id = int(payload["market_id"])
                row.selection_id = int(payload["selection_id"])
                row.back_bookmaker_code = str(payload["back_bookmaker_code"])
                row.rating = Decimal(str(payload["rating"]))
                row.pnl_percentage = Decimal(str(payload["pnl_percentage"]))
                row.last_updated = datetime.fromisoformat(str(payload["last_updated"]))
                row.payload = payload
                row.updated_at = built_at
            upserted_rows += 1

    # Session autoflush is disabled globally; flush row mutations before stale-row pruning.
    db.flush()
    deleted_stale_rows = int(
        db.query(MatcherReadModelRow)
        .filter(
            MatcherReadModelRow.read_model_version == cfg.read_model_version,
            MatcherReadModelRow.builder_run_id != run_id,
        )
        .delete(synchronize_session=False)
    )

    build.upserted_rows = int(upserted_rows)
    build.deleted_stale_rows = int(deleted_stale_rows)
    build.build_summary = {
        "processed_events": int(runtime.get("processed_events", 0)),
        "event_batch_count": int(runtime.get("event_batch_count", 0)),
        "query_round_trip_signal": int(runtime.get("query_round_trip_signal", 0)),
        "opportunity_count": len(payloads),
        "bookmaker_codes": list(runtime.get("bookmaker_codes", [])),
    }
    build.updated_at = _utcnow()
    db.commit()

    row_count = int(
        db.query(MatcherReadModelRow)
        .filter(MatcherReadModelRow.read_model_version == cfg.read_model_version)
        .count()
    )
    completed_at = _utcnow()
    return {
        "read_model_version": cfg.read_model_version,
        "builder_run_id": run_id,
        "built_at": built_at.isoformat(),
        "source_window_start": cfg.source_window_start.isoformat(),
        "source_window_end": cfg.source_window_end.isoformat(),
        "source_max_odds_timestamp": (
            runtime.get("source_max_odds_timestamp").isoformat()
            if runtime.get("source_max_odds_timestamp") is not None
            else None
        ),
        "stake": str(cfg.stake),
        "bet_type": cfg.bet_type.value,
        "event_limit": int(cfg.event_limit),
        "event_batch_size": int(cfg.event_batch_size),
        "row_batch_size": int(cfg.row_batch_size),
        "processed_events": int(runtime.get("processed_events", 0)),
        "event_batch_count": int(runtime.get("event_batch_count", 0)),
        "query_round_trip_signal": int(runtime.get("query_round_trip_signal", 0)),
        "upserted_rows": int(upserted_rows),
        "deleted_stale_rows": int(deleted_stale_rows),
        "row_count": int(row_count),
        "duration_ms": int((completed_at - started_at).total_seconds() * 1000),
    }


def get_read_model_payloads(
    db: Session,
    *,
    read_model_version: str,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    query = (
        db.query(MatcherReadModelRow)
        .filter(MatcherReadModelRow.read_model_version == read_model_version)
        .order_by(MatcherReadModelRow.pnl_percentage.desc(), MatcherReadModelRow.id.asc())
    )
    if isinstance(limit, int) and limit > 0:
        query = query.limit(int(limit))
    rows = query.all()
    return [dict(row.payload or {}) for row in rows]


def get_read_model_serving_snapshot(
    db: Session,
    *,
    read_model_version: str,
    max_age_seconds: int,
    limit: Optional[int] = None,
    offset: int = 0,
    bookmaker_codes: Optional[List[str]] = None,
    min_rating: Optional[Decimal] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Resolve read-model payloads for serving with freshness checks.

    Returns:
    - `ok`: whether read-model is healthy for serving
    - `reason_code`: deterministic fallback reason when `ok` is False
    - `payloads`: read-model rows when healthy
    - `total_count`: filtered total rows (for pagination metadata)
    - `materialized_row_count`: rows materialized on this request path
    - `query_round_trip_signal`: DB query count signal for telemetry parity
    """
    signal = 0
    current_time = _coerce_utc(now) or _utcnow()
    version = (read_model_version or DEFAULT_MATCHER_READ_MODEL_VERSION).strip() or DEFAULT_MATCHER_READ_MODEL_VERSION
    max_age = max(1, int(max_age_seconds))
    page_limit = max(1, int(limit)) if isinstance(limit, int) else None
    page_offset = max(0, int(offset))
    normalized_bookmaker_codes = _normalized_list(bookmaker_codes)
    normalized_min_rating = Decimal(str(min_rating)) if min_rating is not None else None

    build = (
        db.query(MatcherReadModelBuild)
        .filter(MatcherReadModelBuild.read_model_version == version)
        .first()
    )
    signal += 1
    if build is None:
        return {
            "ok": False,
            "reason_code": "read_model_missing_build",
            "payloads": [],
            "total_count": 0,
            "materialized_row_count": 0,
            "query_round_trip_signal": signal,
            "build": None,
        }

    built_at = _coerce_utc(build.built_at)
    if built_at is None:
        return {
            "ok": False,
            "reason_code": "read_model_invalid_built_at",
            "payloads": [],
            "total_count": 0,
            "materialized_row_count": 0,
            "query_round_trip_signal": signal,
            "build": build,
        }

    age_seconds = max(0.0, (current_time - built_at).total_seconds())
    if age_seconds > float(max_age):
        return {
            "ok": False,
            "reason_code": "read_model_stale",
            "payloads": [],
            "total_count": 0,
            "materialized_row_count": 0,
            "query_round_trip_signal": signal,
            "build": build,
            "age_seconds": age_seconds,
        }

    base_query = db.query(MatcherReadModelRow).filter(
        MatcherReadModelRow.read_model_version == version,
    )
    if normalized_bookmaker_codes:
        base_query = base_query.filter(
            MatcherReadModelRow.back_bookmaker_code.in_(normalized_bookmaker_codes),
        )
    if normalized_min_rating is not None:
        base_query = base_query.filter(MatcherReadModelRow.rating >= normalized_min_rating)

    row_count = int(base_query.order_by(None).count())
    signal += 1
    if row_count <= 0:
        has_explicit_filters = bool(normalized_bookmaker_codes) or normalized_min_rating is not None
        if has_explicit_filters:
            total_unfiltered_count = int(
                db.query(MatcherReadModelRow)
                .filter(MatcherReadModelRow.read_model_version == version)
                .order_by(None)
                .count()
            )
            signal += 1
            if total_unfiltered_count > 0:
                return {
                    "ok": True,
                    "reason_code": None,
                    "payloads": [],
                    "total_count": 0,
                    "materialized_row_count": 0,
                    "query_round_trip_signal": signal,
                    "build": build,
                    "age_seconds": age_seconds,
                }
        return {
            "ok": False,
            "reason_code": "read_model_no_rows",
            "payloads": [],
            "total_count": 0,
            "materialized_row_count": 0,
            "query_round_trip_signal": signal,
            "build": build,
        }

    row_query = base_query.order_by(
        MatcherReadModelRow.pnl_percentage.desc(),
        MatcherReadModelRow.id.asc(),
    )
    if page_limit is not None:
        row_query = row_query.offset(page_offset).limit(page_limit)
    rows = row_query.all()
    signal += 1
    payloads = [dict(row.payload or {}) for row in rows]

    return {
        "ok": True,
        "reason_code": None,
        "payloads": payloads,
        "total_count": int(row_count),
        "materialized_row_count": int(len(payloads)),
        "query_round_trip_signal": signal,
        "build": build,
        "age_seconds": age_seconds,
    }


def run_shadow_parity_check(
    db: Session,
    *,
    config: MatcherReadModelBuildConfig,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    cfg = _normalize_config(config)
    runtime_result = compute_runtime_matcher_opportunities(db, config=cfg)
    runtime_payloads = [opp.model_dump(mode="json") for opp in runtime_result["opportunities"]]
    read_model_payloads = get_read_model_payloads(
        db,
        read_model_version=cfg.read_model_version,
        limit=limit,
    )

    if isinstance(limit, int) and limit > 0:
        runtime_payloads = runtime_payloads[: int(limit)]

    runtime_by_key = {_row_key_for_payload(payload): payload for payload in runtime_payloads}
    read_by_key = {_row_key_for_payload(payload): payload for payload in read_model_payloads}

    runtime_keys = set(runtime_by_key.keys())
    read_keys = set(read_by_key.keys())
    only_runtime = sorted(runtime_keys - read_keys)
    only_read = sorted(read_keys - runtime_keys)

    field_mismatches: list[Dict[str, Any]] = []
    common = sorted(runtime_keys.intersection(read_keys))
    for key in common:
        runtime_payload = runtime_by_key[key]
        read_payload = read_by_key[key]
        if runtime_payload != read_payload:
            field_mismatches.append(
                {
                    "row_key": key,
                    "runtime_payload": runtime_payload,
                    "read_model_payload": read_payload,
                }
            )
            if len(field_mismatches) >= 10:
                break

    parity_pass = not only_runtime and not only_read and not field_mismatches
    return {
        "parity_pass": bool(parity_pass),
        "runtime_count": len(runtime_payloads),
        "read_model_count": len(read_model_payloads),
        "only_in_runtime_count": len(only_runtime),
        "only_in_read_model_count": len(only_read),
        "field_mismatch_count": len(field_mismatches),
        "only_in_runtime_sample": only_runtime[:10],
        "only_in_read_model_sample": only_read[:10],
        "field_mismatch_sample": field_mismatches,
    }


def default_foundation_config(
    *,
    read_model_version: str = DEFAULT_MATCHER_READ_MODEL_VERSION,
    source_window_hours: int = 24 * 14,
    event_limit: int = DEFAULT_MATCHER_EVENT_LIMIT,
    event_batch_size: int = DEFAULT_MATCHER_EVENT_BATCH_SIZE,
    row_batch_size: int = DEFAULT_MATCHER_ROW_BATCH_SIZE,
    bookmaker_codes: Optional[List[str]] = None,
) -> MatcherReadModelBuildConfig:
    now = _utcnow()
    return MatcherReadModelBuildConfig(
        read_model_version=read_model_version,
        source_window_start=now,
        source_window_end=now + timedelta(hours=max(1, int(source_window_hours))),
        event_limit=max(1, int(event_limit)),
        event_batch_size=max(1, int(event_batch_size)),
        row_batch_size=max(1, int(row_batch_size)),
        bookmaker_codes=bookmaker_codes,
    )
