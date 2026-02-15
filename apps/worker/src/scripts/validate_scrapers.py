#!/usr/bin/env python
"""
Scraper Validation CLI

Validates scraped odds data against reference bookmaker.
Designed for manual testing and CI/CD integration.

Usage:
    # Validate all bookmakers for a competition
    python -m scripts.validate_scrapers --competition laliga

    # Validate specific bookmaker
    python -m scripts.validate_scrapers --competition laliga --bookmaker mintbet

    # Output JSON (for CI/CD)
    python -m scripts.validate_scrapers --competition laliga --format json

    # Live scrape and validate
    python -m scripts.validate_scrapers --competition laliga --scrape

    # Validate from database (no scraping)
    python -m scripts.validate_scrapers --competition laliga --from-db
"""
import argparse
import asyncio
import logging
import os
import sys
import time
from decimal import Decimal
from typing import Dict, Any, List

# Add paths for imports
sys.path.insert(0, "apps/worker/src")
sys.path.insert(0, "apps/api/src")

from validation.pipeline import ValidationPipeline
from validation.config import ValidationConfig, EXPECTED_EVENTS


def setup_logging(verbose: bool = False):
    """Configure logging for CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def list_competitions():
    """List available competitions."""
    print("\nAvailable competitions:")
    print("-" * 40)
    for comp, config in sorted(EXPECTED_EVENTS.items()):
        print(f"  {comp:<15} (typical: {config['typical']} events)")
    print()


def run_boxing_evidence_checks(bookmaker: str = None) -> Dict[str, Any]:
    """
    Monitoring-only boxing checks for Unibet vs Betfair selection stability.

    Evidence metrics:
    - Coverage: shared events with both bookmakers (home/away present) vs Betfair events
    - Swapped-fighter anomalies: events where Unibet home/away appears reversed vs Betfair
    """
    from collections import defaultdict

    from api.core.database import SessionLocal
    from api.models import Event, Market, Selection, OddsSnapshot, Bookmaker, Competition
    from api.services.normalization_service import normalize_competition_name, fuzzy_match_score

    # "Go" thresholds from Unibet implementation plan.
    coverage_threshold = Decimal("90")
    max_swapped_anomalies = 1

    # This check is specifically about Unibet boxing ordering vs Betfair.
    if bookmaker and bookmaker not in {"unibet", "betfair"}:
        return {
            "applicable": False,
            "reason": f"Bookmaker '{bookmaker}' is outside Unibet/Betfair boxing stability scope",
        }

    db = SessionLocal()
    try:
        rows = db.query(
            Event.id.label("event_id"),
            Event.name.label("event_name"),
            Competition.name.label("competition_name"),
            Bookmaker.code.label("bookmaker_code"),
            Selection.selection_key.label("selection_key"),
            Selection.name.label("selection_name"),
        ).join(
            Market, Market.event_id == Event.id
        ).join(
            Selection, Selection.market_id == Market.id
        ).join(
            OddsSnapshot, OddsSnapshot.selection_id == Selection.id
        ).join(
            Bookmaker, OddsSnapshot.bookmaker_id == Bookmaker.id
        ).join(
            Competition, Event.competition_id == Competition.id
        ).filter(
            OddsSnapshot.is_current == True,
            Market.market_type == "match_winner",
            Bookmaker.code.in_(["unibet", "betfair"]),
        ).all()

        event_names: Dict[int, str] = {}
        event_bookmaker_sides: Dict[int, Dict[str, Dict[str, str]]] = defaultdict(lambda: defaultdict(dict))

        for row in rows:
            if normalize_competition_name(row.competition_name or "") != "boxing":
                continue
            selection_key = (row.selection_key or "").strip().lower()
            if selection_key not in {"home", "away"}:
                continue
            event_names[row.event_id] = row.event_name
            event_bookmaker_sides[row.event_id][row.bookmaker_code][selection_key] = row.selection_name

        betfair_events = {
            eid for eid, data in event_bookmaker_sides.items()
            if "betfair" in data and {"home", "away"}.issubset(set(data["betfair"].keys()))
        }
        unibet_events = {
            eid for eid, data in event_bookmaker_sides.items()
            if "unibet" in data and {"home", "away"}.issubset(set(data["unibet"].keys()))
        }
        shared_events = betfair_events & unibet_events

        coverage_percent = (
            (Decimal(len(shared_events)) / Decimal(len(betfair_events)) * Decimal("100"))
            if betfair_events else Decimal("0")
        ).quantize(Decimal("0.01"))

        swapped_anomalies: List[Dict[str, Any]] = []
        for event_id in sorted(shared_events):
            unibet = event_bookmaker_sides[event_id]["unibet"]
            betfair = event_bookmaker_sides[event_id]["betfair"]

            uh = unibet.get("home", "")
            ua = unibet.get("away", "")
            bh = betfair.get("home", "")
            ba = betfair.get("away", "")
            if not (uh and ua and bh and ba):
                continue

            same_home = fuzzy_match_score(uh, bh)
            same_away = fuzzy_match_score(ua, ba)
            cross_home = fuzzy_match_score(uh, ba)
            cross_away = fuzzy_match_score(ua, bh)

            is_swapped = (
                cross_home >= 0.75 and
                cross_away >= 0.75 and
                same_home < 0.60 and
                same_away < 0.60
            )
            if is_swapped:
                swapped_anomalies.append({
                    "event_id": event_id,
                    "event_name": event_names.get(event_id, str(event_id)),
                    "unibet_home": uh,
                    "unibet_away": ua,
                    "betfair_home": bh,
                    "betfair_away": ba,
                    "scores": {
                        "same_home": round(same_home, 3),
                        "same_away": round(same_away, 3),
                        "cross_home": round(cross_home, 3),
                        "cross_away": round(cross_away, 3),
                    },
                })

        follow_up_required = (
            coverage_percent < coverage_threshold or
            len(swapped_anomalies) > max_swapped_anomalies
        )

        return {
            "applicable": True,
            "coverage_percent": str(coverage_percent),
            "coverage_threshold_percent": str(coverage_threshold),
            "betfair_events": len(betfair_events),
            "unibet_events": len(unibet_events),
            "shared_events": len(shared_events),
            "swapped_anomaly_count": len(swapped_anomalies),
            "max_swapped_anomalies": max_swapped_anomalies,
            "swapped_anomalies": swapped_anomalies[:5],
            "follow_up_required": follow_up_required,
        }
    finally:
        db.close()


async def scrape_and_validate(
    competition: str,
    bookmaker: str = None,
    config: ValidationConfig = None,
) -> dict:
    """
    Scrape live data and validate.

    Args:
        competition: Competition to validate
        bookmaker: Optional specific bookmaker
        config: Validation config

    Returns:
        Validation result dict
    """
    from datetime import datetime, timezone

    from jobs.scrape_service import get_scrape_service
    from jobs.save_odds import save_scrape_result_to_db
    from scrapers.base import ScraperStatus

    config = config or ValidationConfig()

    print(f"\n[SCRAPE] Starting live scrape for {competition}...")
    scrape_start = time.time()

    service = get_scrape_service()

    # Map competition to sport
    competition_to_sport = {
        "epl": "soccer",
        "laliga": "soccer",
        "bundesliga": "soccer",
        "seriea": "soccer",
        "ligue1": "soccer",
        "aleague": "soccer",
        "ucl": "soccer",
        "mls": "soccer",
        "nba": "basketball",
        "nbl": "basketball",
        "nhl": "ice_hockey",
        "afl": "afl",
        "nrl": "nrl",
        "boxing": "boxing",
    }

    sport = competition_to_sport.get(competition, "soccer")

    active_configs = service.get_active_bookmakers_from_db()
    active_by_code = {cfg["code"]: cfg for cfg in active_configs}

    if bookmaker:
        target_codes = {bookmaker}
        if config.reference_bookmaker not in target_codes:
            target_codes.add(config.reference_bookmaker)
    else:
        target_codes = set(active_by_code.keys())

    target_configs = [active_by_code[code] for code in target_codes if code in active_by_code]
    if bookmaker and bookmaker not in active_by_code:
        raise ValueError(f"Bookmaker not active or missing scraper: {bookmaker}")
    if config.reference_bookmaker not in active_by_code:
        logging.warning(f"Reference bookmaker not active: {config.reference_bookmaker}")

    scrapers = {}
    for cfg in target_configs:
        scraping_config = cfg.get("scraping_config", {})
        scraping_config["base_url"] = cfg.get("base_url")
        scraping_config["website_url"] = cfg.get("website_url")
        scraper = service.get_scraper_for_bookmaker(cfg["code"], scraping_config)
        if scraper:
            scrapers[cfg["code"]] = scraper
        else:
            logging.warning(f"[{cfg['code']}] Scraper not available; skipping")

    if not scrapers:
        raise ValueError("No scrapers available for requested bookmakers")

    concurrency = int(os.getenv("VALIDATION_SCRAPE_CONCURRENCY", "4"))
    semaphore = asyncio.Semaphore(concurrency)
    scrape_results = {}

    async def scrape_one(code, scraper):
        async with semaphore:
            logging.info(f"[SCRAPE] {code} starting")
            try:
                result = await scraper.scrape_all_sports_parallel(sports=[sport])
            except Exception as exc:
                logging.exception(f"[SCRAPE] {code} failed: {exc}")
                return None

            if result.status in (ScraperStatus.SUCCESS, ScraperStatus.PARTIAL):
                scrape_session_id = f"validation_{code}_{datetime.now(timezone.utc).isoformat()}"
                save_scrape_result_to_db(result, scrape_session_id)
                scrape_results[code] = result
            else:
                logging.warning(f"[SCRAPE] {code} returned status {result.status}")
            return result

    tasks = [scrape_one(code, scraper) for code, scraper in scrapers.items()]
    await asyncio.gather(*tasks)

    scrape_duration = time.time() - scrape_start
    print(f"[SCRAPE] Completed in {scrape_duration:.2f}s")

    print("[VALIDATE] Validating scraped data (full pipeline)...")

    pipeline = ValidationPipeline(config)
    return pipeline.validate_scrape_results(
        scrape_results=scrape_results,
        competition=competition,
    )


def validate_from_database(
    competition: str,
    bookmaker: str = None,
    config: ValidationConfig = None,
):
    """
    Validate data already in database.

    Args:
        competition: Competition to validate
        bookmaker: Optional specific bookmaker
        config: Validation config

    Returns:
        Validation result
    """
    pipeline = ValidationPipeline(config)
    return pipeline.validate_from_database(
        competition=competition,
        bookmaker_codes=[bookmaker] if bookmaker else None,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Validate scraper data quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --competition laliga
  %(prog)s --competition laliga --bookmaker mintbet
  %(prog)s --competition laliga --format json
  %(prog)s --competition laliga --scrape
  %(prog)s --list-competitions
        """
    )

    parser.add_argument(
        "--competition", "-c",
        help="Competition to validate (e.g., laliga, epl, nba)",
    )
    parser.add_argument(
        "--bookmaker", "-b",
        help="Specific bookmaker to validate (default: all)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["terminal", "json"],
        default="terminal",
        help="Output format (default: terminal)",
    )
    parser.add_argument(
        "--scrape", "-s",
        action="store_true",
        help="Scrape live data before validation",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Validate from database (no scraping)",
    )
    parser.add_argument(
        "--reference",
        default="ladbrokes",
        help="Reference bookmaker (default: ladbrokes)",
    )
    parser.add_argument(
        "--consensus",
        action="store_true",
        help="Use consensus median instead of single reference",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict mode (WARN becomes FAIL)",
    )
    parser.add_argument(
        "--no-anomalies",
        action="store_true",
        help="Hide individual anomaly details",
    )
    parser.add_argument(
        "--no-colors",
        action="store_true",
        help="Disable terminal colors",
    )
    parser.add_argument(
        "--list-competitions",
        action="store_true",
        help="List available competitions and exit",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Handle list competitions
    if args.list_competitions:
        list_competitions()
        return 0

    # Require competition unless listing
    if not args.competition:
        parser.error("--competition is required")

    setup_logging(args.verbose)

    # Build config
    config = ValidationConfig(
        reference_bookmaker=args.reference,
        use_consensus=args.consensus,
        strict_mode=args.strict,
    )

    # Run validation
    try:
        if args.scrape:
            result = asyncio.run(scrape_and_validate(
                competition=args.competition,
                bookmaker=args.bookmaker,
                config=config,
            ))
        else:
            result = validate_from_database(
                competition=args.competition,
                bookmaker=args.bookmaker,
                config=config,
            )

        # Print report
        if result.report:
            from validation.report_generator import ReportGenerator
            generator = ReportGenerator(use_colors=not args.no_colors)
            generator.print_report(
                result.report,
                output_format=args.format,
                show_anomalies=not args.no_anomalies,
            )

        if args.competition == "boxing":
            boxing_checks = run_boxing_evidence_checks(bookmaker=args.bookmaker)
            if boxing_checks.get("applicable"):
                logging.info(
                    "[BOXING-CHECK] coverage=%s%% (threshold=%s%%), swapped=%s (max=%s), shared=%s",
                    boxing_checks["coverage_percent"],
                    boxing_checks["coverage_threshold_percent"],
                    boxing_checks["swapped_anomaly_count"],
                    boxing_checks["max_swapped_anomalies"],
                    boxing_checks["shared_events"],
                )
                if boxing_checks.get("follow_up_required"):
                    logging.warning(
                        "[BOXING-CHECK] FOLLOW-UP REQUIRED: thresholds failed. "
                        "Investigate selection ordering consistency before fallback logic."
                    )
                    for anomaly in boxing_checks.get("swapped_anomalies", []):
                        logging.warning(
                            "[BOXING-CHECK] Swapped candidate: %s | U(home/away)=%s / %s | B(home/away)=%s / %s",
                            anomaly.get("event_name"),
                            anomaly.get("unibet_home"),
                            anomaly.get("unibet_away"),
                            anomaly.get("betfair_home"),
                            anomaly.get("betfair_away"),
                        )
            else:
                logging.info("[BOXING-CHECK] Skipped: %s", boxing_checks.get("reason", "not applicable"))

        # Return exit code based on result
        if result.has_failures:
            return 1
        elif result.has_warnings:
            return 0  # Warnings are not failures
        else:
            return 0

    except KeyboardInterrupt:
        print("\nValidation cancelled.")
        return 130
    except Exception as e:
        logging.exception(f"Validation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
