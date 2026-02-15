"""
Entain Platform Scraper - Covers Ladbrokes, Neds (AU)

Both bookmakers run on the same Entain platform with identical API structure.
The only difference is the base URL:
- Ladbrokes: https://www.ladbrokes.com.au
- Neds: https://www.neds.com.au

This scraper is config-driven - pass different base_url to scrape different bookmakers.

NOTE:
- Unibet AU is Kindred/FDJ and uses a different API (see KindredScraper).

API Endpoint Patterns (as of Jan 2026):
  GraphQL: {api_base}/graphql or {api_base}/gql/router
  REST v2: {api_base}/rest/v2/...
  Legacy: event-request URLs (may still work)

Response Structure (REST/Legacy):
  {events: {}, markets: {}, prices: {}, entrants: {}}
  Odds: Fractional (numerator/denominator) -> converted to decimal

Response Structure (GraphQL):
  {data: {sports: {edges: [{node: {events: ...}}]}}}
  Odds: Decimal format directly

PRODUCTION NOTES:
- Uses Playwright network interception (not direct API calls)
- Intercepts BOTH GraphQL and REST endpoints for compatibility
- Closure pattern for parallel execution safety
- Shared browser instance across scrapes (performance optimization)
- Dynamic waits to minimize scrape time
"""
import asyncio
import re
import time
import unicodedata
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import logging
from playwright.async_api import async_playwright, Response

from .base import BaseScraper, ScrapeResult, ScrapedEvent, ScrapedOdds, ScraperStatus

logger = logging.getLogger(__name__)


class EntainScraper(BaseScraper):
    """
    Scraper for Entain platform bookmakers (Ladbrokes, Neds).

    Config-driven: Pass bookmaker_code and base_url to target different bookmakers.
    All use identical API structure - only domain differs.

    Usage:
        # Ladbrokes
        scraper = EntainScraper("ladbrokes", "https://www.ladbrokes.com.au")

        # Neds
        scraper = EntainScraper("neds", "https://www.neds.com.au")
    """

    # Class-level browser instance (shared across ALL Entain scrapers)
    _browser = None
    _playwright = None
    _browser_lock = None

    # Competition-specific URL paths (yields events with odds directly)
    # Format: sport_code -> list of (competition_name, url_path) tuples
    COMPETITION_URLS = {
        "soccer": [
            ("Premier League", "/sports/soccer/england-premier-league"),
            ("A-League Men", "/sports/soccer/australia-a-league"),
            ("Spanish La Liga", "/sports/soccer/spain-la-liga"),
            ("German Bundesliga", "/sports/soccer/germany-bundesliga"),
            ("Italian Serie A", "/sports/soccer/italy-serie-a"),
            ("French Ligue 1", "/sports/soccer/france-ligue-1"),
            ("UEFA Champions League", "/sports/soccer/uefa-champions-league"),
            ("Major League Soccer", "/sports/soccer/usa-mls"),
        ],
        "afl": [
            ("AFL", "/sports/australian-rules/afl"),
        ],
        "nrl": [
            ("NRL", "/sports/rugby-league/nrl"),
        ],
        "basketball": [
            ("NBA", "/sports/basketball/usa-nba"),
            ("NBL", "/sports/basketball/australia-nbl"),
        ],
        "ice_hockey": [
            ("NHL", "/sports/ice-hockey/usa-nhl"),
        ],
        "boxing": [
            ("Boxing", "/sports/boxing"),
        ],
    }

    # Legacy sport paths (fallback if competition URLs fail)
    SPORT_PATHS = {
        "soccer": "/sports/soccer",
        "afl": "/sports/australian-rules",
        "nrl": "/sports/rugby-league",
        "basketball": "/sports/basketball",
        "ice_hockey": "/sports/ice-hockey",
        "boxing": "/sports/boxing",
    }

    # Competition filters for target sports (used with legacy approach)
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
        "boxing": ["Upcoming Fights", "Boxing"]
    }

    ALL_SPORTS = ["soccer", "basketball", "ice_hockey", "boxing", "afl", "nrl"]

    # Outrights/futures often appear inside sport landing pages and can pollute
    # per-competition validation (e.g. "Division Of NBA Championship Winner").
    # These are not matchup fixtures and should be excluded from match_winner
    # pipelines for team sports.
    OUTRIGHT_NAME_TOKENS = (
        "winner",
        "championship",
        "division",
        "conference",
        "outright",
        "to win",
        "season",
        "playoff",
        "playoffs",
        "series",
    )

    # Any of these tokens indicate we should not treat a market as fixture
    # match-winner for matcher/validation paths.
    DISALLOWED_MARKET_TOKENS = (
        "futures",
        "outright",
        "championship",
        "conference",
        "division",
        "season",
        "series winner",
        "to make",
        "to qualify",
        "qualify",
        "group winner",
        "winner without",
        "top scorer",
        "points leader",
        "player performance",
        "method of victory",
        "win by",
        "by ko",
        "by tko",
        "by decision",
        "exact score",
        "draw no bet",
        "double chance",
        "both teams to score",
        "corners",
        "cards",
        "first to",
        "race to",
        "half time",
        "halftime",
        "1st half",
        "first half",
        "2nd half",
        "second half",
        "quarter",
        "period",
        "set",
        "innings",
        "map",
    )

    ALLOWED_MARKET_TOKENS_BY_SPORT = {
        "soccer": (
            "match result",
            "match winner",
            "head to head",
            "head-to-head",
            "h2h",
            "1x2",
            "full time result",
            "full-time result",
        ),
        "basketball": (
            "money line",
            "moneyline",
            "head to head",
            "head-to-head",
            "h2h",
            "match winner",
            "to win",
        ),
        "ice_hockey": (
            "money line",
            "moneyline",
            "head to head",
            "head-to-head",
            "h2h",
            "match winner",
            "to win",
        ),
        "boxing": (
            "fight betting",
            "fight result",
            "money line",
            "moneyline",
            "match winner",
            "to win",
        ),
    }

    def _is_matchup_event_name(self, name: str) -> bool:
        if not name:
            return False
        lower = name.lower()
        # Common matchup separators across bookmakers
        return any(sep in lower for sep in (" v ", " vs ", " @ ", " - "))

    def _is_outright_event_name(self, name: str) -> bool:
        if not name:
            return False
        lower = name.lower()
        return any(tok in lower for tok in self.OUTRIGHT_NAME_TOKENS)

    def _expected_selection_keys(self, sport: str) -> tuple:
        if sport == "soccer":
            return ("home", "draw", "away")
        return ("home", "away")

    def _is_matcher_market(self, market_name: str, sport: str) -> bool:
        if not market_name:
            return False

        market_lower = market_name.lower().strip()
        if any(token in market_lower for token in self.DISALLOWED_MARKET_TOKENS):
            return False

        allowed_tokens = self.ALLOWED_MARKET_TOKENS_BY_SPORT.get(sport, ())
        return any(token in market_lower for token in allowed_tokens)

    def _sanitize_market_odds(
        self,
        market_odds: List[ScrapedOdds],
        sport: str,
    ) -> List[ScrapedOdds]:
        expected_keys = self._expected_selection_keys(sport)
        allowed_keys = set(expected_keys)
        by_key: Dict[str, ScrapedOdds] = {}

        for odds in market_odds:
            if odds.selection_key not in allowed_keys:
                continue
            if odds.selection_key not in by_key:
                by_key[odds.selection_key] = odds

        if not all(key in by_key for key in expected_keys):
            return []

        return [by_key[key] for key in expected_keys]

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

        Iterates through competition-specific URLs for the sport to get events with odds.
        """
        started_at = datetime.now(timezone.utc)
        scrape_start = time.time()
        all_events = []
        errors = []

        # Get competition URLs for this sport
        competition_urls = self.COMPETITION_URLS.get(sport, [])
        if not competition_urls:
            # Fallback to legacy sport path
            sport_path = self.SPORT_PATHS.get(sport)
            if sport_path:
                competition_urls = [(sport.upper(), sport_path)]
            else:
                error_msg = f"Unsupported sport: {sport}"
                self.logger.error(f"[{self.bookmaker_code}] {error_msg}")
                errors.append(error_msg)
                return self._create_failed_result(started_at, errors)

        try:
            self.logger.info(f"[{self.bookmaker_code}] Starting scrape: {sport} ({len(competition_urls)} competitions)")

            browser = await self._get_or_create_browser()

            # Create new context for this scrape (isolates cookies/cache)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-AU',
                timezone_id='Australia/Sydney'
            )

            page = await context.new_page()

            try:
                # Iterate through each competition for this sport
                for comp_name, comp_path in competition_urls:
                    comp_url = f"{self.base_url}{comp_path}"

                    # LOCAL captured_data - reset per competition
                    captured_data: List[Dict] = []
                    api_urls_seen: List[str] = []

                    # CLOSURE PATTERN: Response handler captures LOCAL captured_data
                    async def make_handler(cd: List[Dict], urls: List[str], comp: str):
                        async def handle_response(response: Response):
                            """Handle intercepted network responses - supports multiple API patterns"""
                            try:
                                url = response.url
                                if response.status != 200:
                                    return

                                content_type = response.headers.get('content-type', '')

                                # Log API URLs for debugging
                                if 'application/json' in content_type and 'api' in url.lower():
                                    if len(urls) < 10:
                                        urls.append(url[:150])

                                if 'application/json' not in content_type:
                                    return

                                # Pattern 1: Legacy event-request URLs
                                if 'event-request' in url:
                                    try:
                                        data = await response.json()
                                        events_count = len(data.get('events', {}))
                                        if events_count > 0:
                                            cd.append({'type': 'legacy', 'data': data, 'competition': comp})
                                            self.logger.info(f"[{self.bookmaker_code}/{comp}] Captured LEGACY: {events_count} events")
                                    except Exception as e:
                                        self.logger.debug(f"Could not parse legacy: {e}")

                                # Pattern 2: GraphQL endpoint
                                elif '/graphql' in url or '/gql/' in url:
                                    try:
                                        data = await response.json()
                                        if data.get('data'):
                                            cd.append({'type': 'graphql', 'data': data, 'competition': comp})
                                            self.logger.info(f"[{self.bookmaker_code}/{comp}] Captured GraphQL")
                                    except Exception as e:
                                        self.logger.debug(f"Could not parse GraphQL: {e}")

                                # Pattern 3: REST v2 sport events
                                elif '/rest/v2/' in url and ('sport' in url or 'event' in url or 'competition' in url):
                                    try:
                                        data = await response.json()
                                        cd.append({'type': 'rest_v2', 'data': data, 'competition': comp})
                                        self.logger.info(f"[{self.bookmaker_code}/{comp}] Captured REST v2")
                                    except Exception as e:
                                        self.logger.debug(f"Could not parse REST v2: {e}")

                                # Pattern 4: v2 API with events
                                elif '/v2/' in url and 'event' in url.lower():
                                    try:
                                        data = await response.json()
                                        if isinstance(data, dict) and (data.get('events') or data.get('data')):
                                            cd.append({'type': 'v2_events', 'data': data, 'competition': comp})
                                            self.logger.info(f"[{self.bookmaker_code}/{comp}] Captured v2 events")
                                    except Exception as e:
                                        self.logger.debug(f"Could not parse v2 events: {e}")

                            except Exception as e:
                                self.logger.debug(f"Error handling response: {e}")
                        return handle_response

                    # Set up handler for this competition
                    handler = await make_handler(captured_data, api_urls_seen, comp_name)
                    page.on('response', lambda res, h=handler: asyncio.create_task(h(res)))

                    # Navigate to competition page
                    nav_start = time.time()
                    self.logger.info(f"[{self.bookmaker_code}/{comp_name}] Navigating to {comp_url}")

                    try:
                        await page.goto(comp_url, wait_until='domcontentloaded', timeout=20000)
                    except Exception as nav_error:
                        self.logger.warning(f"[{self.bookmaker_code}/{comp_name}] Navigation failed: {nav_error}")
                        errors.append(f"{comp_name}: navigation failed")
                        continue

                    nav_time = time.time() - nav_start
                    self.logger.info(f"[{self.bookmaker_code}/{comp_name}] Page load: {nav_time:.2f}s")

                    # Wait for data - need enough time for legacy API to respond
                    # Legacy event-request often comes after GraphQL, so wait longer
                    wait_start = time.time()
                    max_wait = 8.0
                    legacy_captured = False

                    while (time.time() - wait_start) < max_wait:
                        # Check if we have legacy data (preferred)
                        for item in captured_data:
                            if item.get('type') == 'legacy':
                                legacy_captured = True
                                break

                        if legacy_captured:
                            # Give a bit more time for additional data
                            await asyncio.sleep(0.5)
                            break
                        elif captured_data and (time.time() - wait_start) > 4.0:
                            # Have some data but no legacy after 4s, accept what we have
                            await asyncio.sleep(0.3)
                            break

                        await asyncio.sleep(0.3)

                    self.logger.info(f"[{self.bookmaker_code}/{comp_name}] Captured {len(captured_data)} responses (legacy={legacy_captured})")

                    # Parse captured data
                    comp_events = []
                    for item in captured_data:
                        item_type = item.get('type', 'legacy')
                        data = item.get('data', item)

                        if item_type == 'graphql':
                            events = self._parse_graphql_response(data, sport)
                        else:
                            events = self._parse_entain_response(data, sport)

                        # Override competition name with expected name if unknown
                        for e in events:
                            if e.competition == "Unknown Competition":
                                e.competition = comp_name
                        comp_events.extend(events)

                    # Apply competition filter - legacy API returns all competitions
                    # We filter to only the competition we're targeting
                    competition_filters = self.COMPETITION_FILTERS.get(sport, [])
                    if competition_filters and comp_events:
                        filter_set = {f.lower() for f in competition_filters}
                        filtered_events = [
                            e for e in comp_events
                            if e.competition.lower() in filter_set
                        ]
                        if len(filtered_events) < len(comp_events):
                            self.logger.info(
                                f"[{self.bookmaker_code}/{comp_name}] Filtered {len(comp_events)} -> {len(filtered_events)} events"
                            )
                        comp_events = filtered_events

                    if comp_events:
                        self.logger.info(f"[{self.bookmaker_code}/{comp_name}] Parsed {len(comp_events)} events")
                        all_events.extend(comp_events)
                    else:
                        self.logger.warning(f"[{self.bookmaker_code}/{comp_name}] No events parsed (post-filter)")
                        if api_urls_seen:
                            self.logger.debug(f"[{self.bookmaker_code}/{comp_name}] URLs: {api_urls_seen[:5]}")

                    # Small delay between competitions to avoid rate limiting
                    await asyncio.sleep(0.5)

                # Remove duplicates
                seen_ids = set()
                unique_events = []
                for event in all_events:
                    if event.external_id not in seen_ids:
                        seen_ids.add(event.external_id)
                        unique_events.append(event)
                all_events = unique_events

                if limit:
                    all_events = all_events[:limit]

                # Log final stats
                comp_stats = {}
                for event in all_events:
                    comp = event.competition
                    if comp not in comp_stats:
                        comp_stats[comp] = {"events": 0, "odds": 0}
                    comp_stats[comp]["events"] += 1
                    comp_stats[comp]["odds"] += len(event.odds)

                for comp, stats in comp_stats.items():
                    self.logger.info(f"[{self.bookmaker_code}/{sport}] {comp}: {stats['events']} events, {stats['odds']} odds")

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

                # Boxing has no true home/away. Different sources can flip fighter
                # order, which causes odds swaps during cross-bookmaker validation.
                # Enforce deterministic ordering so "home"/"away" selection keys
                # refer to the same fighter across bookmakers.
                if sport == "boxing" and home_team and away_team:
                    left = str(home_team).strip()
                    right = str(away_team).strip()
                    if self._participant_sort_key(right) < self._participant_sort_key(left):
                        left, right = right, left
                    home_team, away_team = left, right
                    event_name = f"{home_team} v {away_team}"

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
                    if not self._is_matcher_market(market_name, sport):
                        continue

                    has_match_winner = True
                    entrant_ids = market.get("entrant_ids", [])
                    market_odds: List[ScrapedOdds] = []

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
                                if selection_key not in {"home", "away", "draw"}:
                                    continue

                                odds = ScrapedOdds(
                                    event_external_id=event_id,
                                    event_name=event_name,
                                    sport=sport,
                                    competition=competition,
                                    start_time=start_time,
                                    market_type="match_winner",
                                    market_name=market_name,
                                    selection_name=entrant_name,
                                    selection_key=selection_key,
                                    decimal_odds=decimal_odds.quantize(Decimal("0.01")),
                                    bookmaker_code=self.bookmaker_code,
                                    source_url=f"{self.base_url}/sports/event/{event_id}",
                                    scraped_at=datetime.now(timezone.utc)
                                )

                                market_odds.append(odds)
                                break

                    event.odds.extend(self._sanitize_market_odds(market_odds, sport))

                if has_match_winner:
                    events_with_match_winner += 1

                if event.odds:
                    events_with_odds += 1
                    events.append(event)

            except Exception as e:
                self.logger.error(f"[{self.bookmaker_code}] Failed to parse event {event_id}: {e}")
                continue

        # Remove outright/futures "events" for team sports. These are not matchups
        # and they distort validation/event coverage calculations.
        if sport in ("basketball", "ice_hockey") and events:
            before = len(events)
            events = [
                e
                for e in events
                if self._is_matchup_event_name(e.name) and not self._is_outright_event_name(e.name)
            ]
            removed = before - len(events)
            if removed > 0:
                self.logger.info(f"[{self.bookmaker_code}] Filtered out {removed} outright/non-match events ({sport})")

        self.logger.info(
            f"[{self.bookmaker_code}] Parsing: parsed={events_parsed}, "
            f"with_match_winner={events_with_match_winner}, with_odds={events_with_odds}"
        )

        return events

    def _parse_graphql_response(self, data: Dict, sport: str) -> List[ScrapedEvent]:
        """
        Parse GraphQL API response into ScrapedEvent objects.

        GraphQL response structure varies but generally:
        {
            "data": {
                "sports" or "competitions" or "events": {
                    "edges": [
                        {"node": {event_data}}
                    ]
                }
            }
        }

        Odds are typically in decimal format directly.
        """
        events = []
        gql_data = data.get("data", {})

        if not gql_data:
            self.logger.warning(f"[{self.bookmaker_code}] Empty GraphQL data")
            return events

        # Log the structure to help debug
        self.logger.info(f"[{self.bookmaker_code}] GraphQL keys: {list(gql_data.keys())}")

        # Try to find events in various possible locations
        event_nodes = []

        # Pattern 1: data.sports.edges[].node.events.edges[].node
        if "sports" in gql_data:
            sports_data = gql_data["sports"]
            for sport_edge in sports_data.get("edges", []):
                sport_node = sport_edge.get("node", {})
                for event_edge in sport_node.get("events", {}).get("edges", []):
                    event_nodes.append(event_edge.get("node", {}))

        # Pattern 2: data.competitions.edges[].node.events.edges[].node
        if "competitions" in gql_data:
            comp_data = gql_data["competitions"]
            for comp_edge in comp_data.get("edges", []):
                comp_node = comp_edge.get("node", {})
                for event_edge in comp_node.get("events", {}).get("edges", []):
                    event_nodes.append(event_edge.get("node", {}))

        # Pattern 3: data.events.edges[].node
        if "events" in gql_data:
            events_data = gql_data["events"]
            for event_edge in events_data.get("edges", []):
                event_nodes.append(event_edge.get("node", {}))

        # Pattern 4: data.eventCards (used on sports landing page)
        if "eventCards" in gql_data:
            for card in gql_data.get("eventCards", []):
                if "event" in card:
                    event_nodes.append(card["event"])
                elif "id" in card and "name" in card:
                    event_nodes.append(card)

        self.logger.info(f"[{self.bookmaker_code}] Found {len(event_nodes)} event nodes in GraphQL")

        for event_data in event_nodes:
            try:
                event_id = str(event_data.get("id", ""))
                event_name = event_data.get("name", "Unknown Event")

                # Get competition info
                competition_data = event_data.get("competition", {}) or {}
                competition = competition_data.get("name", "Unknown Competition")

                # Parse start time
                start_str = event_data.get("startTime") or event_data.get("advertisedStart") or ""
                try:
                    if start_str:
                        start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    else:
                        start_time = datetime.now(timezone.utc) + timedelta(days=1)
                except:
                    start_time = datetime.now(timezone.utc) + timedelta(days=1)

                # Extract teams from event name
                home_team, away_team = self._extract_teams_from_name(event_name)

                if sport == "boxing" and home_team and away_team:
                    left = str(home_team).strip()
                    right = str(away_team).strip()
                    if self._participant_sort_key(right) < self._participant_sort_key(left):
                        left, right = right, left
                    home_team, away_team = left, right
                    event_name = f"{home_team} v {away_team}"

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

                # Parse markets/prices from GraphQL
                markets_data = event_data.get("markets", []) or event_data.get("markets", {}).get("edges", [])

                for market_item in markets_data:
                    # Handle both direct list and edges pattern
                    market = market_item.get("node", market_item) if isinstance(market_item, dict) else {}
                    market_name = market.get("name", "")
                    if not self._is_matcher_market(market_name, sport):
                        continue

                    # Get selections/outcomes
                    selections = market.get("selections", []) or market.get("outcomes", [])
                    market_odds: List[ScrapedOdds] = []
                    for sel_item in selections:
                        sel = sel_item.get("node", sel_item) if isinstance(sel_item, dict) else {}
                        sel_name = sel.get("name", "")

                        # Get odds - GraphQL often has decimal odds directly
                        odds_value = sel.get("odds") or sel.get("price") or sel.get("decimalOdds")
                        if isinstance(odds_value, dict):
                            odds_value = odds_value.get("decimal") or odds_value.get("value")

                        if not odds_value:
                            continue

                        try:
                            decimal_odds = Decimal(str(odds_value))
                            if decimal_odds < Decimal("1.01"):
                                continue
                        except:
                            continue

                        selection_key = self._get_selection_key(sel_name, event)
                        if selection_key not in {"home", "away", "draw"}:
                            continue

                        odds = ScrapedOdds(
                            event_external_id=event_id,
                            event_name=event_name,
                            sport=sport,
                            competition=competition,
                            start_time=start_time,
                            market_type="match_winner",
                            market_name=market_name,
                            selection_name=sel_name,
                            selection_key=selection_key,
                            decimal_odds=decimal_odds.quantize(Decimal("0.01")),
                            bookmaker_code=self.bookmaker_code,
                            source_url=f"{self.base_url}/sports/event/{event_id}",
                            scraped_at=datetime.now(timezone.utc)
                        )
                        market_odds.append(odds)

                    event.odds.extend(self._sanitize_market_odds(market_odds, sport))

                if event.odds:
                    events.append(event)

            except Exception as e:
                self.logger.error(f"[{self.bookmaker_code}] Failed to parse GraphQL event: {e}")
                continue

        if sport in ("basketball", "ice_hockey") and events:
            before = len(events)
            events = [
                e
                for e in events
                if self._is_matchup_event_name(e.name) and not self._is_outright_event_name(e.name)
            ]
            removed = before - len(events)
            if removed > 0:
                self.logger.info(f"[{self.bookmaker_code}] Filtered out {removed} outright/non-match GraphQL events ({sport})")

        self.logger.info(f"[{self.bookmaker_code}] Parsed {len(events)} events from GraphQL")
        return events

    def _extract_teams_from_name(self, event_name: str) -> tuple:
        """Extract home and away teams from event name."""
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

        return home_team, away_team

    def _participant_sort_key(self, name: str) -> str:
        """Stable cross-bookmaker sort key for participant names (used for boxing)."""
        if not name:
            return ""
        norm = name.strip().lower()
        norm = unicodedata.normalize("NFKD", norm).encode("ascii", "ignore").decode("ascii")
        norm = re.sub(r"[^a-z0-9]+", "", norm)
        return norm

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


# Convenience factory functions for each Entain bookmaker (AU)
def create_ladbrokes_scraper(config: Optional[Dict[str, Any]] = None) -> EntainScraper:
    """Create Ladbrokes scraper (Entain platform)."""
    return EntainScraper("ladbrokes", "https://www.ladbrokes.com.au", config)


def create_neds_scraper(config: Optional[Dict[str, Any]] = None) -> EntainScraper:
    """Create Neds scraper (Entain platform)."""
    return EntainScraper("neds", "https://www.neds.com.au", config)
