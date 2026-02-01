"""
Betfair Exchange scraper using Playwright for web scraping.

This scraper navigates to Betfair's Australian Exchange website and intercepts
network requests to capture odds data. No API authentication required.

Targets: https://www.betfair.com.au/exchange/plus/football

PARALLELIZATION NOTES (Phase 1 Production Optimization):
- Each scrape_sport() call uses isolated captured_data via closure pattern
- This allows multiple sports to be scraped in parallel without race conditions
- Use scrape_all_sports_parallel() for optimal performance (6x speedup)

DYNAMIC WAITS (Phase 2 Production Optimization):
- Replaced fixed 5s waits with polling-based detection
- Polls every 300ms for bymarket data capture, max 8s
- Fast sports complete in 2-3s instead of 8s
- Saves 2-4s per competition, significant at scale
"""
import asyncio
import json
import re
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from playwright.async_api import async_playwright, Page, Response
import logging

from .base import BaseScraper, ScrapeResult, ScrapedEvent, ScrapedOdds, ScraperStatus

logger = logging.getLogger(__name__)


class BetfairScraper(BaseScraper):
    """
    Scraper for Betfair Exchange using Playwright.

    Approach:
    1. Launch headless browser (ONCE - reused across scrapes)
    2. Navigate to Betfair Exchange EPL page
    3. Intercept network responses containing odds data
    4. Parse JSON responses to extract events, markets, and lay odds
    5. Match team names with TAB data
    """

    # Class-level browser instance (shared across all scrapes)
    _browser = None
    _playwright = None
    _browser_context = None
    _browser_lock = None  # Asyncio lock for browser creation (initialized lazily)

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            bookmaker_code="betfair",
            base_url="https://www.betfair.com.au",
            config=config
        )

        # Betfair Exchange URLs
        self.exchange_base = "https://www.betfair.com.au/exchange/plus"

        # Competition URLs mapping - All 14 target sports
        self.competition_urls = {
            "soccer": {
                "English Premier League": f"{self.exchange_base}/football/competition/10932509",
                "A-League Men": f"{self.exchange_base}/football/competition/12117172",
                "Spanish La Liga": f"{self.exchange_base}/football/competition/117",
                "German Bundesliga": f"{self.exchange_base}/football/competition/59",
                "Italian Serie A": f"{self.exchange_base}/football/competition/81",
                "French Ligue 1": f"{self.exchange_base}/football/competition/55",
                "UEFA Champions League": f"{self.exchange_base}/football/competition/228",
                "Major League Soccer": f"{self.exchange_base}/football/competition/141",
            },
            "afl": {
                "AFL": f"{self.exchange_base}/australian-rules/competition/11897406"
            },
            "nrl": {
                "NRL": f"{self.exchange_base}/rugby-league/competition/10564377"
            },
            "basketball": {
                "NBA": f"{self.exchange_base}/basketball/competition/10547864",
                "NBL": f"{self.exchange_base}/basketball/competition/10533436",
            },
            "ice_hockey": {
                "NHL": f"{self.exchange_base}/ice-hockey/competition/12550521"
            },
            "boxing": {
                "Boxing": f"{self.exchange_base}/boxing/competition/10817625"
            }
        }

        # NOTE: captured_data is NO LONGER used as instance variable
        # Each scrape_sport() call uses local captured_data via closure pattern
        # This enables safe parallel execution of multiple sports

        # All supported sports for parallel scraping
        self.ALL_SPORTS = ["soccer", "basketball", "ice_hockey", "boxing", "afl", "nrl"]

        # Team name normalization mapping
        self.team_name_mapping = {
            # EPL teams - normalize variations
            "man united": "manchester united",
            "man utd": "manchester united",
            "man city": "manchester city",
            "man city": "manchester city",
            "spurs": "tottenham hotspur",
            "tottenham": "tottenham hotspur",
            "wolves": "wolverhampton wanderers",
            "west ham": "west ham united",
            "newcastle": "newcastle united",
            "brighton": "brighton & hove albion",
            "brighton and hove albion": "brighton & hove albion",
            "nottm forest": "nottingham forest",
            "nottinghm forest": "nottingham forest",
            "nott'm forest": "nottingham forest",
            "leicester": "leicester city",
            "leeds": "leeds united",
        }

    async def scrape_sport(self, sport: str, limit: Optional[int] = None) -> ScrapeResult:
        """
        Scrape Betfair Exchange for a specific sport using Playwright.

        PARALLELIZATION SAFE: Uses closure pattern for captured_data.
        Multiple calls can run concurrently without race conditions.

        Args:
            sport: Our sport code ("soccer", "afl", etc.)
            limit: Max events to scrape

        Returns:
            ScrapeResult with events and lay odds
        """
        started_at = datetime.now(timezone.utc)
        scrape_start = time.time()
        events = []
        errors = []

        try:
            if sport not in self.competition_urls:
                errors.append(f"Unsupported sport: {sport}")
                return self._create_failed_result(started_at, errors)

            self.logger.info(f"[{self.bookmaker_code}] Starting scrape: {sport}")

            # Run Playwright scraping with isolated captured_data
            events = await self._scrape_with_playwright(sport, limit)

            if not events:
                errors.append(f"No events captured from Betfair for {sport}")

        except Exception as e:
            errors.append(f"Betfair scrape failed: {str(e)}")
            self.logger.exception(f"[{self.bookmaker_code}/{sport}] Playwright error")

        # Calculate stats
        total_odds = sum(len(event.odds) for event in events)
        status = ScraperStatus.SUCCESS if not errors else (
            ScraperStatus.PARTIAL if events else ScraperStatus.FAILED
        )

        scrape_duration = time.time() - scrape_start
        result = ScrapeResult(
            bookmaker_code=self.bookmaker_code,
            status=status,
            events_scraped=len(events),
            odds_scraped=total_odds,
            events=events,
            errors=errors,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc)
        )

        self.logger.info(
            f"⏱️  [Betfair/{sport}] Completed in {scrape_duration:.2f}s: "
            f"{len(events)} events, {total_odds} odds"
        )
        self.log_scrape_stats(result)
        return result

    async def scrape_all_sports_parallel(
        self,
        sports: Optional[List[str]] = None,
        limit: Optional[int] = None,
        batch_size: Optional[int] = None
    ) -> ScrapeResult:
        """
        Scrape ALL sports in parallel using asyncio.gather with batching.

        This is the PRIMARY method for production use - provides speedup
        by running sport scrapes concurrently in batches.

        Args:
            sports: List of sports to scrape. Defaults to ALL_SPORTS.
            limit: Optional limit per sport (for testing)
            batch_size: Number of sports to scrape in parallel.
                        Default: SCRAPER_BATCH_SIZE env var, or 1 for Docker compatibility.
                        Set to 3-6 in production for better performance.

        Returns:
            Combined ScrapeResult with all events from all sports

        Performance:
            Sequential (batch=1): 6 sports × 15s = 90s
            Batched (batch=3): 2 batches × 15s = ~30s (3x speedup)
            Parallel (batch=6): 1 batch × 15s = ~15s (6x speedup) - production only
        """
        import os
        # Default to 1 for Docker compatibility, configurable via env for production
        if batch_size is None:
            batch_size = int(os.getenv("SCRAPER_BATCH_SIZE", "1"))
        started_at = datetime.now(timezone.utc)
        scrape_start = time.time()

        sports_to_scrape = sports or self.ALL_SPORTS
        self.logger.info(
            f"[{self.bookmaker_code}] Starting BATCHED PARALLEL scrape of {len(sports_to_scrape)} sports "
            f"(batch_size={batch_size}): {', '.join(sports_to_scrape)}"
        )

        # Process sports in batches to avoid overloading browser
        all_results = []
        for i in range(0, len(sports_to_scrape), batch_size):
            batch = sports_to_scrape[i:i + batch_size]
            self.logger.info(f"[{self.bookmaker_code}] Processing batch {i//batch_size + 1}: {', '.join(batch)}")

            tasks = [self.scrape_sport(sport, limit=limit) for sport in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            all_results.extend(zip(batch, batch_results))

        # Unpack results
        results = [r for _, r in all_results]
        sports_processed = [s for s, _ in all_results]

        # Aggregate results
        all_events = []
        all_errors = []
        total_events_scraped = 0
        total_odds_scraped = 0
        successful_sports = []
        failed_sports = []

        for sport, result in zip(sports_processed, results):
            if isinstance(result, Exception):
                # Task raised an exception
                error_msg = f"{sport}: {str(result)}"
                all_errors.append(error_msg)
                failed_sports.append(sport)
                self.logger.error(f"[{self.bookmaker_code}] {sport} failed with exception: {result}")
            elif isinstance(result, ScrapeResult):
                # Normal result
                all_events.extend(result.events)
                all_errors.extend(result.errors)
                total_events_scraped += result.events_scraped
                total_odds_scraped += result.odds_scraped

                if result.status == ScraperStatus.SUCCESS:
                    successful_sports.append(sport)
                elif result.status == ScraperStatus.PARTIAL:
                    successful_sports.append(f"{sport}(partial)")
                else:
                    failed_sports.append(sport)
            else:
                # Unexpected result type
                all_errors.append(f"{sport}: Unexpected result type: {type(result)}")
                failed_sports.append(sport)

        # Determine overall status
        if not all_errors:
            status = ScraperStatus.SUCCESS
        elif all_events:
            status = ScraperStatus.PARTIAL
        else:
            status = ScraperStatus.FAILED

        scrape_duration = time.time() - scrape_start

        combined_result = ScrapeResult(
            bookmaker_code=self.bookmaker_code,
            status=status,
            events_scraped=total_events_scraped,
            odds_scraped=total_odds_scraped,
            events=all_events,
            errors=all_errors,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc)
        )

        self.logger.info(
            f"⏱️  [Betfair] PARALLEL scrape completed in {scrape_duration:.2f}s: "
            f"{total_events_scraped} events, {total_odds_scraped} odds | "
            f"Success: {', '.join(successful_sports) or 'none'} | "
            f"Failed: {', '.join(failed_sports) or 'none'}"
        )

        return combined_result

    async def _get_or_create_browser(self):
        """
        Get existing browser instance or create new one (singleton pattern).

        Uses asyncio lock to prevent race conditions when multiple
        parallel calls try to create the browser simultaneously.
        """
        # Initialize lock lazily (must be done inside async context)
        if BetfairScraper._browser_lock is None:
            BetfairScraper._browser_lock = asyncio.Lock()

        async with BetfairScraper._browser_lock:
            if BetfairScraper._browser is None or not BetfairScraper._browser.is_connected():
                browser_start = time.time()
                self.logger.info("⏱️  [Betfair] Launching NEW browser instance...")

                BetfairScraper._playwright = await async_playwright().start()
                BetfairScraper._browser = await BetfairScraper._playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )

                browser_launch_time = time.time() - browser_start
                self.logger.info(f"⏱️  [Betfair] Browser launch took {browser_launch_time:.2f}s")
            else:
                self.logger.debug("⏱️  [Betfair] Reusing existing browser instance")

        return BetfairScraper._browser

    async def _scrape_with_playwright(self, sport: str, limit: Optional[int]) -> List[ScrapedEvent]:
        """
        Use Playwright to scrape Betfair Exchange (with browser reuse).

        PARALLELIZATION SAFE: Uses local captured_data via closure pattern.
        Each call has isolated data capture - no race conditions.
        """
        events = []

        # LOCAL captured_data - isolated per call via closure
        # This is the key fix for parallel execution safety
        captured_data: List[Dict] = []

        # LOCAL current_competition tracker (not instance variable)
        current_competition = {"name": "Unknown"}  # Use dict for mutability in closure

        # Get or reuse browser instance (HUGE speedup on subsequent runs)
        browser = await self._get_or_create_browser()

        context = None  # Initialize to None for safe cleanup in finally block
        try:
            # Create NEW context for each scrape (contexts are lightweight, isolates cookies/cache)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-AU',
                timezone_id='Australia/Sydney'
            )

            page = await context.new_page()

            # CLOSURE PATTERN: Response handler captures LOCAL captured_data
            # Each scrape_with_playwright() call has its own isolated list
            async def handle_response(response: Response):
                """Handle intercepted network responses - captures local captured_data"""
                try:
                    url = response.url

                    # Look for the specific Betfair API endpoints we need
                    if response.status == 200:
                        # Key endpoints: navigation-aggregator (fixtures) and bymarket (prices)
                        if any(pattern in url for pattern in [
                            'navigation-aggregator',  # Fixtures + market IDs
                            '/bymarket',              # Actual prices/odds
                            '/readonly/v1/bymarket'   # Full endpoint path
                        ]):
                            try:
                                content_type = response.headers.get('content-type', '')
                                if 'application/json' in content_type:
                                    data = await response.json()

                                    # Append to LOCAL list (not self.captured_data)
                                    captured_data.append({
                                        'url': url,
                                        'data': data,
                                        'timestamp': datetime.now(timezone.utc),
                                        'competition': current_competition["name"]
                                    })

                                    self.logger.info(f"✓ [{sport}/{current_competition['name']}] Captured: {url[:80]}...")

                            except Exception as e:
                                self.logger.debug(f"Could not parse response from {url[:100]}: {e}")

                except Exception as e:
                    self.logger.debug(f"Error handling response: {e}")

            page.on('response', lambda response: asyncio.create_task(handle_response(response)))

            # Navigate to each competition page
            competitions = self.competition_urls.get(sport, {})
            for comp_name, url in competitions.items():
                comp_start = time.time()
                self.logger.info(f"⏱️  [Betfair/{sport}] Navigating to {comp_name}: {url}")

                # Update current competition for response handler (via closure)
                current_competition["name"] = comp_name

                try:
                    # Navigate with domcontentloaded (faster than networkidle)
                    nav_start = time.time()
                    await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    nav_time = time.time() - nav_start
                    self.logger.info(f"⏱️  [Betfair/{sport}] Page load took {nav_time:.2f}s")

                    # PHASE 2: Dynamic wait - poll for captured data instead of fixed 5s
                    # This saves 2-4s for fast competitions that respond quickly
                    wait_start = time.time()
                    max_wait = 8.0  # Maximum wait time in seconds
                    poll_interval = 0.3  # Check every 300ms
                    data_captured = False
                    initial_count = len(captured_data)

                    while (time.time() - wait_start) < max_wait:
                        # Check if we captured new bymarket data (not just navigation)
                        new_bymarket = any(
                            'bymarket' in c.get('url', '')
                            for c in captured_data[initial_count:]
                        )
                        if new_bymarket:
                            # Data captured! Wait a bit more for any additional responses
                            await asyncio.sleep(0.5)
                            data_captured = True
                            break
                        await asyncio.sleep(poll_interval)

                    wait_time = time.time() - wait_start
                    if data_captured:
                        self.logger.info(f"⏱️  [Betfair/{sport}] Data captured after {wait_time:.2f}s (saved {max_wait - wait_time:.1f}s)")
                    else:
                        self.logger.info(f"⏱️  [Betfair/{sport}] Max wait reached ({wait_time:.2f}s), continuing anyway")

                    if sport == "basketball" and comp_name in ("NBA", "NBL"):
                        await self._capture_future_tabs(page, sport, comp_name, captured_data)

                    comp_time = time.time() - comp_start
                    self.logger.info(f"⏱️  [Betfair/{sport}] {comp_name} took {comp_time:.2f}s - captured {len(captured_data)} responses")

                except Exception as e:
                    self.logger.error(f"[Betfair/{sport}] Failed to load {comp_name}: {e}")
                    continue

            # Brief wait for async response handlers to finish processing
            await asyncio.sleep(0.5)
            self.logger.info(f"⏱️  [Betfair/{sport}] Captured {len(captured_data)} total responses")

            # Parse captured data into events (using LOCAL list)
            parse_start = time.time()
            events = self._parse_captured_data_local(captured_data, sport, limit)
            parse_time = time.time() - parse_start
            self.logger.info(f"⏱️  [Betfair/{sport}] Parsing took {parse_time:.2f}s - {len(events)} events")

        finally:
            # Close context (lightweight), but KEEP browser running
            if context:
                await context.close()

        return events

    # NOTE: _handle_response() method REMOVED - replaced by inline closure in _scrape_with_playwright()
    # This enables parallel execution safety (each call has its own captured_data list)

    async def _capture_future_tabs(
        self,
        page: Page,
        sport: str,
        comp_name: str,
        captured_data: List[Dict]
    ) -> None:
        """Trigger Tomorrow/Future tabs so upcoming NBA/NBL markets are captured."""
        for label in ("Tomorrow", "Future"):
            await self._click_filter_tab(page, label, captured_data, sport, comp_name)

    async def _click_filter_tab(
        self,
        page: Page,
        label: str,
        captured_data: List[Dict],
        sport: str,
        comp_name: str
    ) -> None:
        try:
            locator = page.get_by_role("button", name=label)
            if await locator.count() == 0:
                locator = page.get_by_role("link", name=label)
            if await locator.count() == 0:
                locator = page.locator(f"text={label}")
            if await locator.count() == 0:
                self.logger.debug(f"[Betfair/{sport}] {comp_name}: {label} tab not found")
                return

            initial_count = len(captured_data)
            await locator.first.click()
            await asyncio.sleep(0.2)

            if await self._wait_for_new_bymarket(captured_data, initial_count, timeout=6.0):
                self.logger.info(f"[Betfair/{sport}] {comp_name}: captured {label} markets")
            else:
                self.logger.info(f"[Betfair/{sport}] {comp_name}: no new data for {label}")
        except Exception as e:
            self.logger.debug(f"[Betfair/{sport}] {comp_name}: {label} click failed: {e}")

    async def _wait_for_new_bymarket(
        self,
        captured_data: List[Dict],
        initial_count: int,
        timeout: float = 6.0
    ) -> bool:
        wait_start = time.time()
        while (time.time() - wait_start) < timeout:
            new_bymarket = any(
                'bymarket' in c.get('url', '')
                for c in captured_data[initial_count:]
            )
            if new_bymarket:
                await asyncio.sleep(0.5)
                return True
            await asyncio.sleep(0.3)
        return False

    def _parse_captured_data_local(
        self,
        captured_data: List[Dict],
        sport: str,
        limit: Optional[int]
    ) -> List[ScrapedEvent]:
        """
        Parse captured network data into ScrapedEvent objects.

        Takes captured_data as parameter (not self.captured_data) to support
        parallel execution with isolated data per call.
        """
        events_dict: Dict[str, ScrapedEvent] = {}  # Key by event ID
        fixtures_data = None
        bymarket_events = {}  # event_id -> {event_data, competition}

        self.logger.info(f"Parsing {len(captured_data)} captured responses")

        # First pass: identify fixtures and bymarket data
        for capture in captured_data:
            try:
                url = capture['url']
                data = capture['data']
                competition = capture.get('competition', 'Unknown')

                # Check if this is the navigation-aggregator (fixtures)
                if 'navigation-aggregator' in url:
                    fixtures_data = data
                    self.logger.info("Found fixtures data (navigation-aggregator)")

                # Check if this is bymarket (prices)
                elif 'bymarket' in url:
                    # Extract complete event data from bymarket response
                    event_types = data.get('eventTypes', [])
                    if event_types:
                        for et in event_types:
                            event_nodes = et.get('eventNodes', [])
                            for event_node in event_nodes:
                                event_id = str(event_node.get('eventId', ''))
                                if event_id:
                                    if event_id not in bymarket_events:
                                        bymarket_events[event_id] = {
                                            'node': event_node,
                                            'competition': competition
                                        }
                                    else:
                                        # Update event data if new one has better info,
                                        # but PRESERVE the original competition assignment
                                        # (first assignment is correct - from the page we navigated to)
                                        existing_has_event = 'event' in bymarket_events[event_id]['node']
                                        new_has_event = 'event' in event_node
                                        if new_has_event and not existing_has_event:
                                            # Keep original competition, only update node data
                                            original_competition = bymarket_events[event_id]['competition']
                                            bymarket_events[event_id] = {
                                                'node': event_node,
                                                'competition': original_competition
                                            }

            except Exception as e:
                self.logger.debug(f"Could not parse captured data: {e}")
                continue

        # Parse using bymarket data (which has everything we need)
        if bymarket_events:
            events = self._parse_bymarket_events(bymarket_events, fixtures_data, sport)
            if limit:
                events = events[:limit]
            return events

        self.logger.warning("No bymarket data found - cannot parse events")
        return []

    def _parse_captured_data(self, sport: str, limit: Optional[int]) -> List[ScrapedEvent]:
        """Parse captured network data into ScrapedEvent objects"""
        events_dict: Dict[str, ScrapedEvent] = {}  # Key by event ID
        fixtures_data = None
        bymarket_events = {}  # event_id -> {event_data, competition}

        self.logger.info(f"Parsing {len(self.captured_data)} captured responses")

        # First pass: identify fixtures and bymarket data
        for capture in self.captured_data:
            try:
                url = capture['url']
                data = capture['data']
                competition = capture.get('competition', 'Unknown')

                # Check if this is the navigation-aggregator (fixtures)
                if 'navigation-aggregator' in url:
                    fixtures_data = data
                    self.logger.info("Found fixtures data (navigation-aggregator)")

                # Check if this is bymarket (prices)
                elif 'bymarket' in url:
                    # Extract complete event data from bymarket response
                    # This includes eventId, event metadata, and market prices
                    event_types = data.get('eventTypes', [])
                    if event_types:
                        for et in event_types:
                            event_nodes = et.get('eventNodes', [])
                            for event_node in event_nodes:
                                event_id = str(event_node.get('eventId', ''))
                                if event_id:
                                    # Store event with competition info
                                    # Only store if we don't already have this event, OR if this one has better data
                                    if event_id not in bymarket_events:
                                        bymarket_events[event_id] = {
                                            'node': event_node,
                                            'competition': competition
                                        }
                                        self.logger.debug(f"Stored new event {event_id} from {competition}")
                                    else:
                                        # Update event data if new one has better info,
                                        # but PRESERVE the original competition assignment
                                        # (first assignment is correct - from the page we navigated to)
                                        existing_has_event = 'event' in bymarket_events[event_id]['node']
                                        new_has_event = 'event' in event_node
                                        if new_has_event and not existing_has_event:
                                            # Keep original competition, only update node data
                                            original_competition = bymarket_events[event_id]['competition']
                                            bymarket_events[event_id] = {
                                                'node': event_node,
                                                'competition': original_competition
                                            }
                                            self.logger.debug(f"Updated event {event_id} node data (kept competition: {original_competition})")

            except Exception as e:
                self.logger.debug(f"Could not parse captured data: {e}")
                continue

        # Parse using bymarket data (which has everything we need)
        if bymarket_events:
            events = self._parse_bymarket_events(bymarket_events, fixtures_data, sport)
            if limit:
                events = events[:limit]
            return events

        self.logger.warning("No bymarket data found - cannot parse events")
        return []

    def _parse_bymarket_events(
        self,
        bymarket_events: Dict[str, Dict],
        fixtures_data: Optional[Dict],
        sport: str
    ) -> List[ScrapedEvent]:
        """
        Parse events directly from bymarket data.

        bymarket_events structure (after our update):
        {
            "34782800": {
                "node": {
                    "eventId": 34782800,
                    "event": {
                        "eventName": "Man City v Everton",
                        "countryCode": "GB",
                        "openDate": "2025-10-18T14:00:00.000Z"
                    },
                    "marketNodes": [...]
                },
                "competition": "English Premier League"
            }
        }
        """
        events = []

        self.logger.info(f"Parsing {len(bymarket_events)} events from bymarket data")

        for event_id, event_data in bymarket_events.items():
            try:
                # Extract node and competition from our structure
                event_node = event_data.get('node', event_data)  # Fallback for old structure
                competition = event_data.get('competition', 'Unknown')

                # Extract event metadata
                event_meta = event_node.get('event', {})
                event_name = event_meta.get('eventName', '')
                open_date = event_meta.get('openDate', '')

                if not event_name:
                    self.logger.debug(f"Skipping event {event_id} - no name")
                    continue

                # Parse start time
                try:
                    start_time = datetime.fromisoformat(open_date.replace("Z", "+00:00"))
                except:
                    start_time = datetime.now(timezone.utc) + timedelta(days=1)

                # Extract teams from event name
                home_team, away_team = self._extract_teams_from_name(event_name)

                # Prefer fixtures_data competition mapping when available
                # (bymarket responses can include events from other competitions)
                competition_from_fixtures = self._get_competition_for_event(event_id, fixtures_data)
                if competition_from_fixtures != "Unknown":
                    competition = competition_from_fixtures

                # Create event
                event = ScrapedEvent(
                    external_id=event_id,
                    name=event_name,
                    sport=sport,
                    competition=competition,
                    start_time=start_time,
                    home_team=home_team,
                    away_team=away_team,
                    odds=[]
                )

                # Parse markets for this event
                market_nodes = event_node.get('marketNodes', [])
                self.logger.debug(f"Event {event_name} has {len(market_nodes)} market nodes")

                for market_node in market_nodes:
                    # Check if this is Match Odds market
                    description = market_node.get('description', {})
                    market_type = description.get('marketType', '')
                    market_name = description.get('marketName', 'Match Odds')

                    self.logger.debug(f"Market type: {market_type}, name: {market_name}")

                    # Accept MATCH_ODDS (soccer), MONEY_LINE (NHL/NBA), WIN (boxing/other)
                    if market_type in ('MATCH_ODDS', 'MONEY_LINE', 'WIN'):
                        # Parse odds from this market
                        market_odds = self._parse_market_prices(market_node, event, market_name)
                        expected = self._expected_selection_count(sport, market_type)
                        if not market_odds:
                            continue
                        if len(market_odds) < expected:
                            # Keep partial markets: exchanges often have liquidity on only 1 side.
                            # Outmatched shows these (e.g., NBL) and we can still compute opportunities
                            # for selections that have a valid lay price + liquidity.
                            self.logger.info(
                                f"[Betfair/{sport}] Partial {market_name} for {event_name}: "
                                f"{len(market_odds)}<{expected} selections with liquidity"
                            )
                        self.logger.debug(f"Parsed {len(market_odds)} odds from {market_name}")
                        event.odds.extend(market_odds)

                # Only add event if it has odds
                if event.odds:
                    events.append(event)
                    self.logger.info(f"Parsed event: {event_name} with {len(event.odds)} odds")
                else:
                    self.logger.debug(f"Skipping event {event_name} - no odds")

            except Exception as e:
                self.logger.error(f"Failed to parse bymarket event {event_id}: {e}")
                continue

        self.logger.info(f"Successfully parsed {len(events)} events with odds")
        return events

    def _expected_selection_count(self, sport: str, market_type: str) -> int:
        """Expected selection count for H2H markets (soccer has draw)."""
        if sport == "soccer" and market_type == "MATCH_ODDS":
            return 3
        return 2

    def _get_competition_for_event(self, event_id: str, fixtures_data: Optional[Dict]) -> str:
        """Try to get competition name from fixtures data"""
        if not fixtures_data:
            return "Unknown"

        # Competition ID to name mapping for all 14 target sports
        competition_map = {
            # Soccer
            10932509: "English Premier League",
            12117172: "A-League Men",
            117: "Spanish La Liga",
            59: "German Bundesliga",
            81: "Italian Serie A",
            55: "French Ligue 1",
            228: "UEFA Champions League",
            141: "Major League Soccer",
            # AFL
            11897406: "AFL",
            # NRL
            10564377: "NRL",
            # Basketball
            10547864: "NBA",
            10533436: "NBL",
            # Ice Hockey
            12550521: "NHL",
            # Boxing
            10817625: "Boxing"
        }

        # Look through fixtures by date to find matching event
        fixtures_by_date = fixtures_data.get("fixtures", {})
        for date_str, date_fixtures in fixtures_by_date.items():
            for fixture in date_fixtures:
                if str(fixture.get("eventId", "")) == event_id:
                    # Map competition ID to name
                    comp_id = fixture.get("competitionId")
                    return competition_map.get(comp_id, f"Competition {comp_id}")

        return "Unknown"

    def _parse_fixtures_with_prices(
        self,
        fixtures_data: Dict,
        prices_data: Dict[str, Dict],
        sport: str
    ) -> List[ScrapedEvent]:
        """
        Parse fixtures data and attach prices from bymarket responses.

        fixtures_data structure:
        {
            "fixtures": {"2025-10-18": [{"eventId": 34782623, "name": "Nottm Forest v Chelsea", ...}]},
            "outrights": {"markets": {"1.248326936": {"eventId": 34782623, "marketType": "MATCH_ODDS", ...}}}
        }

        prices_data structure:
        {
            "1.248326936": {
                "marketId": "1.248326936",
                "runners": [{"description": {"runnerName": "Chelsea"}, "exchange": {"availableToLay": [...]}}]
            }
        }
        """
        events = []

        # Extract fixtures by date
        fixtures_by_date = fixtures_data.get("fixtures", {})
        self.logger.info(f"Found {len(fixtures_by_date)} dates of fixtures")

        # Extract market info from outrights
        outrights = fixtures_data.get("outrights", {})
        markets_info = outrights.get("markets", {})

        # Build event_id -> market_ids mapping
        event_markets = {}

        # markets_info can be either dict or list
        if isinstance(markets_info, dict):
            market_items = markets_info.items()
        elif isinstance(markets_info, list):
            market_items = [(m.get("marketId", ""), m) for m in markets_info]
        else:
            market_items = []

        for market_id, market_info in market_items:
            event_id = str(market_info.get("eventId", ""))
            market_type = market_info.get("marketType", "")

            if event_id and market_type in ("MATCH_ODDS", "MONEY_LINE", "WIN"):
                if event_id not in event_markets:
                    event_markets[event_id] = []
                event_markets[event_id].append({
                    "market_id": market_id,
                    "market_name": market_info.get("marketName", "Match Odds")
                })
                self.logger.debug(f"Mapped market {market_id} to event {event_id}")

        self.logger.info(f"Built event_markets map with {len(event_markets)} events")
        self.logger.info(f"Have prices_data for {len(prices_data)} markets")

        # Parse each fixture
        for date_str, date_fixtures in fixtures_by_date.items():
            for fixture in date_fixtures:
                try:
                    event_id = str(fixture.get("eventId", ""))
                    event_name = fixture.get("name", "")
                    open_date = fixture.get("openDate", "")

                    if not event_id or not event_name:
                        continue

                    # Parse start time
                    try:
                        start_time = datetime.fromisoformat(open_date.replace("Z", "+00:00"))
                    except:
                        start_time = datetime.now(timezone.utc) + timedelta(days=1)

                    # Extract teams
                    home_team, away_team = self._extract_teams_from_name(event_name)

                    # Create event
                    event = ScrapedEvent(
                        external_id=event_id,
                        name=event_name,
                        sport=sport,
                        competition="English Premier League",
                        start_time=start_time,
                        home_team=home_team,
                        away_team=away_team,
                        odds=[]
                    )

                    # Find markets for this event
                    markets = event_markets.get(event_id, [])
                    for market in markets:
                        market_id = market["market_id"]
                        market_name = market["market_name"]

                        # Get prices for this market
                        if market_id in prices_data:
                            market_data = prices_data[market_id]
                            odds = self._parse_market_prices(market_data, event, market_name)
                            event.odds.extend(odds)

                    # Only add event if it has odds
                    if event.odds:
                        events.append(event)
                        self.logger.info(f"Parsed event: {event_name} with {len(event.odds)} odds")

                except Exception as e:
                    self.logger.error(f"Failed to parse fixture: {e}")
                    continue

        self.logger.info(f"Parsed {len(events)} events with prices")
        return events

    def _parse_market_prices(
        self,
        market_data: Dict,
        event: ScrapedEvent,
        market_name: str
    ) -> List[ScrapedOdds]:
        """Parse prices from a market_data (bymarket response)"""
        odds_list = []

        runners = market_data.get("runners", [])
        market_id = market_data.get("marketId", "")

        for runner in runners:
            try:
                runner_desc = runner.get("description", {})
                runner_name = runner_desc.get("runnerName", "")

                if not runner_name:
                    continue

                # Get lay prices
                exchange = runner.get("exchange", {})
                lay_prices = exchange.get("availableToLay", [])

                if not lay_prices:
                    continue

                # Best lay price
                best_lay = lay_prices[0]
                lay_odds = best_lay.get("price")
                lay_size = best_lay.get("size")

                if not lay_odds:
                    continue
                if lay_size is None or lay_size <= 0:
                    continue

                try:
                    lay_odds_decimal = Decimal(str(lay_odds))
                except Exception:
                    continue

                # Drop no-liquidity placeholders (Betfair often uses >=100)
                if lay_odds_decimal >= Decimal("100"):
                    continue

                # Determine selection key
                selection_key = self._determine_selection_key(
                    runner_name, event.home_team, event.away_team
                )

                # Create odds
                odds = ScrapedOdds(
                    event_external_id=event.external_id,
                    event_name=event.name,
                    sport=event.sport,
                    competition=event.competition,
                    start_time=event.start_time,
                    market_type="match_winner",
                    market_name=market_name,
                    selection_name=runner_name,
                    selection_key=selection_key,
                    decimal_odds=lay_odds_decimal,
                    bookmaker_code=self.bookmaker_code,
                    source_url=f"https://www.betfair.com.au/exchange/plus/market/{market_id}",
                    scraped_at=datetime.now(timezone.utc),
                    liquidity=Decimal(str(lay_size)) if lay_size else None
                )

                odds_list.append(odds)

            except Exception as e:
                self.logger.error(f"Failed to parse runner: {e}")
                continue

        return odds_list

    def _parse_betfair_item(self, item: Dict, sport: str) -> Optional[ScrapedEvent]:
        """
        Parse a single item from Betfair API response.

        Betfair API structures vary, but common fields:
        - marketId: Unique market identifier
        - event: {id, name, countryCode, timezone, openDate}
        - competition: {id, name}
        - runners: [{selectionId, runnerName, ex: {availableToLay, availableToBack}}]
        - marketName: Usually "Match Odds" for head-to-head
        """
        try:
            # Extract event information
            event_data = item.get('event', {})
            if not event_data:
                return None

            event_id = event_data.get('id', item.get('eventId', ''))
            event_name = event_data.get('name', item.get('eventName', ''))

            if not event_id or not event_name:
                return None

            # Extract competition
            competition_data = item.get('competition', {})
            competition_name = competition_data.get('name', 'Unknown')

            # Parse start time
            start_time_str = event_data.get('openDate', item.get('marketStartTime', ''))
            try:
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            except:
                start_time = datetime.now(timezone.utc) + timedelta(days=1)

            # Extract team names from event name (e.g., "Liverpool v Chelsea")
            home_team, away_team = self._extract_teams_from_name(event_name)

            # Create event
            event = ScrapedEvent(
                external_id=str(event_id),
                name=event_name,
                sport=sport,
                competition=competition_name,
                start_time=start_time,
                home_team=home_team,
                away_team=away_team,
                odds=[]
            )

            # Parse odds (lay prices) from runners
            runners = item.get('runners', [])
            market_name = item.get('marketName', 'Match Odds')
            market_id = item.get('marketId', '')

            for runner in runners:
                try:
                    selection_name = runner.get('runnerName', runner.get('name', ''))
                    selection_id = runner.get('selectionId', runner.get('id', ''))

                    if not selection_name:
                        continue

                    # Get lay prices (exchange offers)
                    ex_data = runner.get('ex', {})
                    lay_prices = ex_data.get('availableToLay', [])

                    if not lay_prices:
                        continue

                    # Get best lay price (first in array)
                    best_lay = lay_prices[0]
                    lay_odds = best_lay.get('price', best_lay.get('odds', 0))
                    lay_size = best_lay.get('size', best_lay.get('liquidity', 0))

                    if not lay_odds:
                        continue

                    # Determine selection key (home/away/draw)
                    selection_key = self._determine_selection_key(
                        selection_name, home_team, away_team
                    )

                    # Create odds snapshot
                    odds = ScrapedOdds(
                        event_external_id=str(event_id),
                        event_name=event_name,
                        sport=sport,
                        competition=competition_name,
                        start_time=start_time,
                        market_type="match_winner",
                        market_name=market_name,
                        selection_name=selection_name,
                        selection_key=selection_key,
                        decimal_odds=Decimal(str(lay_odds)),
                        bookmaker_code=self.bookmaker_code,
                        source_url=f"https://www.betfair.com.au/exchange/plus/market/{market_id}",
                        scraped_at=datetime.now(timezone.utc),
                        liquidity=Decimal(str(lay_size)) if lay_size else None
                    )

                    event.odds.append(odds)

                except Exception as e:
                    self.logger.debug(f"Failed to parse runner: {e}")
                    continue

            # Only return event if it has odds
            if event.odds:
                return event

        except Exception as e:
            self.logger.debug(f"Failed to parse Betfair item: {e}")

        return None

    def _extract_teams_from_name(self, event_name: str) -> tuple[Optional[str], Optional[str]]:
        """
        Extract home and away team names from event name.

        Common formats:
        - "Liverpool v Chelsea"
        - "Man United vs Man City"
        - "Tottenham @ Arsenal"
        """
        # Try different separators
        for separator in [' v ', ' vs ', ' @ ', ' - ']:
            if separator in event_name:
                parts = event_name.split(separator)
                if len(parts) == 2:
                    if separator == ' @ ':
                        # Betfair uses Away @ Home for US sports (NBA/NHL)
                        away = parts[0].strip()
                        home = parts[1].strip()
                        return (home, away)

                    home = parts[0].strip()
                    away = parts[1].strip()
                    return (home, away)

        return (None, None)

    def _determine_selection_key(
        self,
        selection_name: str,
        home_team: Optional[str],
        away_team: Optional[str]
    ) -> str:
        """
        Determine if selection is home, away, or draw.

        Uses fuzzy matching with team name normalization.
        """
        selection_lower = self._normalize_team_name(selection_name)

        # Check for draw
        if selection_lower in ['draw', 'tie', 'the draw']:
            return 'draw'

        # Match with home team
        if home_team:
            home_normalized = self._normalize_team_name(home_team)
            if self._teams_match(selection_lower, home_normalized):
                return 'home'

        # Match with away team
        if away_team:
            away_normalized = self._normalize_team_name(away_team)
            if self._teams_match(selection_lower, away_normalized):
                return 'away'

        return 'other'

    def _normalize_team_name(self, name: str) -> str:
        """
        Normalize team name for matching.

        Handles:
        - Case insensitivity
        - Common abbreviations (Man United, Spurs, etc.)
        - Extra whitespace
        - Special characters
        """
        if not name:
            return ""

        # Convert to lowercase
        normalized = name.lower().strip()

        # Remove extra whitespace
        normalized = ' '.join(normalized.split())

        # Apply mapping for known variations
        normalized = self.team_name_mapping.get(normalized, normalized)

        return normalized

    def _teams_match(self, name1: str, name2: str) -> bool:
        """
        Check if two team names match.

        Uses fuzzy matching to handle slight variations.
        """
        if name1 == name2:
            return True

        # Check if one name is contained in the other
        if name1 in name2 or name2 in name1:
            return True

        # Check if first word matches (e.g., "Liverpool" matches "Liverpool FC")
        name1_first = name1.split()[0] if name1 else ""
        name2_first = name2.split()[0] if name2 else ""

        if len(name1_first) > 3 and len(name2_first) > 3:
            if name1_first == name2_first:
                return True

        return False

    def _create_failed_result(self, started_at: datetime, errors: List[str]) -> ScrapeResult:
        """Create a failed ScrapeResult"""
        return ScrapeResult(
            bookmaker_code=self.bookmaker_code,
            status=ScraperStatus.FAILED,
            events_scraped=0,
            odds_scraped=0,
            events=[],
            errors=errors,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc)
        )

    def parse_event(self, event_data: Any) -> ScrapedEvent:
        """Required abstract method - not used in Playwright implementation"""
        raise NotImplementedError("Use _parse_betfair_item instead")

    def parse_odds(self, odds_data: Any, event: ScrapedEvent) -> List[ScrapedOdds]:
        """Required abstract method - not used in Playwright implementation"""
        raise NotImplementedError("Use _parse_betfair_item instead")
