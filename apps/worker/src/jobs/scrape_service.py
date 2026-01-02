"""
Scraping service for on-demand odds fetching.
Triggered by user actions (page load, refresh button).

PRODUCTION OPTIMIZATION (Phase 1):
- Parallel bookmaker scraping: All bookmakers run simultaneously
- Parallel sport scraping: Each bookmaker scrapes all sports in parallel
- Result: 96s → 10-15s for full scrape (6-8x improvement)

DYNAMIC SCRAPER REGISTRY (Phase 1.2):
- Config-driven scraper selection from database
- Platform scrapers cover multiple bookmakers (e.g., Entain covers Ladbrokes, Neds, Unibet)
- New bookmakers added by updating database config, not code

Architecture:
- scrape_all_active_bookmakers_parallel() → asyncio.gather for all bookmakers
- Each bookmaker uses scrape_all_sports_parallel() internally
- Total time = max(slowest_bookmaker) instead of sum(all_bookmakers)
"""
import sys
sys.path.insert(0, "apps/api/src")

import asyncio
import logging
import os
import time
import redis
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Type
from decimal import Decimal

from scrapers.tab_scraper import TABScraper
from scrapers.betfair_scraper import BetfairScraper
from scrapers.ladbrokes_scraper import LadbrokesScraper
from scrapers.entain_scraper import EntainScraper
from scrapers.punterstech_scraper import PunterstechScraper
from scrapers.base import BaseScraper, ScrapeResult, ScraperStatus
from jobs.save_odds import save_scrape_result_to_db
from jobs.cleanup_service import CleanupService

# Optional Sentry integration for error tracking
try:
    from api.core.monitoring import capture_exception, capture_message, add_breadcrumb, init_sentry
    # Initialize Sentry for worker process
    init_sentry()
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    def capture_exception(*args, **kwargs): pass
    def capture_message(*args, **kwargs): pass
    def add_breadcrumb(*args, **kwargs): pass

logger = logging.getLogger(__name__)


# =============================================================================
# SCRAPER REGISTRY
# =============================================================================
# Maps scraper_class (from bookmaker.scraping_config) to scraper implementation.
# Platform scrapers (like EntainScraper) can handle multiple bookmakers with
# different base_urls - just pass different config.
#
# To add a new platform:
# 1. Create the scraper class (e.g., PunterstechScraper)
# 2. Add it to SCRAPER_CLASSES below
# 3. Update bookmaker.scraping_config in database to use new scraper_class
# =============================================================================
SCRAPER_CLASSES: Dict[str, Type[BaseScraper]] = {
    "entain": EntainScraper,            # Ladbrokes, Neds
    "betfair": BetfairScraper,          # Betfair Exchange
    "tab": TABScraper,                  # TAB (needs proxy)
    "punterstech": PunterstechScraper,  # 21 bookmakers (TradieBET, MintBet, etc.)
    # Future platform scrapers:
    # "betmakers": BetMakersScraper,        # 33 bookmakers
    # "generation_web": GenerationWebScraper,  # 22 bookmakers
    # "betcloud": BetCloudScraper,          # 26 bookmakers
}


class ScrapeService:
    """
    Service for managing on-demand scraping.

    Supports two modes:
    1. Static scrapers (legacy): Hardcoded scraper instances
    2. Dynamic scrapers (new): Created from database config using SCRAPER_CLASSES registry

    Active bookmakers are determined by:
    - Database: bookmaker.is_active = True AND scraper_class in SCRAPER_CLASSES
    - Or fallback to static list if database unavailable
    """

    def __init__(self):
        # Static scrapers (legacy - kept for backwards compatibility)
        # These are used as fallback if database is unavailable
        self._static_scrapers = {
            "betfair": BetfairScraper(),
            "ladbrokes": EntainScraper("ladbrokes", "https://www.ladbrokes.com.au"),
        }

        # Cache for dynamically created scrapers
        self._dynamic_scrapers: Dict[str, BaseScraper] = {}

        self.redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        self.breaker_threshold = int(os.getenv("BOOKMAKER_BREAKER_THRESHOLD", "5"))
        self.breaker_cooldown = int(os.getenv("BOOKMAKER_BREAKER_COOLDOWN_SECONDS", "60"))
        self.bookmaker_timeout = int(os.getenv("BOOKMAKER_TIMEOUT_SECONDS", "25"))

    @property
    def scrapers(self) -> Dict[str, BaseScraper]:
        """
        Get all available scrapers (static + dynamic).

        Returns combined dict of static scrapers and any dynamically created ones.
        """
        combined = dict(self._static_scrapers)
        combined.update(self._dynamic_scrapers)
        return combined

    def get_scraper_for_bookmaker(self, bookmaker_code: str, bookmaker_config: Optional[Dict] = None) -> Optional[BaseScraper]:
        """
        Get or create a scraper for a bookmaker.

        Args:
            bookmaker_code: The bookmaker's code (e.g., 'ladbrokes', 'neds')
            bookmaker_config: Optional config dict with scraper_class, base_url, etc.
                             If None, uses static scrapers.

        Returns:
            BaseScraper instance or None if not available
        """
        # Check if already created
        if bookmaker_code in self._dynamic_scrapers:
            return self._dynamic_scrapers[bookmaker_code]

        if bookmaker_code in self._static_scrapers:
            return self._static_scrapers[bookmaker_code]

        # Try to create dynamically from config
        if bookmaker_config:
            scraper_class_name = bookmaker_config.get("scraper_class")
            if scraper_class_name and scraper_class_name in SCRAPER_CLASSES:
                ScraperClass = SCRAPER_CLASSES[scraper_class_name]

                # Get base_url from config
                base_url = bookmaker_config.get("base_url") or bookmaker_config.get("website_url")

                if base_url:
                    try:
                        # Create scraper instance
                        scraper = ScraperClass(
                            bookmaker_code=bookmaker_code,
                            base_url=base_url,
                            config=bookmaker_config
                        )
                        self._dynamic_scrapers[bookmaker_code] = scraper
                        logger.info(f"[{bookmaker_code}] Created dynamic scraper ({scraper_class_name})")
                        return scraper
                    except Exception as e:
                        logger.error(f"[{bookmaker_code}] Failed to create scraper: {e}")
                        return None

        return None

    def get_active_bookmakers_from_db(self) -> List[Dict[str, Any]]:
        """
        Get list of active bookmakers from database.

        Returns list of dicts with bookmaker config (code, base_url, scraping_config).
        Falls back to static list if database unavailable.
        """
        try:
            from api.core.database import SessionLocal
            from api.models import Bookmaker

            db = SessionLocal()
            try:
                active = db.query(Bookmaker).filter(
                    Bookmaker.is_active == True
                ).all()

                result = []
                for bm in active:
                    config = bm.scraping_config or {}
                    scraper_class = config.get("scraper_class")

                    # Only include if we have a scraper for this platform
                    if scraper_class in SCRAPER_CLASSES:
                        result.append({
                            "code": bm.code,
                            "name": bm.name,
                            "base_url": bm.base_url or bm.website_url,
                            "website_url": bm.website_url,
                            "scraping_config": config
                        })
                    else:
                        logger.debug(f"[{bm.code}] Skipped: scraper_class '{scraper_class}' not in registry")

                logger.info(f"Found {len(result)} active bookmakers with available scrapers")
                return result

            finally:
                db.close()

        except Exception as e:
            logger.warning(f"Could not load bookmakers from DB, using static list: {e}")
            # Fallback to static scrapers
            return [
                {"code": "betfair", "base_url": "https://www.betfair.com.au", "scraping_config": {"scraper_class": "betfair"}},
                {"code": "ladbrokes", "base_url": "https://www.ladbrokes.com.au", "scraping_config": {"scraper_class": "entain"}},
            ]

    def _get_breaker_state(self, bookmaker_code: str) -> Dict[str, Any]:
        """Get circuit breaker state from Redis."""
        breaker_key = f"breaker:{bookmaker_code}"
        data = self.redis_client.get(breaker_key)
        if not data:
            return {"state": "closed", "failures": 0, "opened_at": None}
        return json.loads(data)

    def _set_breaker_state(self, bookmaker_code: str, state: str, failures: int = 0):
        """Update circuit breaker state in Redis."""
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

    def _run_post_scrape_cleanup(self) -> Dict[str, Any]:
        """
        Run lightweight cleanup after each scrape.

        Phase 3 optimization: Keep database small by removing stale data immediately.
        Only cleans non-current odds (fast, safe operation).
        Past events cleanup runs less frequently via scheduled job.

        Returns:
            Dict with cleanup statistics
        """
        from api.core.database import SessionLocal

        db = SessionLocal()
        try:
            service = CleanupService(db)

            # Quick cleanup: just remove non-current odds
            # This is fast and safe - these odds are already superseded
            result = service.cleanup_non_current_odds()

            return {
                "odds_deleted": result.get("deleted", 0),
                "duration_seconds": result.get("duration_seconds", 0)
            }
        finally:
            db.close()

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
            # Report to Sentry with context
            capture_exception(e, {
                "bookmaker": bookmaker_code,
                "sport": sport,
                "operation": "scrape_bookmaker"
            })
            return {
                "bookmaker": bookmaker_code,
                "success": False,
                "error": str(e),
                "events_scraped": 0,
                "odds_scraped": 0
            }

    async def scrape_bookmaker_all_sports(
        self,
        bookmaker_code: str,
        sports: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Scrape a single bookmaker for ALL sports using parallel sport scraping.

        Uses the new scrape_all_sports_parallel() method for 6x speedup.

        Args:
            bookmaker_code: Bookmaker to scrape
            sports: List of sports (defaults to all 6)
            limit: Optional limit per sport

        Returns:
            Dict with scrape statistics
        """
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
            scraper = self.scrapers[bookmaker_code]

            logger.info(f"⏱️  [{bookmaker_code}] Starting PARALLEL sport scrape")

            # Use the new parallel sports method WITH TIMEOUT
            try:
                # For sequential sports (batch_size=1), need longer timeout:
                # 6 sports × ~10s each = ~60s per bookmaker
                all_sports_timeout = max(self.bookmaker_timeout * 6, 120)
                result = await asyncio.wait_for(
                    scraper.scrape_all_sports_parallel(sports=sports, limit=limit),
                    timeout=all_sports_timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"[{bookmaker_code}] Parallel scrape timed out after {all_sports_timeout}s")
                self._record_failure(bookmaker_code)
                return {
                    "bookmaker": bookmaker_code,
                    "success": False,
                    "error": f"Timeout after {all_sports_timeout}s",
                    "events_scraped": 0,
                    "odds_scraped": 0,
                    "timeout": True
                }

            scrape_duration = time.time() - total_start

            logger.info(
                f"⏱️  [{bookmaker_code}] PARALLEL scrape completed in {scrape_duration:.2f}s: "
                f"{result.events_scraped} events, {result.odds_scraped} odds"
            )

            # Save to database
            db_start = time.time()
            scrape_session_id = f"{bookmaker_code}_{datetime.now(timezone.utc).isoformat()}"
            save_stats = save_scrape_result_to_db(result, scrape_session_id)
            db_duration = time.time() - db_start

            total_duration = time.time() - total_start

            logger.info(f"⏱️  [{bookmaker_code}] Database save took {db_duration:.2f}s")
            logger.info(
                f"⏱️  [{bookmaker_code}] TOTAL: {total_duration:.2f}s "
                f"(scrape: {scrape_duration:.2f}s, db: {db_duration:.2f}s)"
            )

            # Record success - reset circuit breaker
            self._record_success(bookmaker_code)

            return {
                "bookmaker": bookmaker_code,
                "success": result.status in (ScraperStatus.SUCCESS, ScraperStatus.PARTIAL),
                "events_scraped": result.events_scraped,
                "odds_scraped": result.odds_scraped,
                "events_saved": save_stats["events_saved"],
                "odds_saved": save_stats["odds_saved"],
                "errors": result.errors + ([f"{save_stats['errors']} save errors"] if save_stats["errors"] > 0 else []),
                "duration_seconds": total_duration,
                "scrape_duration_seconds": scrape_duration,
                "db_duration_seconds": db_duration,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.exception(f"Parallel scrape failed for {bookmaker_code}: {e}")
            self._record_failure(bookmaker_code)
            # Report to Sentry with context
            capture_exception(e, {
                "bookmaker": bookmaker_code,
                "operation": "scrape_bookmaker_all_sports"
            })
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
        Scrape all active bookmakers in PARALLEL for all sports.

        PRODUCTION OPTIMIZED (Phase 1):
        - All bookmakers run simultaneously via asyncio.gather
        - Each bookmaker scrapes all sports in parallel internally
        - Total time = max(slowest_bookmaker) ≈ 10-15s instead of 96s+

        DYNAMIC REGISTRY (Phase 1.2):
        - Loads active bookmakers from database
        - Creates scrapers dynamically based on scraping_config.scraper_class
        - Falls back to static list if database unavailable

        Args:
            sport: Sport to scrape ("all" for all sports, or specific sport code)
            limit: Optional limit on events per bookmaker per sport

        Returns:
            Dict with aggregate statistics
        """
        parallel_start = time.time()

        # All 6 sports we support
        ALL_SPORTS = ["soccer", "afl", "nrl", "basketball", "ice_hockey", "boxing"]

        # Determine which sports to scrape
        sports_to_scrape = ALL_SPORTS if sport == "all" else [sport]

        # Get active bookmakers from database (with fallback)
        active_bookmaker_configs = self.get_active_bookmakers_from_db()
        active_bookmaker_codes = [bm["code"] for bm in active_bookmaker_configs]

        # Create scrapers for each active bookmaker
        for bm_config in active_bookmaker_configs:
            code = bm_config["code"]
            scraping_config = bm_config.get("scraping_config", {})
            scraping_config["base_url"] = bm_config.get("base_url")
            scraping_config["website_url"] = bm_config.get("website_url")
            self.get_scraper_for_bookmaker(code, scraping_config)

        logger.info(
            f"[PARALLEL] Starting scrape: {len(active_bookmaker_codes)} bookmakers x {len(sports_to_scrape)} sports"
        )
        logger.info(f"[PARALLEL] Active bookmakers: {', '.join(active_bookmaker_codes)}")

        # PARALLEL EXECUTION: All bookmakers run simultaneously
        tasks = [
            self.scrape_bookmaker_all_sports(
                bookmaker_code=bookmaker,
                sports=sports_to_scrape,
                limit=limit
            )
            for bookmaker in active_bookmaker_codes
        ]

        # Wait for all bookmakers to complete (with exception handling)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        parallel_duration = time.time() - parallel_start
        logger.info(
            f"[PARALLEL] All bookmakers completed in {parallel_duration:.2f}s"
        )

        # Aggregate statistics
        total_events = 0
        total_odds = 0
        total_saved = 0
        all_errors = []
        success_count = 0
        bookmaker_results = []

        for bookmaker, result in zip(active_bookmaker_codes, results):
            if isinstance(result, Exception):
                logger.error(f"[{bookmaker}] Scrape task failed with exception: {result}")
                all_errors.append(f"{bookmaker}: {str(result)}")
                bookmaker_results.append({
                    "bookmaker": bookmaker,
                    "success": False,
                    "error": str(result)
                })
                continue

            bookmaker_results.append(result)

            if result.get("success"):
                success_count += 1

            total_events += result.get("events_scraped", 0)
            total_odds += result.get("odds_scraped", 0)
            total_saved += result.get("odds_saved", 0)

            # Collect errors
            result_errors = result.get("errors", [])
            if result_errors:
                all_errors.extend([f"{bookmaker}: {e}" for e in result_errors])

        # Run cleanup after successful scrape (Phase 3 optimization)
        cleanup_result = None
        if success_count > 0:
            try:
                cleanup_start = time.time()
                cleanup_result = self._run_post_scrape_cleanup()
                cleanup_duration = time.time() - cleanup_start
                logger.info(f"⏱️  [CLEANUP] Post-scrape cleanup took {cleanup_duration:.2f}s")
            except Exception as e:
                logger.error(f"[CLEANUP] Post-scrape cleanup failed: {e}")
                cleanup_result = {"error": str(e)}

        return {
            "success": success_count > 0,
            "bookmakers_scraped": success_count,
            "total_bookmakers": len(active_bookmaker_codes),
            "events_scraped": total_events,
            "odds_scraped": total_odds,
            "odds_saved": total_saved,
            "errors": all_errors,
            "duration_seconds": parallel_duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": bookmaker_results,
            "parallel": True,  # Flag indicating parallel execution
            "cleanup": cleanup_result  # Phase 3: cleanup stats
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
