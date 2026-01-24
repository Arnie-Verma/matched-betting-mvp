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
