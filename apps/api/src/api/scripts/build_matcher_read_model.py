"""Build matcher read-model foundation snapshot with optional shadow parity check."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from api.core.database import SessionLocal
from api.services.matcher_read_model_service import (
    DEFAULT_MATCHER_EVENT_BATCH_SIZE,
    DEFAULT_MATCHER_EVENT_LIMIT,
    DEFAULT_MATCHER_READ_MODEL_VERSION,
    DEFAULT_MATCHER_ROW_BATCH_SIZE,
    MatcherReadModelBuildConfig,
    build_matcher_read_model,
    run_shadow_parity_check,
)
from api.services.matching_engine import BetType


def _parse_csv(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    parts = [(part or "").strip().lower() for part in raw.split(",")]
    items = [part for part in parts if part]
    return items or None


def _parse_int_or(raw: int | None, fallback: int) -> int:
    if isinstance(raw, int) and raw > 0:
        return int(raw)
    return int(fallback)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build matcher read-model foundation snapshot")
    parser.add_argument("--read-model-version", type=str, default=DEFAULT_MATCHER_READ_MODEL_VERSION)
    parser.add_argument("--source-window-hours", type=int, default=24 * 14)
    parser.add_argument("--event-limit", type=int, default=DEFAULT_MATCHER_EVENT_LIMIT)
    parser.add_argument("--event-batch-size", type=int, default=DEFAULT_MATCHER_EVENT_BATCH_SIZE)
    parser.add_argument("--row-batch-size", type=int, default=DEFAULT_MATCHER_ROW_BATCH_SIZE)
    parser.add_argument("--stake", type=str, default="100")
    parser.add_argument("--bet-type", type=str, choices=[item.value for item in BetType], default=BetType.NORMAL.value)
    parser.add_argument("--min-rating", type=str, default=None)
    parser.add_argument("--bookmaker-codes", type=str, default=None, help="Comma-separated bookmaker codes")
    parser.add_argument("--sport-codes", type=str, default=None, help="Comma-separated sport codes")
    parser.add_argument("--competition-codes", type=str, default=None, help="Comma-separated competition codes")
    parser.add_argument("--competition-ids", type=str, default=None, help="Comma-separated competition IDs")
    parser.add_argument("--search", type=str, default=None)
    parser.add_argument("--shadow-parity", action="store_true", help="Run non-serving parity check after build")
    parser.add_argument("--shadow-parity-limit", type=int, default=None)
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    config = MatcherReadModelBuildConfig(
        read_model_version=(args.read_model_version or DEFAULT_MATCHER_READ_MODEL_VERSION).strip(),
        source_window_start=now,
        source_window_end=now + timedelta(hours=max(1, int(args.source_window_hours))),
        stake=Decimal(str(args.stake)),
        bet_type=BetType(args.bet_type),
        min_rating=Decimal(str(args.min_rating)) if args.min_rating else None,
        bookmaker_codes=_parse_csv(args.bookmaker_codes),
        sport_codes=_parse_csv(args.sport_codes),
        competition_codes=_parse_csv(args.competition_codes),
        competition_ids=[int(item.strip()) for item in (args.competition_ids or "").split(",") if item.strip().isdigit()],
        search=(args.search or None),
        event_limit=_parse_int_or(args.event_limit, DEFAULT_MATCHER_EVENT_LIMIT),
        event_batch_size=_parse_int_or(args.event_batch_size, DEFAULT_MATCHER_EVENT_BATCH_SIZE),
        row_batch_size=_parse_int_or(args.row_batch_size, DEFAULT_MATCHER_ROW_BATCH_SIZE),
    )

    db = SessionLocal()
    try:
        build_summary = build_matcher_read_model(db, config=config)
        output: dict[str, object] = {
            "build_summary": build_summary,
            "shadow_parity": None,
        }
        if args.shadow_parity:
            output["shadow_parity"] = run_shadow_parity_check(
                db,
                config=config,
                limit=args.shadow_parity_limit,
            )
    finally:
        db.close()

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

