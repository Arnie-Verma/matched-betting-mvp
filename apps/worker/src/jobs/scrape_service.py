"""
Scraping service for on-demand odds fetching.
Triggered by user actions (page load, refresh button).
"""
import sys
sys.path.insert(0, "apps/api/src")

import asyncio
import logging
import os
import redis
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from decimal import Decimal

from scrapers.tab_scraper import TABScraper
from scrapers.betfair_scraper import BetfairScraper
from scrapers.ladbrokes_scraper import LadbrokesScraper
from jobs.save_odds import save_scrape_result_to_db

logger = logging.getLogger(__name__)


class ScrapeService:
    """Service for managing on-demand scraping"""

    def __init__(self):
        self.scrapers = {
            # "tab": TABScraper(),  # Disabled - needs rotating proxy for production
            "betfair": BetfairScraper(),
            "ladbrokes": LadbrokesScraper(),
            # Add more scrapers as they're implemented
            # "neds": NedsScraper(),
        }
        self.redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        self.breaker_threshold = int(os.getenv("BOOKMAKER_BREAKER_THRESHOLD", "5"))
        self.breaker_cooldown = int(os.getenv("BOOKMAKER_BREAKER_COOLDOWN_SECONDS", "60"))
        self.bookmaker_timeout = int(os.getenv("BOOKMAKER_TIMEOUT_SECONDS", "25"))

    def _get_breaker_state(self, bookmaker_code: str) -> Dict[str, Any]:
        """Get circuit breaker state from Redis."""
        breaker_key = f"breaker:{bookmaker_code}"
        data = self.redis_client.get(breaker_key)
        if not data:
            return {"state": "closed", "failures": 0, "opened_at": None}
        import json
        return json.loads(data)

    def _set_breaker_state(self, bookmaker_code: str, state: str, failures: int = 0):
        """Update circuit breaker state in Redis."""
        import json
        breaker_key = f"breaker:{bookmaker_code}"
        breaker_data = {
            "state": state,
            "failures": failures,
            "opened_at": datetime.now(timezone.utc).isoformat() if state == "open" else None,
        }
        ttl = self.breaker_cooldown + 60  # Extra buffer for cooldown
        self.redis_client.setex(breaker_key, ttl, json.dumps(breaker_data))

    def _record_success(self, bookmaker_code: str):
        """Record successful scrape - reset circuit breaker."""
        self._set_breaker_state(bookmaker_code, "closed", 0)

    def _record_failure(self, bookmaker_code: str):
        """Record failed scrape - increment failure counter and open breaker if threshold reached."""
        breaker_state = self._get_breaker_state(bookmaker_code)
        failures = breaker_state.get("failures", 0) + 1

        if failures >= self.breaker_threshold:
            logger.warning(
                f"[{bookmaker_code}] Circuit breaker OPEN after {failures} failures "
                f"(threshold: {self.breaker_threshold}). Cooldown: {self.breaker_cooldown}s"
            )
            self._set_breaker_state(bookmaker_code, "open", failures)
        else:
            logger.info(f"[{bookmaker_code}] Failure {failures}/{self.breaker_threshold}")
            self._set_breaker_state(bookmaker_code, "closed", failures)

    def _check_breaker(self, bookmaker_code: str) -> bool:
        """
        Check if circuit breaker allows scraping.

        Returns True if scraping allowed, False if breaker is open.
        Implements half-open state after cooldown period.
        """
        breaker_state = self._get_breaker_state(bookmaker_code)
        state = breaker_state.get("state", "closed")

        if state == "closed":
            return True

        if state == "open":
            opened_at_str = breaker_state.get("opened_at")
            if not opened_at_str:
                # No timestamp, allow retry
                return True

            from datetime import datetime
            opened_at = datetime.fromisoformat(opened_at_str)
            cooldown_elapsed = (datetime.now(timezone.utc) - opened_at).total_seconds()

            if cooldown_elapsed >= self.breaker_cooldown:
                # Enter half-open state - allow one retry
                logger.info(f"[{bookmaker_code}] Circuit breaker entering HALF-OPEN state (cooldown elapsed)")
                self._set_breaker_state(bookmaker_code, "half-open", breaker_state.get("failures", 0))
                return True
            else:
                logger.warning(
                    f"[{bookmaker_code}] Circuit breaker OPEN - skipping scrape "
                    f"(cooldown: {int(self.breaker_cooldown - cooldown_elapsed)}s remaining)"
                )
                return False

        if state == "half-open":
            # Allow one retry in half-open state
            return True

        return True

    async def scrape_bookmaker(
        self,
        bookmaker_code: str,
        sport: str = "soccer",
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scrape a single bookmaker and save to database.

        Implements:
        - Circuit breaker pattern (skip after N failures, retry after cooldown)
        - Timeout protection (asyncio.wait_for)

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

        # Circuit breaker check
        if not self._check_breaker(bookmaker_code):
            return {
                "bookmaker": bookmaker_code,
                "success": False,
                "error": "Circuit breaker OPEN - skipping scrape",
                "events_scraped": 0,
                "odds_scraped": 0,
                "breaker_state": "open"
            }

        try:
            total_start = time.time()
            logger.info(f"⏱️  [{bookmaker_code}] Starting scrape: {sport}")

            # Run scraper WITH TIMEOUT
            scrape_start = time.time()
            scraper = self.scrapers[bookmaker_code]

            try:
                result = await asyncio.wait_for(
                    scraper.scrape_sport(sport, limit=limit),
                    timeout=self.bookmaker_timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"[{bookmaker_code}] Scrape timed out after {self.bookmaker_timeout}s")
                self._record_failure(bookmaker_code)
                return {
                    "bookmaker": bookmaker_code,
                    "success": False,
                    "error": f"Timeout after {self.bookmaker_timeout}s",
                    "events_scraped": 0,
                    "odds_scraped": 0,
                    "timeout": True
                }

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

            # Record success - reset circuit breaker
            self._record_success(bookmaker_code)

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
            # Record failure - increment circuit breaker counter
            self._record_failure(bookmaker_code)
            return {
                "bookmaker": bookmaker_code,
                "success": False,
                "error": str(e),
                "events_scraped": 0,
                "odds_scraped": 0
            }

    async def scrape_all_active_bookmakers(
        self,
        sport: str = "all",
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scrape all active bookmakers in parallel for all sports.

        Args:
            sport: Sport to scrape ("all" for all sports, or specific sport code)
            limit: Optional limit on events per bookmaker per sport

        Returns:
            Dict with aggregate statistics
        """
        import time
        parallel_start = time.time()

        # All 6 sports we support
        ALL_SPORTS = ["soccer", "afl", "nrl", "basketball", "ice_hockey", "boxing"]

        # Determine which sports to scrape
        sports_to_scrape = ALL_SPORTS if sport == "all" else [sport]

        logger.info(f"⏱️  [PARALLEL] Starting parallel scrape for all active bookmakers across {len(sports_to_scrape)} sports")

        # Scrape Betfair and Ladbrokes (TAB disabled - needs rotating proxy)
        active_bookmakers = ["betfair", "ladbrokes"]

        # Run scrapers in parallel - all bookmakers x all sports
        # NOTE: Betfair/Ladbrokes share browser instances with captured_data
        # Running them in parallel causes race conditions. Run sequentially per bookmaker.
        all_results = []

        for bookmaker in active_bookmakers:
            # Run each bookmaker's sports sequentially to avoid race conditions
            # (captured_data is shared within a bookmaker's scraper instance)
            for s in sports_to_scrape:
                result = await self.scrape_bookmaker(bookmaker, s, limit)
                all_results.append(result)

        results = all_results

        parallel_duration = time.time() - parallel_start
        num_tasks = len(active_bookmakers) * len(sports_to_scrape)
        logger.info(f"⏱️  [SEQUENTIAL] All scrapers completed in {parallel_duration:.2f}s ({num_tasks} tasks)")

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
