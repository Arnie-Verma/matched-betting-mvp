"""
Ladbrokes (ladbrokes.com.au) scraper for Australian sports betting odds.

Uses Playwright to navigate to Ladbrokes sports pages and intercept API responses.
The Ladbrokes API requires browser context (cookies/headers) for most sports.

API Endpoint: https://api.ladbrokes.com.au/v2/sport/event-request?category_ids=[CATEGORY_ID]
Response: JSON with events, markets, prices, entrants as separate dicts keyed by ID
Odds: Fractional format (numerator/denominator) - converted to decimal

PARALLELIZATION NOTES (Phase 1 Production Optimization):
- Each scrape_sport() call uses isolated captured_data via closure pattern
- This allows multiple sports to be scraped in parallel without race conditions
- Use scrape_all_sports_parallel() for optimal performance (6x speedup)

DYNAMIC WAITS (Phase 2 Production Optimization):
- Replaced fixed 5s waits with smart networkidle detection
- Fast APIs (boxing, NBL) complete in 2-3s instead of 8s
- Saves 2-4s per sport, significant at scale
"""
import asyncio
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Callable
import logging
from playwright.async_api import async_playwright, Response, Page

from .base import BaseScraper, ScrapeResult, ScrapedEvent, ScrapedOdds, ScraperStatus

logger = logging.getLogger(__name__)


class LadbrokesScraper(BaseScraper):
    """
    Scraper for Ladbrokes (ladbrokes.com.au) using Playwright.

    Approach:
    1. Launch headless browser (reused across scrapes)
    2. Navigate to sport-specific page
    3. Intercept API responses containing event data
    4. Parse JSON responses to extract events, markets, and odds
    """

    # Class-level browser instance (shared across all scrapes)
    _browser = None
    _playwright = None
    _browser_lock = None  # Asyncio lock for browser creation (initialized lazily)

    # Sport page URLs
    SPORT_URLS = {
        "soccer": "https://www.ladbrokes.com.au/sports/soccer",
        "afl": "https://www.ladbrokes.com.au/sports/australian-rules",
        "nrl": "https://www.ladbrokes.com.au/sports/rugby-league",
        "basketball": "https://www.ladbrokes.com.au/sports/basketball",
        "ice_hockey": "https://www.ladbrokes.com.au/sports/ice-hockey",
        "boxing": "https://www.ladbrokes.com.au/sports/boxing",
    }

    # Competition name mapping for 14 target sports
    # Note: Use EXACT names as returned by Ladbrokes API
    COMPETITION_FILTERS = {
        "soccer": [
            "Premier League",  # Ladbrokes API returns "Premier League" for EPL
            "English Premier League",  # TAB/Betfair use this
            "A-League Men",
            "A-League Women",
            "Spanish La Liga",
            "German Bundesliga",
            "German Bundesliga Women",
            "Italian Serie A",
            "French Ligue 1",
            "UEFA Champions League",
            "Major League Soccer",
        ],
        "afl": ["AFL"],
        "nrl": ["NRL"],
        "basketball": ["NBA", "NBL"],
        "ice_hockey": ["NHL"],
        "boxing": ["Upcoming Fights"]  # Ladbrokes boxing competition name
    }

    # All supported sports for parallel scraping
    ALL_SPORTS = ["soccer", "basketball", "ice_hockey", "boxing", "afl", "nrl"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            bookmaker_code="ladbrokes",
            base_url="https://www.ladbrokes.com.au",
            config=config
        )
        # NOTE: captured_data is NO LONGER used as instance variable
        # Each scrape_sport() call uses local captured_data via closure pattern
        # This enables safe parallel execution of multiple sports

    async def _get_or_create_browser(self):
        """
        Get or create shared browser instance.

        Uses asyncio lock to prevent race conditions when multiple
        parallel calls try to create the browser simultaneously.
        """
        # Initialize lock lazily (must be done inside async context)
        if LadbrokesScraper._browser_lock is None:
            LadbrokesScraper._browser_lock = asyncio.Lock()

        async with LadbrokesScraper._browser_lock:
            if LadbrokesScraper._browser is None:
                browser_start = time.time()
                self.logger.info("⏱️  [Ladbrokes] Launching browser (first time)...")

                LadbrokesScraper._playwright = await async_playwright().start()
                LadbrokesScraper._browser = await LadbrokesScraper._playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )

                browser_launch_time = time.time() - browser_start
                self.logger.info(f"⏱️  [Ladbrokes] Browser launch took {browser_launch_time:.2f}s")
            else:
                self.logger.debug("⏱️  [Ladbrokes] Reusing existing browser instance")

        return LadbrokesScraper._browser

    async def scrape_sport(self, sport: str, limit: Optional[int] = None) -> ScrapeResult:
        """
        Scrape Ladbrokes for a specific sport using Playwright.

        PARALLELIZATION SAFE: Uses closure pattern for captured_data.
        Multiple calls can run concurrently without race conditions.
        """
        started_at = datetime.now(timezone.utc)
        scrape_start = time.time()
        all_events = []
        errors = []

        sport_url = self.SPORT_URLS.get(sport)
        if not sport_url:
            error_msg = f"Unsupported sport: {sport}"
            self.logger.error(f"[{self.bookmaker_code}] {error_msg}")
            errors.append(error_msg)
            return self._create_failed_result(started_at, errors)

        # LOCAL captured_data - isolated per call via closure
        # This is the key fix for parallel execution safety
        captured_data: List[Dict] = []

        try:
            self.logger.info(f"[{self.bookmaker_code}] Starting scrape: {sport}")

            # Get or reuse browser instance
            browser = await self._get_or_create_browser()

            # Create new context for this scrape (isolates cookies/cache)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-AU',
                timezone_id='Australia/Sydney'
            )

            page = await context.new_page()

            # CLOSURE PATTERN: Response handler captures LOCAL captured_data
            # Each scrape_sport() call has its own isolated list
            async def handle_response(response: Response):
                """Handle intercepted network responses - captures local captured_data"""
                try:
                    url = response.url
                    # Look for event-request API calls
                    if response.status == 200 and 'event-request' in url:
                        try:
                            content_type = response.headers.get('content-type', '')
                            if 'application/json' in content_type:
                                data = await response.json()
                                events_count = len(data.get('events', {}))
                                if events_count > 0:
                                    # Append to LOCAL list (not self.captured_data)
                                    captured_data.append(data)
                                    self.logger.info(f"✓ [{sport}] Captured Ladbrokes data: {events_count} events")
                        except Exception as e:
                            self.logger.debug(f"Could not parse response: {e}")
                except Exception as e:
                    self.logger.debug(f"Error handling response: {e}")

            page.on('response', lambda res: asyncio.create_task(handle_response(res)))

            try:
                # Navigate to sport page
                nav_start = time.time()
                self.logger.info(f"⏱️  [Ladbrokes/{sport}] Navigating to {sport_url}")
                await page.goto(sport_url, wait_until='domcontentloaded', timeout=20000)
                nav_time = time.time() - nav_start
                self.logger.info(f"⏱️  [Ladbrokes/{sport}] Page load took {nav_time:.2f}s")

                # PHASE 2: Dynamic wait - poll for captured data instead of fixed 5s
                # This saves 2-4s for fast APIs that respond quickly
                wait_start = time.time()
                max_wait = 8.0  # Maximum wait time in seconds
                poll_interval = 0.3  # Check every 300ms
                data_captured = False

                while (time.time() - wait_start) < max_wait:
                    if captured_data:
                        # Data captured! Wait a bit more for any additional responses
                        await asyncio.sleep(0.5)
                        data_captured = True
                        break
                    await asyncio.sleep(poll_interval)

                wait_time = time.time() - wait_start
                if data_captured:
                    self.logger.info(f"⏱️  [Ladbrokes/{sport}] Data captured after {wait_time:.2f}s (saved {max_wait - wait_time:.1f}s)")
                else:
                    self.logger.info(f"⏱️  [Ladbrokes/{sport}] Max wait reached ({wait_time:.2f}s), no data captured")

                # Brief wait for async response handlers to finish processing
                await asyncio.sleep(0.3)

                self.logger.info(f"⏱️  [Ladbrokes/{sport}] Captured {len(captured_data)} API responses")

                # Parse captured data (using LOCAL list)
                if captured_data:
                    for data in captured_data:
                        events = self._parse_ladbrokes_response(data, sport)
                        all_events.extend(events)

                    # Remove duplicates (by external_id)
                    seen_ids = set()
                    unique_events = []
                    for event in all_events:
                        if event.external_id not in seen_ids:
                            seen_ids.add(event.external_id)
                            unique_events.append(event)
                    all_events = unique_events

                    # Apply competition filters (exact match)
                    competition_filters = self.COMPETITION_FILTERS.get(sport, [])
                    if competition_filters:
                        filter_set = {f.lower() for f in competition_filters}
                        filtered_events = [
                            e for e in all_events
                            if e.competition.lower() in filter_set
                        ]
                        self.logger.info(
                            f"[{self.bookmaker_code}/{sport}] Filtered {len(all_events)} → {len(filtered_events)} events "
                            f"(keeping: {', '.join(competition_filters)})"
                        )
                        all_events = filtered_events

                    if limit:
                        all_events = all_events[:limit]

                    # Log per-competition stats
                    competitions = {}
                    for event in all_events:
                        comp = event.competition
                        if comp not in competitions:
                            competitions[comp] = {"events": 0, "odds": 0}
                        competitions[comp]["events"] += 1
                        competitions[comp]["odds"] += len(event.odds)

                    for comp, stats in competitions.items():
                        self.logger.info(
                            f"[{self.bookmaker_code}/{sport}] {comp}: {stats['events']} events, {stats['odds']} odds"
                        )
                else:
                    self.logger.warning(f"[{self.bookmaker_code}/{sport}] No API data captured")
                    errors.append(f"No API data captured for {sport}")

            finally:
                await context.close()

        except Exception as e:
            error_msg = f"Scrape error: {str(e)}"
            self.logger.exception(f"[{self.bookmaker_code}/{sport}] Fatal error")
            errors.append(error_msg)

        # Calculate stats
        total_odds = sum(len(event.odds) for event in all_events)
        status = ScraperStatus.SUCCESS if not errors else (
            ScraperStatus.PARTIAL if all_events else ScraperStatus.FAILED
        )

        scrape_duration = time.time() - scrape_start
        result = ScrapeResult(
            bookmaker_code=self.bookmaker_code,
            status=status,
            events_scraped=len(all_events),
            odds_scraped=total_odds,
            events=all_events,
            errors=errors,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc)
        )

        self.logger.info(
            f"⏱️  [Ladbrokes/{sport}] Completed in {scrape_duration:.2f}s: "
            f"{len(all_events)} events, {total_odds} odds"
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
            Sequential (batch=1): 6 sports × 8s = 48s
            Batched (batch=3): 2 batches × 8s = ~16s (3x speedup)
            Parallel (batch=6): 1 batch × 8s = ~8s (6x speedup) - production only
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
            f"⏱️  [Ladbrokes] PARALLEL scrape completed in {scrape_duration:.2f}s: "
            f"{total_events_scraped} events, {total_odds_scraped} odds | "
            f"Success: {', '.join(successful_sports) or 'none'} | "
            f"Failed: {', '.join(failed_sports) or 'none'}"
        )

        return combined_result

    # NOTE: _handle_response() method REMOVED - replaced by inline closure in scrape_sport()
    # This enables parallel execution safety (each call has its own captured_data list)

    def _parse_ladbrokes_response(self, data: Dict, sport: str) -> List[ScrapedEvent]:
        """
        Parse Ladbrokes API response into ScrapedEvent objects.

        Response structure:
        {
            "events": {event_id: {name, competition, start, ...}},
            "markets": {market_id: {name, event_id, entrant_ids, ...}},
            "prices": {entrant_id: {odds: {numerator, denominator}}},
            "entrants": {entrant_id: {name, market_id, ...}}
        }
        """
        events = []

        events_data = data.get("events", {})
        markets_data = data.get("markets", {})
        prices_data = data.get("prices", {})
        entrants_data = data.get("entrants", {})

        self.logger.info(f"[{self.bookmaker_code}] Raw API data: {len(events_data)} events, {len(markets_data)} markets, {len(prices_data)} prices, {len(entrants_data)} entrants")

        # Track parsing stats
        events_parsed = 0
        events_with_match_winner = 0
        events_with_odds = 0
        sample_competitions = set()

        for event_id, event_data in events_data.items():
            try:
                events_parsed += 1

                # Parse event metadata
                event_name = event_data.get("name", "Unknown Event")
                competition_data = event_data.get("competition", {})
                competition = competition_data.get("name", "Unknown Competition")
                advertised_start = event_data.get("advertised_start", "")

                # Track sample competitions (first 10)
                if len(sample_competitions) < 10:
                    sample_competitions.add(competition)

                # Parse start time
                try:
                    if isinstance(advertised_start, str):
                        start_time = datetime.fromisoformat(advertised_start.replace("Z", "+00:00"))
                    else:
                        start_time = datetime.now(timezone.utc) + timedelta(days=1)
                except:
                    start_time = datetime.now(timezone.utc) + timedelta(days=1)

                # Extract home/away teams from participants
                participant_ids = event_data.get("participant_ids", [])
                event_participants = data.get("event_participants", {})
                home_team = None
                away_team = None

                if len(participant_ids) >= 2:
                    home_participant = event_participants.get(participant_ids[0], {})
                    away_participant = event_participants.get(participant_ids[1], {})
                    home_team = home_participant.get("name")
                    away_team = away_participant.get("name")

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
                event_markets = [m for m in markets_data.values() if m.get("event_id") == event_id]
                has_match_winner = False

                for market in event_markets:
                    market_name = market.get("name", "Unknown Market")
                    market_type = self.normalize_market_type(market_name)

                    # Only scrape Match Result / H2H markets
                    if market_type != "match_winner":
                        continue

                    has_match_winner = True
                    market_id = market.get("id")
                    entrant_ids = market.get("entrant_ids", [])

                    # Parse odds for each entrant (home/away/draw)
                    for entrant_id in entrant_ids:
                        entrant = entrants_data.get(entrant_id, {})
                        entrant_name = entrant.get("name", "Unknown")

                        # CRITICAL FIX: Prices dict uses a different market ID than markets dict
                        # Search for price keys that match this entrant_id
                        price_found = False
                        for price_key, price_data in prices_data.items():
                            # Price key format: {entrant_id}:{hidden_market_id}:
                            if price_key.startswith(f"{entrant_id}:"):
                                odds_data = price_data.get("odds", {})
                                numerator = odds_data.get("numerator")
                                denominator = odds_data.get("denominator")

                                if not numerator or not denominator:
                                    continue

                                try:
                                    decimal_odds = Decimal(numerator) / Decimal(denominator) + Decimal("1")
                                except:
                                    self.logger.warning(
                                        f"[{self.bookmaker_code}] Invalid odds: {numerator}/{denominator}"
                                    )
                                    continue

                                # Determine selection key
                                selection_key = self._get_selection_key(entrant_name, event)

                                # Create odds
                                odds = ScrapedOdds(
                                    event_external_id=event_id,
                                    event_name=event_name,
                                    sport=sport,
                                    competition=competition,
                                    start_time=start_time,
                                    market_type=market_type,
                                    market_name=market_name,
                                    selection_name=entrant_name,
                                    selection_key=selection_key,
                                    decimal_odds=decimal_odds.quantize(Decimal("0.01")),
                                    bookmaker_code=self.bookmaker_code,
                                    source_url=f"{self.base_url}/sports/event/{event_id}",
                                    scraped_at=datetime.now(timezone.utc)
                                )

                                event.odds.append(odds)
                                price_found = True
                                break  # Found price for this entrant, move to next entrant

                        if not price_found and len(event.odds) < 1:  # Only log for first entrant
                            self.logger.debug(
                                f"[{self.bookmaker_code}] No price found for entrant {entrant_id} ({entrant_name})"
                            )

                # Track stats
                if has_match_winner:
                    events_with_match_winner += 1

                # Only add event if it has odds
                if event.odds:
                    events_with_odds += 1
                    events.append(event)

            except Exception as e:
                self.logger.error(f"[{self.bookmaker_code}] Failed to parse event {event_id}: {e}")
                continue

        # Log parsing statistics
        self.logger.info(
            f"[{self.bookmaker_code}] Parsing stats: "
            f"parsed={events_parsed}, "
            f"with_match_winner={events_with_match_winner}, "
            f"with_odds={events_with_odds}, "
            f"final_events={len(events)}"
        )
        self.logger.info(
            f"[{self.bookmaker_code}] Sample competitions: {', '.join(sorted(sample_competitions))}"
        )

        return events

    def _get_selection_key(self, selection_name: str, event: ScrapedEvent) -> str:
        """Determine selection key (home/away/draw) from selection name"""
        name_lower = selection_name.lower()

        # Check for draw
        if name_lower in ["draw", "tie"]:
            return "draw"

        # Match with home team
        if event.home_team and event.home_team.lower() in name_lower:
            return "home"

        # Match with away team
        if event.away_team and event.away_team.lower() in name_lower:
            return "away"

        return "other"

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
        """Required abstract method - not used in this implementation"""
        raise NotImplementedError("Use _parse_ladbrokes_response instead")

    def parse_odds(self, odds_data: Any, event: ScrapedEvent) -> List[ScrapedOdds]:
        """Required abstract method - not used in this implementation"""
        raise NotImplementedError("Use _parse_ladbrokes_response instead")
