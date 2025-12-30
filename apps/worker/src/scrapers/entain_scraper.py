"""
Entain Platform Scraper - Covers Ladbrokes, Neds, Unibet (AU)

All three bookmakers run on the same Entain platform with identical API structure.
The only difference is the base URL:
- Ladbrokes: https://www.ladbrokes.com.au
- Neds: https://www.neds.com.au
- Unibet: https://www.unibet.com.au

This scraper is config-driven - pass different base_url to scrape different bookmakers.

API Endpoint Pattern:
  {base_url}/sports/{sport} - Triggers API calls intercepted by Playwright

Response Structure:
  {events: {}, markets: {}, prices: {}, entrants: {}}
  Odds: Fractional (numerator/denominator) -> converted to decimal

PRODUCTION NOTES:
- Uses Playwright network interception (not direct API calls)
- Closure pattern for parallel execution safety
- Shared browser instance across scrapes (performance optimization)
- Dynamic waits to minimize scrape time
"""
import asyncio
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import logging
from playwright.async_api import async_playwright, Response

from .base import BaseScraper, ScrapeResult, ScrapedEvent, ScrapedOdds, ScraperStatus

logger = logging.getLogger(__name__)


class EntainScraper(BaseScraper):
    """
    Scraper for Entain platform bookmakers (Ladbrokes, Neds, Unibet AU).

    Config-driven: Pass bookmaker_code and base_url to target different bookmakers.
    All use identical API structure - only domain differs.

    Usage:
        # Ladbrokes
        scraper = EntainScraper("ladbrokes", "https://www.ladbrokes.com.au")

        # Neds
        scraper = EntainScraper("neds", "https://www.neds.com.au")

        # Unibet
        scraper = EntainScraper("unibet", "https://www.unibet.com.au")
    """

    # Class-level browser instance (shared across ALL Entain scrapers)
    _browser = None
    _playwright = None
    _browser_lock = None

    # Sport URL paths (appended to base_url)
    SPORT_PATHS = {
        "soccer": "/sports/soccer",
        "afl": "/sports/australian-rules",
        "nrl": "/sports/rugby-league",
        "basketball": "/sports/basketball",
        "ice_hockey": "/sports/ice-hockey",
        "boxing": "/sports/boxing",
    }

    # Competition filters for target sports
    COMPETITION_FILTERS = {
        "soccer": [
            "Premier League",
            "English Premier League",
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
        "boxing": ["Upcoming Fights"]
    }

    ALL_SPORTS = ["soccer", "basketball", "ice_hockey", "boxing", "afl", "nrl"]

    def __init__(
        self,
        bookmaker_code: str,
        base_url: str,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Entain scraper for a specific bookmaker.

        Args:
            bookmaker_code: Unique code (ladbrokes, neds, unibet)
            base_url: Bookmaker's base URL (e.g., https://www.ladbrokes.com.au)
            config: Optional additional configuration
        """
        super().__init__(
            bookmaker_code=bookmaker_code,
            base_url=base_url,
            config=config or {}
        )
        self.logger.info(f"[{self.bookmaker_code}] Initialized EntainScraper with base_url: {base_url}")

    async def _get_or_create_browser(self):
        """
        Get or create shared browser instance.

        Uses asyncio lock to prevent race conditions when multiple
        parallel calls try to create the browser simultaneously.
        Browser is shared across ALL Entain scraper instances.
        """
        if EntainScraper._browser_lock is None:
            EntainScraper._browser_lock = asyncio.Lock()

        async with EntainScraper._browser_lock:
            if EntainScraper._browser is None:
                browser_start = time.time()
                self.logger.info(f"[{self.bookmaker_code}] Launching browser (first time)...")

                EntainScraper._playwright = await async_playwright().start()
                EntainScraper._browser = await EntainScraper._playwright.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )

                browser_launch_time = time.time() - browser_start
                self.logger.info(f"[{self.bookmaker_code}] Browser launch took {browser_launch_time:.2f}s")
            else:
                self.logger.debug(f"[{self.bookmaker_code}] Reusing existing browser instance")

        return EntainScraper._browser

    def _get_sport_url(self, sport: str) -> Optional[str]:
        """Get full URL for a sport page."""
        path = self.SPORT_PATHS.get(sport)
        if not path:
            return None
        return f"{self.base_url}{path}"

    async def scrape_sport(self, sport: str, limit: Optional[int] = None) -> ScrapeResult:
        """
        Scrape a specific sport using Playwright network interception.

        PARALLELIZATION SAFE: Uses closure pattern for captured_data.
        Multiple calls can run concurrently without race conditions.
        """
        started_at = datetime.now(timezone.utc)
        scrape_start = time.time()
        all_events = []
        errors = []

        sport_url = self._get_sport_url(sport)
        if not sport_url:
            error_msg = f"Unsupported sport: {sport}"
            self.logger.error(f"[{self.bookmaker_code}] {error_msg}")
            errors.append(error_msg)
            return self._create_failed_result(started_at, errors)

        # LOCAL captured_data - isolated per call via closure
        captured_data: List[Dict] = []

        try:
            self.logger.info(f"[{self.bookmaker_code}] Starting scrape: {sport}")

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
            async def handle_response(response: Response):
                """Handle intercepted network responses"""
                try:
                    url = response.url
                    if response.status == 200 and 'event-request' in url:
                        try:
                            content_type = response.headers.get('content-type', '')
                            if 'application/json' in content_type:
                                data = await response.json()
                                events_count = len(data.get('events', {}))
                                if events_count > 0:
                                    captured_data.append(data)
                                    self.logger.info(f"[{self.bookmaker_code}/{sport}] Captured API data: {events_count} events")
                        except Exception as e:
                            self.logger.debug(f"Could not parse response: {e}")
                except Exception as e:
                    self.logger.debug(f"Error handling response: {e}")

            page.on('response', lambda res: asyncio.create_task(handle_response(res)))

            try:
                # Navigate to sport page
                nav_start = time.time()
                self.logger.info(f"[{self.bookmaker_code}/{sport}] Navigating to {sport_url}")
                await page.goto(sport_url, wait_until='domcontentloaded', timeout=20000)
                nav_time = time.time() - nav_start
                self.logger.info(f"[{self.bookmaker_code}/{sport}] Page load took {nav_time:.2f}s")

                # Dynamic wait - poll for captured data instead of fixed wait
                wait_start = time.time()
                max_wait = 8.0
                poll_interval = 0.3
                data_captured = False

                while (time.time() - wait_start) < max_wait:
                    if captured_data:
                        await asyncio.sleep(0.5)
                        data_captured = True
                        break
                    await asyncio.sleep(poll_interval)

                wait_time = time.time() - wait_start
                if data_captured:
                    self.logger.info(f"[{self.bookmaker_code}/{sport}] Data captured after {wait_time:.2f}s")
                else:
                    self.logger.info(f"[{self.bookmaker_code}/{sport}] Max wait reached ({wait_time:.2f}s)")

                await asyncio.sleep(0.3)

                self.logger.info(f"[{self.bookmaker_code}/{sport}] Captured {len(captured_data)} API responses")

                # Parse captured data
                if captured_data:
                    for data in captured_data:
                        events = self._parse_entain_response(data, sport)
                        all_events.extend(events)

                    # Remove duplicates
                    seen_ids = set()
                    unique_events = []
                    for event in all_events:
                        if event.external_id not in seen_ids:
                            seen_ids.add(event.external_id)
                            unique_events.append(event)
                    all_events = unique_events

                    # Apply competition filters
                    competition_filters = self.COMPETITION_FILTERS.get(sport, [])
                    if competition_filters:
                        filter_set = {f.lower() for f in competition_filters}
                        filtered_events = [
                            e for e in all_events
                            if e.competition.lower() in filter_set
                        ]
                        self.logger.info(
                            f"[{self.bookmaker_code}/{sport}] Filtered {len(all_events)} -> {len(filtered_events)} events"
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
            f"[{self.bookmaker_code}/{sport}] Completed in {scrape_duration:.2f}s: "
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

        Args:
            sports: List of sports to scrape. Defaults to ALL_SPORTS.
            limit: Optional limit per sport
            batch_size: Number of sports to scrape in parallel (default from env)

        Returns:
            Combined ScrapeResult with all events from all sports
        """
        import os
        if batch_size is None:
            batch_size = int(os.getenv("SCRAPER_BATCH_SIZE", "1"))

        started_at = datetime.now(timezone.utc)
        scrape_start = time.time()

        sports_to_scrape = sports or self.ALL_SPORTS
        self.logger.info(
            f"[{self.bookmaker_code}] Starting PARALLEL scrape of {len(sports_to_scrape)} sports "
            f"(batch_size={batch_size})"
        )

        # Process sports in batches
        all_results = []
        for i in range(0, len(sports_to_scrape), batch_size):
            batch = sports_to_scrape[i:i + batch_size]
            self.logger.info(f"[{self.bookmaker_code}] Processing batch {i//batch_size + 1}: {', '.join(batch)}")

            tasks = [self.scrape_sport(sport, limit=limit) for sport in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            all_results.extend(zip(batch, batch_results))

        # Aggregate results
        all_events = []
        all_errors = []
        total_events_scraped = 0
        total_odds_scraped = 0
        successful_sports = []
        failed_sports = []

        for sport, result in all_results:
            if isinstance(result, Exception):
                error_msg = f"{sport}: {str(result)}"
                all_errors.append(error_msg)
                failed_sports.append(sport)
                self.logger.error(f"[{self.bookmaker_code}] {sport} failed: {result}")
            elif isinstance(result, ScrapeResult):
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
                all_errors.append(f"{sport}: Unexpected result type")
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
            f"[{self.bookmaker_code}] PARALLEL scrape completed in {scrape_duration:.2f}s: "
            f"{total_events_scraped} events, {total_odds_scraped} odds | "
            f"Success: {', '.join(successful_sports) or 'none'} | "
            f"Failed: {', '.join(failed_sports) or 'none'}"
        )

        return combined_result

    def _parse_entain_response(self, data: Dict, sport: str) -> List[ScrapedEvent]:
        """
        Parse Entain API response into ScrapedEvent objects.

        Response structure (identical for Ladbrokes, Neds, Unibet):
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

        self.logger.info(
            f"[{self.bookmaker_code}] Raw API: {len(events_data)} events, "
            f"{len(markets_data)} markets, {len(prices_data)} prices"
        )

        events_parsed = 0
        events_with_match_winner = 0
        events_with_odds = 0

        for event_id, event_data in events_data.items():
            try:
                events_parsed += 1

                event_name = event_data.get("name", "Unknown Event")
                competition_data = event_data.get("competition", {})
                competition = competition_data.get("name", "Unknown Competition")
                advertised_start = event_data.get("advertised_start", "")

                # Parse start time
                try:
                    if isinstance(advertised_start, str):
                        start_time = datetime.fromisoformat(advertised_start.replace("Z", "+00:00"))
                    else:
                        start_time = datetime.now(timezone.utc) + timedelta(days=1)
                except:
                    start_time = datetime.now(timezone.utc) + timedelta(days=1)

                # Extract home/away teams from event name
                home_team = None
                away_team = None

                if " v " in event_name:
                    parts = event_name.split(" v ", 1)
                    if len(parts) == 2:
                        home_team = parts[0].strip()
                        away_team = parts[1].strip()
                elif " vs " in event_name.lower():
                    idx = event_name.lower().find(" vs ")
                    home_team = event_name[:idx].strip()
                    away_team = event_name[idx + 4:].strip()
                elif " @ " in event_name:
                    parts = event_name.split(" @ ", 1)
                    if len(parts) == 2:
                        away_team = parts[0].strip()
                        home_team = parts[1].strip()

                # Fallback to participant data
                if not home_team or not away_team:
                    participant_ids = event_data.get("participant_ids", [])
                    event_participants = data.get("event_participants", {})
                    if len(participant_ids) >= 2:
                        home_participant = event_participants.get(participant_ids[0], {})
                        away_participant = event_participants.get(participant_ids[1], {})
                        home_team = home_team or home_participant.get("name")
                        away_team = away_team or away_participant.get("name")

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

                    if market_type != "match_winner":
                        continue

                    has_match_winner = True
                    entrant_ids = market.get("entrant_ids", [])

                    for entrant_id in entrant_ids:
                        entrant = entrants_data.get(entrant_id, {})
                        entrant_name = entrant.get("name", "Unknown")

                        # Find price for this entrant
                        for price_key, price_data in prices_data.items():
                            if price_key.startswith(f"{entrant_id}:"):
                                odds_data = price_data.get("odds", {})
                                numerator = odds_data.get("numerator")
                                denominator = odds_data.get("denominator")

                                if not numerator or not denominator:
                                    continue

                                try:
                                    decimal_odds = Decimal(numerator) / Decimal(denominator) + Decimal("1")
                                except:
                                    continue

                                selection_key = self._get_selection_key(entrant_name, event)

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
                                break

                if has_match_winner:
                    events_with_match_winner += 1

                if event.odds:
                    events_with_odds += 1
                    events.append(event)

            except Exception as e:
                self.logger.error(f"[{self.bookmaker_code}] Failed to parse event {event_id}: {e}")
                continue

        self.logger.info(
            f"[{self.bookmaker_code}] Parsing: parsed={events_parsed}, "
            f"with_match_winner={events_with_match_winner}, with_odds={events_with_odds}"
        )

        return events

    def _get_selection_key(self, selection_name: str, event: ScrapedEvent) -> str:
        """Determine selection key (home/away/draw) from selection name."""
        name_lower = selection_name.lower().strip()

        if name_lower in ["draw", "the draw", "tie", "x"]:
            return "draw"

        def normalize_team(name: str) -> str:
            if not name:
                return ""
            n = name.lower().strip()
            for suffix in [" fc", " afc", " cf", " sc", " united", " city"]:
                if n.endswith(suffix):
                    n = n[:-len(suffix)].strip()
            return n

        sel_norm = normalize_team(selection_name)
        home_norm = normalize_team(event.home_team) if event.home_team else ""
        away_norm = normalize_team(event.away_team) if event.away_team else ""

        if home_norm and sel_norm == home_norm:
            return "home"
        if away_norm and sel_norm == away_norm:
            return "away"

        if home_norm and (home_norm in sel_norm or sel_norm in home_norm):
            return "home"
        if away_norm and (away_norm in sel_norm or sel_norm in away_norm):
            return "away"

        if event.home_team and event.home_team.lower() in name_lower:
            return "home"
        if event.away_team and event.away_team.lower() in name_lower:
            return "away"

        return "other"

    def _create_failed_result(self, started_at: datetime, errors: List[str]) -> ScrapeResult:
        """Create a failed ScrapeResult."""
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
        """Required abstract method - not used in this implementation."""
        raise NotImplementedError("Use _parse_entain_response instead")

    def parse_odds(self, odds_data: Any, event: ScrapedEvent) -> List[ScrapedOdds]:
        """Required abstract method - not used in this implementation."""
        raise NotImplementedError("Use _parse_entain_response instead")


# Convenience factory functions for each Entain bookmaker
def create_ladbrokes_scraper(config: Optional[Dict[str, Any]] = None) -> EntainScraper:
    """Create Ladbrokes scraper (Entain platform)."""
    return EntainScraper("ladbrokes", "https://www.ladbrokes.com.au", config)


def create_neds_scraper(config: Optional[Dict[str, Any]] = None) -> EntainScraper:
    """Create Neds scraper (Entain platform)."""
    return EntainScraper("neds", "https://www.neds.com.au", config)


def create_unibet_scraper(config: Optional[Dict[str, Any]] = None) -> EntainScraper:
    """Create Unibet AU scraper (Entain platform)."""
    return EntainScraper("unibet", "https://www.unibet.com.au", config)
