"""
Ladbrokes (ladbrokes.com.au) scraper for Australian sports betting odds.

Uses Playwright to navigate to Ladbrokes sports pages and intercept API responses.
The Ladbrokes API requires browser context (cookies/headers) for most sports.

API Endpoint: https://api.ladbrokes.com.au/v2/sport/event-request?category_ids=[CATEGORY_ID]
Response: JSON with events, markets, prices, entrants as separate dicts keyed by ID
Odds: Fractional format (numerator/denominator) - converted to decimal
"""
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import logging
from playwright.async_api import async_playwright, Response

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

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            bookmaker_code="ladbrokes",
            base_url="https://www.ladbrokes.com.au",
            config=config
        )
        self.captured_data: List[Dict] = []

    async def _get_or_create_browser(self):
        """Get or create shared browser instance"""
        import time

        if LadbrokesScraper._browser is None:
            browser_start = time.time()
            self.logger.info("⏱️  [Ladbrokes] Launching browser (first time)...")

            LadbrokesScraper._playwright = await async_playwright().start()
            LadbrokesScraper._browser = await LadbrokesScraper._playwright.chromium.launch(
                headless=True
            )

            browser_launch_time = time.time() - browser_start
            self.logger.info(f"⏱️  [Ladbrokes] Browser launch took {browser_launch_time:.2f}s")
        else:
            self.logger.info("⏱️  [Ladbrokes] Reusing existing browser instance (FAST!)")

        return LadbrokesScraper._browser

    async def scrape_sport(self, sport: str, limit: Optional[int] = None) -> ScrapeResult:
        """
        Scrape Ladbrokes for a specific sport using Playwright.
        """
        import time
        started_at = datetime.now(timezone.utc)
        all_events = []
        errors = []

        sport_url = self.SPORT_URLS.get(sport)
        if not sport_url:
            error_msg = f"Unsupported sport: {sport}"
            self.logger.error(f"[{self.bookmaker_code}] {error_msg}")
            errors.append(error_msg)
            return self._create_failed_result(started_at, errors)

        try:
            self.logger.info(f"[{self.bookmaker_code}] Starting scrape: {sport}")

            # Clear captured data from previous scrapes
            self.captured_data = []

            # Get or reuse browser instance
            browser = await self._get_or_create_browser()

            # Create new context for this scrape
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-AU',
                timezone_id='Australia/Sydney'
            )

            page = await context.new_page()

            # Set up network interception
            async def handle_response(response: Response):
                await self._handle_response(response)

            page.on('response', lambda res: asyncio.create_task(handle_response(res)))

            try:
                # Navigate to sport page
                nav_start = time.time()
                self.logger.info(f"⏱️  [Ladbrokes] Navigating to {sport_url}")
                await page.goto(sport_url, wait_until='domcontentloaded', timeout=20000)
                nav_time = time.time() - nav_start
                self.logger.info(f"⏱️  [Ladbrokes] Page load took {nav_time:.2f}s")

                # Wait for API calls to complete
                await page.wait_for_timeout(5000)

                # Wait for async response handlers
                await asyncio.sleep(1)

                self.logger.info(f"⏱️  [Ladbrokes] Captured {len(self.captured_data)} API responses")

                # Parse captured data
                if self.captured_data:
                    for data in self.captured_data:
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
                            f"[{self.bookmaker_code}] Filtered {len(all_events)} → {len(filtered_events)} events "
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
                            f"[{self.bookmaker_code}] {comp}: {stats['events']} events, {stats['odds']} odds"
                        )
                else:
                    self.logger.warning(f"[{self.bookmaker_code}] No API data captured for {sport}")
                    errors.append(f"No API data captured for {sport}")

            finally:
                await context.close()

        except Exception as e:
            error_msg = f"Scrape error: {str(e)}"
            self.logger.exception(f"[{self.bookmaker_code}] Fatal error for {sport}")
            errors.append(error_msg)

        # Calculate stats
        total_odds = sum(len(event.odds) for event in all_events)
        status = ScraperStatus.SUCCESS if not errors else (
            ScraperStatus.PARTIAL if all_events else ScraperStatus.FAILED
        )

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

        self.log_scrape_stats(result)
        return result

    async def _handle_response(self, response: Response):
        """Handle intercepted network responses"""
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
                            self.captured_data.append(data)
                            self.logger.info(f"✓ Captured Ladbrokes data: {events_count} events")
                except Exception as e:
                    self.logger.debug(f"Could not parse response: {e}")

        except Exception as e:
            self.logger.debug(f"Error handling response: {e}")

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
