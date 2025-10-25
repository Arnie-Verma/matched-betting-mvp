"""
Scraping service for on-demand odds fetching.
Triggered by user actions (page load, refresh button).
"""
import sys
sys.path.insert(0, "apps/api/src")

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from decimal import Decimal

from scrapers.tab_scraper import TABScraper
from scrapers.betfair_scraper import BetfairScraper
from jobs.save_odds import save_scrape_result_to_db

logger = logging.getLogger(__name__)


class ScrapeService:
    """Service for managing on-demand scraping"""

    def __init__(self):
        self.scrapers = {
            "tab": TABScraper(),
            "betfair": BetfairScraper(),
            # Add more scrapers as they're implemented
            # "ladbrokes": LadbrokesScraper(),
        }

    async def scrape_bookmaker(
        self,
        bookmaker_code: str,
        sport: str = "soccer",
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scrape a single bookmaker and save to database.

        Args:
            bookmaker_code: Bookmaker to scrape (e.g., "tab")
            sport: Sport to scrape (default: "soccer" for EPL)
            limit: Optional limit on events

        Returns:
            Dict with scrape statistics
        """
        import time

        if bookmaker_code not in self.scrapers:
            logger.error(f"Scraper not found for bookmaker: {bookmaker_code}")
            return {
                "bookmaker": bookmaker_code,
                "success": False,
                "error": f"Scraper not implemented for {bookmaker_code}",
                "events_scraped": 0,
                "odds_scraped": 0
            }

        try:
            total_start = time.time()
            logger.info(f"⏱️  [{bookmaker_code}] Starting scrape: {sport}")

            # Run scraper
            scrape_start = time.time()
            scraper = self.scrapers[bookmaker_code]
            result = await scraper.scrape_sport(sport, limit=limit)
            scrape_duration = time.time() - scrape_start

            logger.info(f"⏱️  [{bookmaker_code}] Scraping took {scrape_duration:.2f}s - {result.events_scraped} events, {result.odds_scraped} odds")

            # Save to database
            db_start = time.time()
            scrape_session_id = f"{bookmaker_code}_{datetime.now(timezone.utc).isoformat()}"
            save_stats = save_scrape_result_to_db(result, scrape_session_id)
            db_duration = time.time() - db_start

            total_duration = time.time() - total_start

            logger.info(f"⏱️  [{bookmaker_code}] Database save took {db_duration:.2f}s")
            logger.info(f"⏱️  [{bookmaker_code}] TOTAL: {total_duration:.2f}s (scrape: {scrape_duration:.2f}s, db: {db_duration:.2f}s)")

            return {
                "bookmaker": bookmaker_code,
                "success": result.status.value == "success",
                "events_scraped": result.events_scraped,
                "odds_scraped": result.odds_scraped,
                "events_saved": save_stats["events_saved"],
                "odds_saved": save_stats["odds_saved"],
                "errors": result.errors + ([f"{save_stats['errors']} save errors"] if save_stats["errors"] > 0 else []),
                "duration_seconds": result.duration_seconds,
                "scrape_duration_seconds": scrape_duration,
                "db_duration_seconds": db_duration,
                "total_duration_seconds": total_duration,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.exception(f"Scrape failed for {bookmaker_code}: {e}")
            return {
                "bookmaker": bookmaker_code,
                "success": False,
                "error": str(e),
                "events_scraped": 0,
                "odds_scraped": 0
            }

    async def scrape_all_active_bookmakers(
        self,
        sport: str = "soccer",
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scrape all active bookmakers in parallel.

        Args:
            sport: Sport to scrape
            limit: Optional limit on events per bookmaker

        Returns:
            Dict with aggregate statistics
        """
        import time
        parallel_start = time.time()

        logger.info(f"⏱️  [PARALLEL] Starting parallel scrape for all active bookmakers")

        # Scrape both TAB and Betfair
        active_bookmakers = ["tab", "betfair"]

        # Run scrapers in parallel
        tasks = [
            self.scrape_bookmaker(bookmaker, sport, limit)
            for bookmaker in active_bookmakers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        parallel_duration = time.time() - parallel_start
        logger.info(f"⏱️  [PARALLEL] All scrapers completed in {parallel_duration:.2f}s")

        # Aggregate statistics
        total_events = 0
        total_odds = 0
        total_saved = 0
        all_errors = []
        success_count = 0

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Scrape task failed: {result}")
                all_errors.append(str(result))
                continue

            if result.get("success"):
                success_count += 1

            total_events += result.get("events_scraped", 0)
            total_odds += result.get("odds_scraped", 0)
            total_saved += result.get("odds_saved", 0)
            all_errors.extend(result.get("errors", []))

        return {
            "success": success_count > 0,
            "bookmakers_scraped": success_count,
            "total_bookmakers": len(active_bookmakers),
            "events_scraped": total_events,
            "odds_scraped": total_odds,
            "odds_saved": total_saved,
            "errors": all_errors,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": [r for r in results if not isinstance(r, Exception)]
        }


# Singleton instance
_scrape_service = None


def get_scrape_service() -> ScrapeService:
    """Get singleton scrape service instance"""
    global _scrape_service
    if _scrape_service is None:
        _scrape_service = ScrapeService()
    return _scrape_service


async def trigger_scrape(sport: str = "soccer", limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Convenience function to trigger scraping.
    Can be called from API endpoints.

    Args:
        sport: Sport to scrape (default: soccer for EPL)
        limit: Optional limit on events

    Returns:
        Scrape statistics
    """
    service = get_scrape_service()
    return await service.scrape_all_active_bookmakers(sport, limit)
