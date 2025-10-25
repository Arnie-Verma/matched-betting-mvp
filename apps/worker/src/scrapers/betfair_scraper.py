"""
Betfair Exchange scraper using Playwright for web scraping.

This scraper navigates to Betfair's Australian Exchange website and intercepts
network requests to capture odds data. No API authentication required.

Targets: https://www.betfair.com.au/exchange/plus/football
"""
import asyncio
import json
import re
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

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            bookmaker_code="betfair",
            base_url="https://www.betfair.com.au",
            config=config
        )

        # Betfair Exchange URLs
        self.exchange_base = "https://www.betfair.com.au/exchange/plus"

        # Competition URLs mapping
        # OPTIMIZED: Only scrape EPL for speed (can add more later)
        self.competition_urls = {
            "soccer": {
                "English Premier League": f"{self.exchange_base}/football/competition/10932509",
                # Disabled for speed - add back if needed:
                # "UEFA Champions League": f"{self.exchange_base}/football/competition/228",
                # "La Liga": f"{self.exchange_base}/football/competition/117",
            },
            "afl": {
                "AFL": f"{self.exchange_base}/australian-rules/competition/11897406"
            },
            "nrl": {
                "NRL": f"{self.exchange_base}/rugby-league/competition/10139818"
            }
        }

        # Captured network data
        self.captured_data: List[Dict] = []

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

        Args:
            sport: Our sport code ("soccer", "afl", etc.)
            limit: Max events to scrape

        Returns:
            ScrapeResult with events and lay odds
        """
        started_at = datetime.now(timezone.utc)
        events = []
        errors = []

        try:
            if sport not in self.competition_urls:
                errors.append(f"Unsupported sport: {sport}")
                return self._create_failed_result(started_at, errors)

            self.logger.info(f"Starting Betfair scrape for {sport} using Playwright")

            # Run Playwright scraping
            events = await self._scrape_with_playwright(sport, limit)

            if not events:
                errors.append("No events captured from Betfair")

        except Exception as e:
            errors.append(f"Betfair scrape failed: {str(e)}")
            self.logger.exception(f"Betfair Playwright error for {sport}")

        # Calculate stats
        total_odds = sum(len(event.odds) for event in events)
        status = ScraperStatus.SUCCESS if not errors else (
            ScraperStatus.PARTIAL if events else ScraperStatus.FAILED
        )

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

        self.log_scrape_stats(result)
        return result

    async def _get_or_create_browser(self):
        """Get existing browser instance or create new one (singleton pattern)"""
        import time

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
            self.logger.info("⏱️  [Betfair] Reusing existing browser instance (FAST!)")

        return BetfairScraper._browser

    async def _scrape_with_playwright(self, sport: str, limit: Optional[int]) -> List[ScrapedEvent]:
        """Use Playwright to scrape Betfair Exchange (with browser reuse)"""
        import time
        events = []

        # Clear captured data from previous scrapes (prevent memory accumulation)
        self.captured_data = []

        # Get or reuse browser instance (HUGE speedup on subsequent runs)
        browser = await self._get_or_create_browser()

        try:
            # Create NEW context for each scrape (contexts are lightweight)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-AU',
                timezone_id='Australia/Sydney'
            )

            page = await context.new_page()

            # Set up network interception
            page.on('response', lambda response: asyncio.create_task(
                self._handle_response(response)
            ))

            # Navigate to EPL page (hardcoded for now)
            competitions = self.competition_urls.get(sport, {})
            for comp_name, url in competitions.items():
                comp_start = time.time()
                self.logger.info(f"⏱️  [Betfair] Navigating to {comp_name}: {url}")

                try:
                    # Navigate with domcontentloaded (MUCH faster than networkidle)
                    # domcontentloaded = HTML parsed, but may still be loading resources
                    # networkidle = all network requests finished (slower but more reliable)
                    nav_start = time.time()
                    await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                    nav_time = time.time() - nav_start
                    self.logger.info(f"⏱️  [Betfair] Page load (domcontentloaded) took {nav_time:.2f}s")

                    # OPTIMIZED: Wait only 500ms for critical API calls (not 2000ms!)
                    # The APIs we need usually respond within 500ms after domcontentloaded
                    wait_start = time.time()
                    await page.wait_for_timeout(500)  # Reduced from 2000ms to 500ms
                    wait_time = time.time() - wait_start
                    self.logger.info(f"⏱️  [Betfair] Wait after page load took {wait_time:.2f}s")

                    # REMOVED: Scroll and click operations - they don't capture more data
                    # The bymarket API calls happen automatically after page load
                    # Clicking/scrolling doesn't trigger additional useful API calls

                    comp_time = time.time() - comp_start
                    self.logger.info(f"⏱️  [Betfair] {comp_name} took {comp_time:.2f}s - captured {len(self.captured_data)} network responses")

                except Exception as e:
                    self.logger.error(f"Failed to load {comp_name}: {e}")
                    continue

            # Parse captured data into events
            parse_start = time.time()
            events = self._parse_captured_data(sport, limit)
            parse_time = time.time() - parse_start
            self.logger.info(f"⏱️  [Betfair] Parsing took {parse_time:.2f}s - {len(events)} events")

        finally:
            # Close context (lightweight), but KEEP browser running
            await context.close()

        return events

    async def _handle_response(self, response: Response):
        """Handle intercepted network responses"""
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
                        # Try to parse JSON response
                        content_type = response.headers.get('content-type', '')
                        if 'application/json' in content_type:
                            data = await response.json()

                            self.captured_data.append({
                                'url': url,
                                'data': data,
                                'timestamp': datetime.now(timezone.utc)
                            })

                            self.logger.debug(f"Captured data from: {url[:100]}...")

                    except Exception as e:
                        self.logger.debug(f"Could not parse response from {url[:100]}: {e}")

        except Exception as e:
            self.logger.debug(f"Error handling response: {e}")

    def _parse_captured_data(self, sport: str, limit: Optional[int]) -> List[ScrapedEvent]:
        """Parse captured network data into ScrapedEvent objects"""
        events_dict: Dict[str, ScrapedEvent] = {}  # Key by event ID
        fixtures_data = None
        bymarket_events = {}  # event_id -> event_data with markets

        self.logger.info(f"Parsing {len(self.captured_data)} captured responses")

        # First pass: identify fixtures and bymarket data
        for capture in self.captured_data:
            try:
                url = capture['url']
                data = capture['data']

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
                                    # Only store if we don't already have this event, OR if this one has better data
                                    # Some bymarket responses have full event data, others just have market prices
                                    if event_id not in bymarket_events:
                                        bymarket_events[event_id] = event_node
                                        self.logger.debug(f"Stored new event {event_id}")
                                    else:
                                        # If existing entry has no 'event' key but new one does, replace it
                                        existing_has_event = 'event' in bymarket_events[event_id]
                                        new_has_event = 'event' in event_node
                                        if new_has_event and not existing_has_event:
                                            bymarket_events[event_id] = event_node
                                            self.logger.debug(f"Updated event {event_id} with better data")
                                        else:
                                            self.logger.debug(f"Skipped duplicate event {event_id}")

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

        bymarket_events structure:
        {
            "34782800": {
                "eventId": 34782800,
                "event": {
                    "eventName": "Man City v Everton",
                    "countryCode": "GB",
                    "openDate": "2025-10-18T14:00:00.000Z"
                },
                "marketNodes": [{
                    "marketId": "1.248324306",
                    "description": {"marketName": "Match Odds"},
                    "runners": [{"description": {"runnerName": "Man City"}, "exchange": {"availableToLay": [...]}}]
                }]
            }
        }
        """
        events = []

        self.logger.info(f"Parsing {len(bymarket_events)} events from bymarket data")

        for event_id, event_node in bymarket_events.items():
            try:
                # Extract event metadata
                event_data = event_node.get('event', {})
                event_name = event_data.get('eventName', '')
                open_date = event_data.get('openDate', '')

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

                # Get competition from fixtures data if available
                competition = self._get_competition_for_event(event_id, fixtures_data)

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

                    if market_type == 'MATCH_ODDS':
                        # Parse odds from this market
                        market_odds = self._parse_market_prices(market_node, event, market_name)
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

    def _get_competition_for_event(self, event_id: str, fixtures_data: Optional[Dict]) -> str:
        """Try to get competition name from fixtures data"""
        if not fixtures_data:
            return "Unknown"

        # Look through fixtures by date to find matching event
        fixtures_by_date = fixtures_data.get("fixtures", {})
        for date_str, date_fixtures in fixtures_by_date.items():
            for fixture in date_fixtures:
                if str(fixture.get("eventId", "")) == event_id:
                    # Try to map competition ID to name
                    comp_id = fixture.get("competitionId")
                    if comp_id == 10932509:
                        return "English Premier League"
                    elif comp_id == 228:
                        return "UEFA Champions League"
                    elif comp_id == 117:
                        return "La Liga"
                    else:
                        return f"Competition {comp_id}"

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

            if event_id and market_type == "MATCH_ODDS":
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
                    decimal_odds=Decimal(str(lay_odds)),
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
