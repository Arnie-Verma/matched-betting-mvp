"""
Test script for Betfair scraper.

Run from inside the mb_api container:
    docker exec -it mb_api python test_betfair_scraper.py
"""
import sys

# This file is a manual smoke-test script (see __main__). Skip under pytest so
# it doesn't run as part of the automated test suite.
if "pytest" in sys.modules:
    import pytest

    pytest.skip("Manual Betfair smoke-test script (run directly).", allow_module_level=True)

sys.path.insert(0, "apps/worker/src")

import asyncio
import logging
from scrapers.betfair_scraper import BetfairScraper

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_betfair_scraper():
    """Test Betfair scraper for EPL odds"""

    logger.info("="*60)
    logger.info("TESTING BETFAIR SCRAPER")
    logger.info("="*60)

    # Create scraper instance
    scraper = BetfairScraper()

    # Test scraping EPL (limit to 5 events for quick test)
    logger.info("\n🔍 Scraping Betfair Exchange for EPL (limit: 5 events)...")
    result = await scraper.scrape_sport(sport="soccer", limit=5)

    # Display results
    logger.info("\n" + "="*60)
    logger.info("SCRAPE RESULTS")
    logger.info("="*60)
    logger.info(f"Status: {result.status}")
    logger.info(f"Events scraped: {result.events_scraped}")
    logger.info(f"Odds scraped: {result.odds_scraped}")
    logger.info(f"Duration: {result.duration_seconds:.2f}s")
    logger.info(f"Errors: {len(result.errors)}")

    if result.errors:
        logger.warning("\n⚠️  ERRORS:")
        for error in result.errors:
            logger.warning(f"  - {error}")

    # Display event details
    if result.events:
        logger.info("\n" + "="*60)
        logger.info("EVENT DETAILS")
        logger.info("="*60)

        for i, event in enumerate(result.events, 1):
            logger.info(f"\n[{i}] {event.name}")
            logger.info(f"    Competition: {event.competition}")
            logger.info(f"    Start Time: {event.start_time}")
            logger.info(f"    Home: {event.home_team}")
            logger.info(f"    Away: {event.away_team}")
            logger.info(f"    Odds count: {len(event.odds)}")

            # Show first few odds
            for j, odds in enumerate(event.odds[:3], 1):
                logger.info(f"      [{j}] {odds.selection_name}: {odds.decimal_odds} (lay)")
                logger.info(f"          Selection key: {odds.selection_key}")
                if odds.liquidity:
                    logger.info(f"          Liquidity: ${odds.liquidity}")

    logger.info("\n" + "="*60)
    logger.info("TEST COMPLETE")
    logger.info("="*60)

    return result


if __name__ == "__main__":
    try:
        result = asyncio.run(test_betfair_scraper())

        if result.status.value == "success":
            logger.info("\n✅ Betfair scraper test PASSED")
            sys.exit(0)
        else:
            logger.error("\n❌ Betfair scraper test FAILED")
            sys.exit(1)

    except Exception as e:
        logger.exception(f"\n💥 Test crashed: {e}")
        sys.exit(1)
