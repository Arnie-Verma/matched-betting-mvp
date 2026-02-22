"""
Scraping service for on-demand odds fetching.
Triggered by user actions (page load, refresh button).

Key runtime behavior:
- Dynamic active bookmaker selection from DB + freeze policy.
- Bounded bookmaker scheduler with global and per-platform caps.
- Per-bookmaker isolation: one scrape failure does not cancel others.
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
from typing import List, Dict, Any, Optional, Type, Tuple
from decimal import Decimal

from scrapers.tab_scraper import TABScraper
from scrapers.betfair_scraper import BetfairScraper
from scrapers.ladbrokes_scraper import LadbrokesScraper
from scrapers.entain_scraper import EntainScraper
from scrapers.punterstech_scraper import PunterstechScraper
from scrapers.kindred_scraper import KindredScraper
from scrapers.base import BaseScraper, ScrapeResult, ScraperStatus
from jobs.save_odds import save_scrape_result_to_db
from jobs.cleanup_service import CleanupService
from api.services.observability_service import emit_observability_event
from api.services.rollout_control_service import RolloutControlService

# Optional validation integration
try:
    from validation.pipeline import ValidationPipeline
    from validation.config import ValidationConfig
    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False
    ValidationPipeline = None
    ValidationConfig = None

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
    "kindred": KindredScraper,          # Unibet (AU)
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

    DEFAULT_PLATFORM_CONCURRENCY_CAPS: Dict[str, int] = {
        # Punterstech has many active skins in Phase A; default cap=2 prevents
        # serialized fan-out while keeping bounded execution and isolation.
        "punterstech": 2,
    }

    def __init__(self):
        # Static scrapers (legacy - kept for backwards compatibility)
        # These are used as fallback if database is unavailable
        self._static_scrapers = {
            "betfair": BetfairScraper(),
            "ladbrokes": EntainScraper("ladbrokes", "https://www.ladbrokes.com.au"),
        }

        # Cache for dynamically created scrapers
        self._dynamic_scrapers: Dict[str, BaseScraper] = {}
        self._bookmaker_platform_codes: Dict[str, str] = {}

        self.redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        self.breaker_threshold = int(os.getenv("BOOKMAKER_BREAKER_THRESHOLD", "5"))
        self.breaker_cooldown = int(os.getenv("BOOKMAKER_BREAKER_COOLDOWN_SECONDS", "60"))
        self.bookmaker_timeout = int(os.getenv("BOOKMAKER_TIMEOUT_SECONDS", "25"))
        self.global_scrape_concurrency_cap = self._read_positive_int(
            "SCRAPE_GLOBAL_CONCURRENCY_CAP",
            fallback=self._read_positive_int("BOOKMAKER_CONCURRENCY_CAP", fallback=4),
        )
        self.platform_default_concurrency_cap = self._read_positive_int(
            "SCRAPE_PLATFORM_CONCURRENCY_DEFAULT_CAP",
            fallback=1,
        )
        self.platform_concurrency_caps = {
            **self.DEFAULT_PLATFORM_CONCURRENCY_CAPS,
            **self._load_platform_concurrency_caps(
            os.getenv("SCRAPE_PLATFORM_CONCURRENCY_CAPS_JSON", "")
            ),
        }

        # Validation settings
        self.validation_enabled = os.getenv("VALIDATION_ENABLED", "false").lower() == "true"
        self._validation_pipeline = None

    @staticmethod
    def _percentile(values: List[float], percentile: float) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return float(values[0])
        ordered = sorted(values)
        percentile = min(max(percentile, 0.0), 1.0)
        position = (len(ordered) - 1) * percentile
        lower_index = int(position)
        upper_index = min(lower_index + 1, len(ordered) - 1)
        weight = position - lower_index
        return float(ordered[lower_index] * (1.0 - weight) + ordered[upper_index] * weight)

    @staticmethod
    def _read_positive_int(env_name: str, fallback: int) -> int:
        raw_value = os.getenv(env_name)
        if raw_value is None or raw_value == "":
            return max(1, int(fallback))
        try:
            return max(1, int(raw_value))
        except ValueError:
            logger.warning(f"Invalid {env_name}={raw_value!r}; using fallback={fallback}")
            return max(1, int(fallback))

    @staticmethod
    def _load_platform_concurrency_caps(raw_caps: str) -> Dict[str, int]:
        """
        Parse platform cap overrides from JSON object string.
        Example: {"entain": 2, "punterstech": 3}
        """
        if not raw_caps:
            return {}

        try:
            parsed = json.loads(raw_caps)
        except json.JSONDecodeError:
            logger.warning("Invalid SCRAPE_PLATFORM_CONCURRENCY_CAPS_JSON; ignoring overrides")
            return {}

        if not isinstance(parsed, dict):
            logger.warning("SCRAPE_PLATFORM_CONCURRENCY_CAPS_JSON must be an object; ignoring overrides")
            return {}

        normalized: Dict[str, int] = {}
        for platform, cap in parsed.items():
            if not isinstance(platform, str) or not platform.strip():
                continue
            try:
                normalized[platform.strip()] = max(1, int(cap))
            except (TypeError, ValueError):
                logger.warning(f"Ignoring invalid cap for platform {platform!r}: {cap!r}")
                continue
        return normalized

    def _resolve_platform_cap(self, platform: str) -> int:
        return max(
            1,
            int(
                self.platform_concurrency_caps.get(
                    platform,
                    self.platform_default_concurrency_cap,
                )
            ),
        )

    @staticmethod
    def _extract_platform_code(bookmaker_config: Dict[str, Any]) -> str:
        scraping_config = bookmaker_config.get("scraping_config") or {}
        if isinstance(scraping_config, dict):
            platform = scraping_config.get("scraper_class")
            if isinstance(platform, str) and platform.strip():
                return platform.strip()
        return "unknown"

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

    def get_active_bookmakers_from_db(
        self,
        *,
        requested_sport: Optional[str] = None,
        requested_competition: Optional[str] = None,
        requested_bookmakers: Optional[List[str]] = None,
        include_decisions: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get list of active bookmakers from database.

        Returns list of dicts with bookmaker config (code, base_url, scraping_config).
        Applies onboarding freeze policy (for example Unibet during Phase A).
        Falls back to static list if database unavailable.
        """
        try:
            from api.core.database import SessionLocal
            from api.models import Bookmaker

            db = SessionLocal()
            try:
                active = db.query(Bookmaker).all()

                result = []
                for bm in active:
                    config = bm.scraping_config or {}
                    scraper_class = config.get("scraper_class")

                    # Only include if we have a scraper for this platform
                    if scraper_class in SCRAPER_CLASSES:
                        self._bookmaker_platform_codes[bm.code] = str(scraper_class)
                        result.append({
                            "code": bm.code,
                            "name": bm.name,
                            "base_url": bm.base_url or bm.website_url,
                            "website_url": bm.website_url,
                            "scraping_config": config
                        })
                    else:
                        logger.debug(f"[{bm.code}] Skipped: scraper_class '{scraper_class}' not in registry")

                selection = RolloutControlService.resolve_runnable_bookmakers(
                    db,
                    bookmaker_rows=active,
                    requested_sport=requested_sport,
                    requested_competition=requested_competition,
                    requested_bookmakers=requested_bookmakers,
                )
                result_codes = {_normalize_code(cfg.get("code")) for cfg in selection.runnable_configs}
                runnable = [cfg for cfg in result if _normalize_code(cfg.get("code")) in result_codes]

                logger.info(
                    f"Found {len(runnable)} runnable bookmakers "
                    f"(requested_sport={requested_sport}, requested_competition={requested_competition})"
                )
                if include_decisions:
                    return [
                        {
                            **cfg,
                            "selection_decision": next(
                                (d for d in selection.decisions if d.get("bookmaker_code") == _normalize_code(cfg.get("code"))),
                                None,
                            ),
                        }
                        for cfg in runnable
                    ]
                return runnable

            finally:
                db.close()

        except Exception as e:
            logger.warning(f"Could not load bookmakers from DB, using static list: {e}")
            # Fallback to static scrapers
            self._bookmaker_platform_codes["betfair"] = "betfair"
            self._bookmaker_platform_codes["ladbrokes"] = "entain"
            fallback = [
                {"code": "betfair", "base_url": "https://www.betfair.com.au", "scraping_config": {"scraper_class": "betfair"}},
                {"code": "ladbrokes", "base_url": "https://www.ladbrokes.com.au", "scraping_config": {"scraper_class": "entain"}},
            ]
            requested = {_normalize_code(code) for code in (requested_bookmakers or []) if _normalize_code(code)}
            if requested:
                return [cfg for cfg in fallback if _normalize_code(cfg.get("code")) in requested]
            return fallback

    def _get_breaker_state(self, bookmaker_code: str) -> Dict[str, Any]:
        """Get circuit breaker state from Redis."""
        breaker_key = f"breaker:{bookmaker_code}"
        data = self.redis_client.get(breaker_key)
        if not data:
            return {"state": "closed", "failures": 0, "opened_at": None}
        return json.loads(data)

    def _set_breaker_state(self, bookmaker_code: str, state: str, failures: int = 0):
        """Update circuit breaker state in Redis."""
        previous_state = self._get_breaker_state(bookmaker_code).get("state", "closed")
        breaker_key = f"breaker:{bookmaker_code}"
        breaker_data = {
            "state": state,
            "failures": failures,
            "opened_at": datetime.now(timezone.utc).isoformat() if state == "open" else None,
        }
        ttl = self.breaker_cooldown + 60  # Extra buffer for cooldown
        self.redis_client.setex(breaker_key, ttl, json.dumps(breaker_data))

        if previous_state != state:
            emit_observability_event(
                category="scrape_reliability",
                metric_name="breaker_transition",
                source="worker",
                bookmaker_code=bookmaker_code,
                platform_code=self._bookmaker_platform_codes.get(bookmaker_code),
                action_type="breaker_state_transition",
                payload={
                    "from_state": previous_state,
                    "to_state": state,
                    "failures": int(failures),
                },
            )

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

    def _run_post_scrape_validation(self, competition: str = "laliga") -> Optional[Dict[str, Any]]:
        """
        Run validation after scrape (non-blocking).

        Validates scraped data against reference bookmaker.
        Returns validation summary, never blocks or raises.

        Args:
            competition: Competition to validate

        Returns:
            Validation summary dict, or None if validation unavailable/failed
        """
        if not VALIDATION_AVAILABLE:
            logger.debug("[VALIDATION] Validation module not available")
            return None

        if not self.validation_enabled:
            logger.debug("[VALIDATION] Validation disabled")
            return None

        try:
            # Lazy init validation pipeline
            if self._validation_pipeline is None:
                self._validation_pipeline = ValidationPipeline(ValidationConfig())

            # Run validation from database (non-blocking)
            result = self._validation_pipeline.validate_from_database(
                competition=competition,
            )

            # Log summary
            if result.report:
                from validation.report_generator import ReportGenerator
                generator = ReportGenerator(use_colors=False)
                logger.info(generator.generate_summary_line(result.report))

            # Alert on failures (non-blocking)
            if result.has_failures:
                self._send_validation_alert(result)

            return {
                "competition": competition,
                "has_failures": result.has_failures,
                "has_warnings": result.has_warnings,
                "failed_bookmakers": result.failed_bookmakers,
                "warned_bookmakers": result.warned_bookmakers,
                "duration_seconds": result.duration_seconds,
            }

        except Exception as e:
            logger.error(f"[VALIDATION] Validation failed (non-blocking): {e}")
            capture_exception(e, {"operation": "post_scrape_validation"})
            return {"error": str(e)}

    def _send_validation_alert(self, result) -> None:
        """
        Send alert for validation failures (non-blocking).

        Integrates with Sentry for error tracking.

        Args:
            result: PipelineResult from validation
        """
        if SENTRY_AVAILABLE:
            capture_message(
                f"Scraper validation failed: {result.failed_bookmakers}",
                level="warning",
                extras={
                    "competition": result.competition,
                    "failed_bookmakers": result.failed_bookmakers,
                    "warned_bookmakers": result.warned_bookmakers,
                }
            )

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
                # 6 sports × ~15s each = ~90s per bookmaker, plus buffer for slow connections
                # Increased from 120s to 180s to reduce timeout errors in parallel scrapes
                all_sports_timeout = max(self.bookmaker_timeout * 6, 180)
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

    async def _run_bounded_bookmaker_schedule(
        self,
        bookmaker_configs: List[Dict[str, Any]],
        sports_to_scrape: List[str],
        limit: Optional[int],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Run bookmaker scrape tasks with bounded global + per-platform concurrency.

        Isolation policy: each bookmaker is executed independently and converted to
        a non-fatal error result if it raises.
        """
        if not bookmaker_configs:
            return [], {
                "global_cap": self.global_scrape_concurrency_cap,
                "platform_caps": {},
                "observed_max_in_flight_global": 0,
                "observed_max_in_flight_by_platform": {},
                "total_scheduled": 0,
            }

        global_cap = min(self.global_scrape_concurrency_cap, len(bookmaker_configs))
        platforms = [self._extract_platform_code(cfg) for cfg in bookmaker_configs]
        platform_caps = {
            platform: self._resolve_platform_cap(platform)
            for platform in sorted(set(platforms))
        }
        platform_semaphores = {
            platform: asyncio.Semaphore(cap)
            for platform, cap in platform_caps.items()
        }

        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        for cfg in bookmaker_configs:
            queue.put_nowait(cfg)

        current_global = 0
        max_global = 0
        current_platform: Dict[str, int] = {platform: 0 for platform in platform_caps}
        max_platform: Dict[str, int] = {platform: 0 for platform in platform_caps}
        counters_lock = asyncio.Lock()
        results_by_bookmaker: Dict[str, Dict[str, Any]] = {}

        async def _mark_start(platform: str) -> None:
            nonlocal current_global, max_global
            async with counters_lock:
                current_global += 1
                max_global = max(max_global, current_global)
                current_platform[platform] = current_platform.get(platform, 0) + 1
                max_platform[platform] = max(
                    max_platform.get(platform, 0),
                    current_platform[platform],
                )

        async def _mark_finish(platform: str) -> None:
            nonlocal current_global
            async with counters_lock:
                current_global = max(0, current_global - 1)
                current_platform[platform] = max(0, current_platform.get(platform, 0) - 1)

        async def _worker() -> None:
            while True:
                try:
                    bookmaker_cfg = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return

                bookmaker_code = bookmaker_cfg.get("code")
                platform = self._extract_platform_code(bookmaker_cfg)
                platform_semaphore = platform_semaphores[platform]

                await platform_semaphore.acquire()
                await _mark_start(platform)
                try:
                    result = await self.scrape_bookmaker_all_sports(
                        bookmaker_code=bookmaker_code,
                        sports=sports_to_scrape,
                        limit=limit,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception(f"[{bookmaker_code}] Scheduler worker failed: {exc}")
                    result = {
                        "bookmaker": bookmaker_code,
                        "success": False,
                        "error": str(exc),
                        "events_scraped": 0,
                        "odds_scraped": 0,
                    }
                finally:
                    await _mark_finish(platform)
                    platform_semaphore.release()
                    queue.task_done()

                results_by_bookmaker[str(bookmaker_code)] = result

        workers = [asyncio.create_task(_worker()) for _ in range(global_cap)]
        await asyncio.gather(*workers)

        ordered_results: List[Dict[str, Any]] = []
        for cfg in bookmaker_configs:
            code = str(cfg.get("code"))
            ordered_results.append(
                results_by_bookmaker.get(
                    code,
                    {
                        "bookmaker": code,
                        "success": False,
                        "error": "Missing scheduler result",
                        "events_scraped": 0,
                        "odds_scraped": 0,
                    },
                )
            )

        metrics = {
            "global_cap": global_cap,
            "platform_caps": platform_caps,
            "observed_max_in_flight_global": max_global,
            "observed_max_in_flight_by_platform": max_platform,
            "total_scheduled": len(bookmaker_configs),
        }
        return ordered_results, metrics

    async def scrape_all_active_bookmakers(
        self,
        sport: str = "all",
        limit: Optional[int] = None,
        requested_bookmakers: Optional[List[str]] = None,
        requested_competition: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Scrape all active bookmakers for all sports with bounded concurrency.

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
        active_bookmaker_configs = self.get_active_bookmakers_from_db(
            requested_sport=sport,
            requested_competition=requested_competition,
            requested_bookmakers=requested_bookmakers,
        )
        active_bookmaker_codes = [bm["code"] for bm in active_bookmaker_configs]

        if not active_bookmaker_configs:
            return {
                "success": False,
                "bookmakers_scraped": 0,
                "total_bookmakers": 0,
                "events_scraped": 0,
                "odds_scraped": 0,
                "odds_saved": 0,
                "errors": ["No runnable bookmakers after lifecycle/freeze/rollout selection"],
                "duration_seconds": 0.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "results": [],
                "parallel": True,
                "scheduler": {
                    "global_cap": int(self.global_scrape_concurrency_cap),
                    "platform_caps": {},
                    "observed_max_in_flight_global": 0,
                    "observed_max_in_flight_by_platform": {},
                    "total_scheduled": 0,
                },
                "cleanup": None,
                "validation": None,
            }

        # Create scrapers for each active bookmaker
        for bm_config in active_bookmaker_configs:
            code = bm_config["code"]
            scraping_config = dict(bm_config.get("scraping_config", {}))
            scraping_config["base_url"] = bm_config.get("base_url")
            scraping_config["website_url"] = bm_config.get("website_url")
            self.get_scraper_for_bookmaker(code, scraping_config)

        logger.info(
            f"[BOUNDED] Starting scrape: {len(active_bookmaker_codes)} bookmakers x {len(sports_to_scrape)} sports"
        )
        logger.info(f"[BOUNDED] Active bookmakers: {', '.join(active_bookmaker_codes)}")
        logger.info(
            f"[BOUNDED] Caps: global={self.global_scrape_concurrency_cap}, "
            f"platform_default={self.platform_default_concurrency_cap}, "
            f"platform_overrides={self.platform_concurrency_caps}"
        )

        # Bounded execution: worker-pool by bookmaker with per-platform semaphores
        results, scheduler_metrics = await self._run_bounded_bookmaker_schedule(
            bookmaker_configs=active_bookmaker_configs,
            sports_to_scrape=sports_to_scrape,
            limit=limit,
        )

        parallel_duration = time.time() - parallel_start
        logger.info(
            f"[BOUNDED] All bookmakers completed in {parallel_duration:.2f}s"
        )
        logger.info(
            f"[BOUNDED] Observed max in-flight: global={scheduler_metrics.get('observed_max_in_flight_global')}, "
            f"per_platform={scheduler_metrics.get('observed_max_in_flight_by_platform')}"
        )

        # Aggregate statistics
        total_events = 0
        total_odds = 0
        total_saved = 0
        all_errors = []
        success_count = 0
        bookmaker_results = []
        scrape_durations: List[float] = []
        platform_outcomes: Dict[str, Dict[str, int]] = {}

        for bookmaker, result in zip(active_bookmaker_codes, results):
            bookmaker_results.append(result)
            platform_code = self._bookmaker_platform_codes.get(bookmaker, "unknown")
            platform_bucket = platform_outcomes.setdefault(
                platform_code,
                {"success": 0, "failure": 0},
            )

            if result.get("success"):
                success_count += 1
                platform_bucket["success"] += 1
            else:
                platform_bucket["failure"] += 1

            total_events += result.get("events_scraped", 0)
            total_odds += result.get("odds_scraped", 0)
            total_saved += result.get("odds_saved", 0)
            duration_seconds = result.get("scrape_duration_seconds")
            if duration_seconds is None:
                duration_seconds = result.get("duration_seconds")
            if duration_seconds is not None:
                try:
                    scrape_durations.append(float(duration_seconds))
                except (TypeError, ValueError):
                    pass

            # Collect errors
            result_errors = result.get("errors", [])
            if result_errors:
                all_errors.extend([f"{bookmaker}: {e}" for e in result_errors])

            emit_observability_event(
                category="scrape_reliability",
                metric_name="scrape_bookmaker_result",
                source="worker",
                bookmaker_code=bookmaker,
                platform_code=platform_code,
                action_type="bookmaker_scrape_result",
                payload={
                    "success": bool(result.get("success")),
                    "events_scraped": int(result.get("events_scraped", 0) or 0),
                    "odds_scraped": int(result.get("odds_scraped", 0) or 0),
                    "odds_saved": int(result.get("odds_saved", 0) or 0),
                    "scrape_duration_seconds": result.get("scrape_duration_seconds"),
                    "duration_seconds": result.get("duration_seconds"),
                    "error": result.get("error"),
                },
            )

        total_bookmakers = len(active_bookmaker_codes)
        failure_count = max(0, total_bookmakers - success_count)
        scrape_success_rate = (success_count / total_bookmakers) if total_bookmakers else 0.0
        open_breaker_count = sum(
            1
            for code in active_bookmaker_codes
            if str(self._get_breaker_state(code).get("state", "closed")).lower() == "open"
        )
        scrape_duration_p95 = self._percentile(scrape_durations, 0.95) if scrape_durations else 0.0

        emit_observability_event(
            category="scheduler",
            metric_name="scrape_scheduler_cycle",
            source="worker",
            action_type="bounded_scheduler_cycle",
            payload={
                "configured_global_cap": int(self.global_scrape_concurrency_cap),
                "configured_platform_default_cap": int(self.platform_default_concurrency_cap),
                "configured_platform_caps": dict(self.platform_concurrency_caps),
                "observed_max_in_flight_global": int(
                    scheduler_metrics.get("observed_max_in_flight_global", 0) or 0
                ),
                "observed_max_in_flight_by_platform": scheduler_metrics.get(
                    "observed_max_in_flight_by_platform", {}
                ),
                "effective_global_cap": int(scheduler_metrics.get("global_cap", 0) or 0),
                "effective_platform_caps": scheduler_metrics.get("platform_caps", {}),
                "total_scheduled": int(scheduler_metrics.get("total_scheduled", 0) or 0),
                "cycle_duration_seconds": float(parallel_duration),
            },
        )
        emit_observability_event(
            category="scrape_reliability",
            metric_name="scrape_reliability_cycle",
            source="worker",
            action_type="scrape_cycle_summary",
            payload={
                "total_bookmakers": total_bookmakers,
                "success_count": success_count,
                "failure_count": failure_count,
                "scrape_success_rate": scrape_success_rate,
                "open_breaker_count": open_breaker_count,
                "scrape_duration_p95_seconds": scrape_duration_p95,
                "platform_outcomes": platform_outcomes,
            },
        )

        # Run cleanup after successful scrape (Phase 3 optimization)
        cleanup_result = None
        if success_count > 0:
            try:
                cleanup_start = time.time()
                cleanup_result = self._run_post_scrape_cleanup()
                cleanup_duration = time.time() - cleanup_start
                logger.info(f"[CLEANUP] Post-scrape cleanup took {cleanup_duration:.2f}s")
            except Exception as e:
                logger.error(f"[CLEANUP] Post-scrape cleanup failed: {e}")
                cleanup_result = {"error": str(e)}

        # Run validation after successful scrape (non-blocking)
        validation_result = None
        if success_count > 0 and self.validation_enabled:
            try:
                validation_start = time.time()
                # Map sport to competition for validation
                competition_map = {
                    "soccer": "laliga",  # Default to La Liga for soccer
                    "afl": "afl",
                    "nrl": "nrl",
                    "basketball": "nba",
                    "ice_hockey": "nhl",
                    "boxing": "boxing",
                }
                # Validate primary sport/competition
                validation_comp = competition_map.get(sports_to_scrape[0], "laliga")
                validation_result = self._run_post_scrape_validation(validation_comp)
                validation_duration = time.time() - validation_start
                logger.info(f"[VALIDATION] Post-scrape validation took {validation_duration:.2f}s")
            except Exception as e:
                logger.error(f"[VALIDATION] Post-scrape validation failed: {e}")
                validation_result = {"error": str(e)}

        return {
            "success": success_count > 0,
            "bookmakers_scraped": success_count,
            "total_bookmakers": total_bookmakers,
            "events_scraped": total_events,
            "odds_scraped": total_odds,
            "odds_saved": total_saved,
            "errors": all_errors,
            "duration_seconds": parallel_duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": bookmaker_results,
            "parallel": True,  # Preserve existing contract; execution remains concurrent.
            "scheduler": scheduler_metrics,
            "cleanup": cleanup_result,  # Phase 3: cleanup stats
            "validation": validation_result,  # Validation results
        }

# Singleton instance
_scrape_service = None


def get_scrape_service() -> ScrapeService:
    """Get singleton scrape service instance"""
    global _scrape_service
    if _scrape_service is None:
        _scrape_service = ScrapeService()
    return _scrape_service


def _normalize_code(value: Any) -> str:
    return str(value or "").strip().lower()


async def trigger_scrape(
    sport: str = "soccer",
    limit: Optional[int] = None,
    requested_bookmakers: Optional[List[str]] = None,
    requested_competition: Optional[str] = None,
) -> Dict[str, Any]:
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
    return await service.scrape_all_active_bookmakers(
        sport,
        limit,
        requested_bookmakers=requested_bookmakers,
        requested_competition=requested_competition,
    )
