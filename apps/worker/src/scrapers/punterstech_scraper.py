"""
Punterstech Platform Scraper - Covers 21 Australian bookmakers

Punterstech is a white-label betting software provider that powers 21 bookmakers:
TradieBET, MintBet, XBet, MillennialBet, BetReal, BetBlitz, BetChamps,
TopBet, BetFocus, LightningBet, ChaseBet, BlondeBet, WizBet, BetBuzz,
AlphaBet, TrueBet, RipperBet, StarSports, CashCage, TeamBet

All bookmakers use IDENTICAL API structure - only the domain differs.

API Pattern:
  POST {api_base}/api-events/public/next-to-go
  GET  {api_base}/api-events/public/quick-markets/{EventKey}

Events Structure (next-to-go):
  {
    "Events": [
      {
        "EventKey": "13039916",
        "Name": "Melbourne Victory v Perth Glory",
        "EventType": "football",
        "EventSubType": "australia-aleague",
        "Competitors": [...],
        "StartTime": "1767342900000"
      }
    ]
  }

Quick Markets Structure (quick-markets/{EventKey}):
  {
    "Markets": [
      {
        "Type": "HeadToHead",
        "Market": {
          "Description": "Match Result",
          "Outcomes": [
            {"Name": "Melbourne Victory", "Prices": [{"WinPrice": 1.65}]}
          ]
        }
      }
    ]
  }

PRODUCTION NOTES:
- Direct HTTP requests (no Playwright required)
- Capture events from next-to-go, odds from quick-markets per EventKey
- Concurrency-limited httpx client for scale
"""
import asyncio
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import logging
from urllib.parse import urlparse

import httpx

from .base import BaseScraper, ScrapeResult, ScrapedEvent, ScrapedOdds, ScraperStatus

logger = logging.getLogger(__name__)


# Punterstech bookmaker configurations
# Format: (code, api_base_url, website_url)
# URLs verified 2026-01-02
PUNTERSTECH_BOOKMAKERS = {
    # Working/Verified brands
    "tradiebet": ("tradiebet", "https://api.public.tradie.bet", "https://www.tradie.bet"),
    "mintbet": ("mintbet", "https://api.public.mintbet.au", "https://www.mintbet.com.au"),
    "millennialbet": ("millennialbet", "https://api.public.millennialbet.com.au", "https://www.millennialbet.com.au"),
    "betreal": ("betreal", "https://api.public.betreal.com.au", "https://www.betreal.com.au"),
    "betblitz": ("betblitz", "https://api.public.betblitz.com.au", "https://www.betblitz.com.au"),
    "betchamps": ("betchamps", "https://api.public.betchamps.com.au", "https://www.betchamps.com.au"),
    "betfocus": ("betfocus", "https://api.public.betfocus.com.au", "https://www.betfocus.com.au"),
    "lightningbet": ("lightningbet", "https://api.public.lightningbet.com.au", "https://www.lightningbet.com.au"),
    "blondebet": ("blondebet", "https://api.public.blondebet.com.au", "https://www.blondebet.com.au"),
    "wizbet": ("wizbet", "https://api.public.wizbet.com.au", "https://www.wizbet.com.au"),
    "truebet": ("truebet", "https://api.public.truebet.com.au", "https://www.truebet.com.au"),
    "cashcage": ("cashcage", "https://api.public.cashcage.com.au", "https://www.cashcage.com.au"),
    "teambet": ("teambet", "https://api.public.teambet.com.au", "https://www.teambet.com.au"),
    "betvista": ("betvista", "https://api.public.betvista.com.au", "https://www.betvista.com.au"),
    # Corrected URLs (verified 2026-01-03)
    "topbet": ("topbet", "https://api.public.topbet.au", "https://www.topbet.au"),
    "chasebet": ("chasebet", "https://api.public.chasebet.com.au", "https://www.chasebet.com.au"),
    "betbuzz": ("betbuzz", "https://api.public.betbuzz.au", "https://www.betbuzz.au"),
    "betalpha": ("betalpha", "https://api.public.betalpha.au", "https://www.betalpha.au"),
    "ripperbet": ("ripperbet", "https://api.public.ripperbet.au", "https://www.ripperbet.au"),
    "starsports": ("starsports", "https://api.public.starsports.com.au", "https://www.starsports.com.au"),
    # xbet removed - domain not found/defunct
}


class PunterstechScraper(BaseScraper):
    """
    Scraper for Punterstech platform bookmakers (21 bookmakers).

    Uses direct API calls (next-to-go + quick-markets) to capture events and odds.

    Usage:
        # TradieBET
        scraper = PunterstechScraper("tradiebet", "https://api.public.tradie.bet")

        # MintBet
        scraper = PunterstechScraper("mintbet", "https://api.public.mintbet.au")
    """

    # Sport URL paths (Punterstech uses "football" not "soccer")
    SPORT_PATHS = {
        "soccer": "/sports/football",
        "afl": "/sports/australian-rules",
        "nrl": "/sports/rugby-league",
        "basketball": "/sports/basketball",
        "ice_hockey": "/sports/ice-hockey",
        "boxing": "/sports/martial-arts",
        "cricket": "/sports/cricket",
        "tennis": "/sports/tennis",
    }

    # Sport name mappings (Punterstech name -> our internal name)
    SPORT_MAPPINGS = {
        "soccer": "soccer",
        "football": "soccer",
        "australian-rules": "afl",
        "australian rules": "afl",
        "afl": "afl",
        "rugby-league": "nrl",
        "rugby league": "nrl",
        "nrl": "nrl",
        "basketball": "basketball",
        "nba": "basketball",
        "ice-hockey": "ice_hockey",
        "ice hockey": "ice_hockey",
        "hockey": "ice_hockey",
        "nhl": "ice_hockey",
        "boxing": "boxing",
        "martial-arts": "boxing",
        "martial arts": "boxing",
        "mma": "mma",
        "ufc": "mma",
        "tennis": "tennis",
        "cricket": "cricket",
        "golf": "golf",
        "rugby union": "rugby_union",
    }

    # Competition filters - only scrape these for matched betting
    COMPETITION_FILTERS = {
        "soccer": [
            "english premier league", "epl",
            "a-league", "a league", "a-league men", "a-league women", "aleague",
            "la liga", "spanish la liga", "spanish primera", "spain-la-liga",
            "bundesliga", "german bundesliga",
            "serie a", "italian serie a", "italy-serie-a",
            "ligue 1", "french ligue 1", "france-ligue-1",
            "champions league", "uefa champions league",
            "mls", "major league soccer",
            "fa cup", "league cup", "carabao cup",
            "england-premier-league", "england-championship",
        ],
        "afl": ["afl", "australian football league"],
        "nrl": ["nrl", "national rugby league"],
        # NOTE: Keep this tight. "National Basketball League" matches many countries.
        "basketball": ["nba", "nbl", "australia-nbl"],
        "ice_hockey": ["nhl", "national hockey league"],
        "boxing": ["boxing", "upcoming fights", "fight night", "ufc", "ultimate-fighting"],
    }
    COMPETITION_PATTERNS = COMPETITION_FILTERS

    # EventType codes used by next-to-go endpoint
    EVENT_TYPE_CODES = {
        "soccer": ["football"],
        "afl": ["australian-rules"],
        "nrl": ["rugby-league"],
        "basketball": ["basketball"],
        "ice_hockey": ["ice-hockey"],
        # MintBet exposes BOTH "boxing" and "martial-arts" event types
        # (see /api-events/public/open-event-types).
        "boxing": ["boxing", "martial-arts"],
    }

    # Market types we care about (for matched betting)
    TARGET_MARKET_TYPES = [
        "match result", "match winner", "head to head", "h2h",
        "money line", "moneyline", "to win", "win only",
        "match betting", "full time result", "1x2",
    ]

    # Selection phrases that indicate non-match-winner markets
    DISALLOWED_SELECTION_PHRASES = [
        "score first",
        "to score",
        "both teams",
        "double chance",
        "draw no bet",
        "handicap",
        "spread",
        "margin",
        "first half",
        "second half",
        "half time",
        "halftime",
        "win and",
        "to win and",
        "win &",
        "to win &",
        "win +",
        "to win +",
        "win /",
        "to win /",
        " and over",
        " and under",
        " and yes",
        " and no",
        " and btts",
        "clean sheet",
    ]

    ALL_SPORTS = ["soccer", "basketball", "ice_hockey", "boxing"]

    def __init__(
        self,
        bookmaker_code: str,
        base_url: str,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize Punterstech scraper for a specific bookmaker.

        Args:
            bookmaker_code: Unique code (tradiebet, mintbet, etc.)
            base_url: API base URL (e.g., https://api.public.tradie.bet)
                      NOTE: For Punterstech, base_url is the API URL, not website URL
            config: Optional additional configuration
        """
        parsed = urlparse(base_url)
        scheme = parsed.scheme or "https"
        netloc = (parsed.netloc or parsed.path).strip("/")

        if "api.public." in netloc:
            api_base_url = f"{scheme}://{netloc}"
        else:
            host = netloc.replace("www.", "")
            api_base_url = f"{scheme}://api.public.{host}"

        # Get website URL from config or known mappings
        website_url = None
        if config:
            website_url = config.get("website_url")

        if not website_url and bookmaker_code in PUNTERSTECH_BOOKMAKERS:
            _, _, website_url = PUNTERSTECH_BOOKMAKERS[bookmaker_code]

        if not website_url:
            if "api.public." in netloc:
                website_url = f"{scheme}://{netloc.replace('api.public.', 'www.')}"
            else:
                website_url = f"{scheme}://{netloc}"

        super().__init__(
            bookmaker_code=bookmaker_code,
            base_url=website_url,
            config=config or {}
        )

        self.api_base_url = api_base_url.rstrip("/")
        self.api_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self.headers.get("User-Agent", "Mozilla/5.0"),
        }
        self._http_client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()
        self._request_semaphore = asyncio.Semaphore(
            int(self.config.get("max_concurrent_requests", 8))
        )
        self.logger.info(f"[{self.bookmaker_code}] Initialized PunterstechScraper with website: {website_url}")

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Create or reuse a shared HTTP client for API calls."""
        async with self._client_lock:
            if self._http_client is None or self._http_client.is_closed:
                self._http_client = httpx.AsyncClient(
                    headers=self.api_headers.copy(),
                    timeout=self.timeout_seconds,
                    follow_redirects=True,
                )
        return self._http_client

    async def _request_json(self, method: str, url: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Request JSON with basic retries and concurrency control."""
        last_exc = None
        for attempt in range(self.max_retries):
            try:
                client = await self._get_http_client()
                async with self._request_semaphore:
                    response = await client.request(method, url, json=payload)
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    raise
        raise last_exc if last_exc else RuntimeError("Request failed without exception")

    async def _fetch_next_to_go(self, event_types: List[str], result_limit: int) -> List[Dict[str, Any]]:
        url = f"{self.api_base_url}/api-events/public/next-to-go"
        payload = {"EventType": event_types, "ResultLimit": result_limit}
        data = await self._request_json("POST", url, payload)
        return data.get("Events", [])

    async def _fetch_quick_markets(self, event_key: str) -> List[Dict[str, Any]]:
        """
        Fetch markets for an event.

        Uses /markets endpoint (has all odds) instead of /quick-markets
        (only has odds for events close to start time).
        """
        # Use /markets endpoint - has full odds for all scheduled events
        # /quick-markets only returns data for events within ~1-2 days
        url = f"{self.api_base_url}/api-events/public/markets/{event_key}"
        data = await self._request_json("GET", url)
        return data.get("Markets", [])

    def _get_event_key(self, event_data: Dict[str, Any]) -> Optional[str]:
        event_key = event_data.get("EventKey") or event_data.get("ID") or event_data.get("Id")
        if event_key is None:
            return None
        return str(event_key)

    def _parse_start_time_ms(self, start_ms: Any) -> Optional[datetime]:
        if start_ms is None or start_ms == "":
            return None
        try:
            return datetime.fromtimestamp(int(start_ms) / 1000, tz=timezone.utc)
        except (ValueError, TypeError):
            return None

    def _get_competition_name(self, event_data: Dict[str, Any]) -> str:
        event_subtype = event_data.get("EventSubType", "")
        competition = event_subtype.replace("-", " ").strip()
        meta = event_data.get("Meta", {})
        if meta.get("MasterEventName"):
            competition = meta["MasterEventName"]
        return competition or "Unknown Competition"

    def _should_include_event(self, event_data: Dict[str, Any], target_sport: str) -> bool:
        event_type = event_data.get("EventType", "").lower()
        mapped_sport = self.SPORT_MAPPINGS.get(event_type)
        if mapped_sport != target_sport:
            return False

        start_time = self._parse_start_time_ms(event_data.get("StartTime"))
        if start_time and start_time < datetime.now(timezone.utc):
            return False

        competition_filters = self.COMPETITION_FILTERS.get(target_sport, [])
        if competition_filters:
            comp_lower = self._get_competition_name(event_data).lower()
            # Skip futures/outrights - odds matcher is for head-to-head fixtures.
            if any(token in comp_lower for token in ("futures", "outright")):
                return False
            if not any(f in comp_lower for f in competition_filters):
                return False

        return True

    def _get_sport_url(self, sport: str) -> Optional[str]:
        """Get full URL for a sport page."""
        path = self.SPORT_PATHS.get(sport)
        if not path:
            return None
        return f"{self.base_url}{path}"

    async def scrape_sport(self, sport: str, limit: Optional[int] = None) -> ScrapeResult:
        """
        Scrape a specific sport via Punterstech public APIs.
        """
        started_at = datetime.now(timezone.utc)
        scrape_start = time.time()
        all_events = []
        errors = []

        event_types = self.EVENT_TYPE_CODES.get(sport)
        if not event_types:
            error_msg = f"Unsupported sport: {sport}"
            self.logger.error(f"[{self.bookmaker_code}] {error_msg}")
            errors.append(error_msg)
            return self._create_failed_result(started_at, errors)

        api_limit = int(self.config.get("result_limit", 500))
        if limit:
            api_limit = min(api_limit, limit)

        try:
            self.logger.info(
                f"[{self.bookmaker_code}] Starting scrape: {sport} (event_types={event_types}, limit={api_limit})"
            )

            events_list = await self._fetch_next_to_go(event_types, api_limit)
            if not events_list:
                errors.append(f"No events returned for {sport}")
                return self._create_failed_result(started_at, errors)

            # Pre-filter to reduce quick-markets calls
            eligible_events = [e for e in events_list if self._should_include_event(e, sport)]
            if limit:
                eligible_events = eligible_events[:limit]

            self.logger.info(
                f"[{self.bookmaker_code}/{sport}] next-to-go returned {len(events_list)} events, "
                f"eligible={len(eligible_events)}"
            )

            events_by_key: Dict[str, Dict] = {}
            for event in eligible_events:
                event_key = self._get_event_key(event)
                if event_key:
                    events_by_key[event_key] = event

            if not events_by_key:
                errors.append(f"No matching events for {sport}")
                return self._create_failed_result(started_at, errors)

            self.logger.info(
                f"[{self.bookmaker_code}/{sport}] Fetching quick-markets for {len(events_by_key)} events"
            )

            markets_by_key: Dict[str, List[Dict]] = {}
            event_keys = list(events_by_key.keys())
            results = await asyncio.gather(
                *[self._fetch_quick_markets(key) for key in event_keys],
                return_exceptions=True
            )

            for event_key, result in zip(event_keys, results):
                if isinstance(result, Exception):
                    errors.append(f"quick-markets {event_key}: {result}")
                    continue
                markets_by_key[event_key] = result

            self.logger.info(
                f"[{self.bookmaker_code}/{sport}] Captured {len(markets_by_key)} quick-markets responses"
            )

            events_without_markets = [k for k in events_by_key if k not in markets_by_key]
            if events_without_markets:
                self.logger.debug(
                    f"[{self.bookmaker_code}/{sport}] {len(events_without_markets)} events without markets data"
                )

            all_events = self._parse_punterstech_events(events_by_key, markets_by_key, sport)

            # Remove duplicates
            seen_ids = set()
            unique_events = []
            for event in all_events:
                if event.external_id not in seen_ids:
                    seen_ids.add(event.external_id)
                    unique_events.append(event)
            all_events = unique_events

            # Apply competition filters (log only; pre-filter already done)
            competition_filters = self.COMPETITION_FILTERS.get(sport, [])
            if competition_filters:
                filter_set = {f.lower() for f in competition_filters}
                filtered_events = []
                for event in all_events:
                    comp_lower = event.competition.lower()
                    if any(f in comp_lower for f in filter_set):
                        filtered_events.append(event)

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

    def _parse_punterstech_events(
        self,
        events_by_key: Dict[str, Dict],
        markets_by_key: Dict[str, List[Dict]],
        target_sport: str
    ) -> List[ScrapedEvent]:
        """
        Parse Punterstech events with their markets/odds.

        Args:
            events_by_key: Dict of EventKey -> event data
            markets_by_key: Dict of EventKey -> list of markets
            target_sport: Internal sport name (soccer, basketball, etc.)
        """
        parsed_events = []

        for event_key, event_data in events_by_key.items():
            try:
                # Get event type and map to internal sport
                event_type = event_data.get("EventType", "").lower()
                mapped_sport = self.SPORT_MAPPINGS.get(event_type)

                if not mapped_sport or mapped_sport != target_sport:
                    continue

                # Parse event details
                event_name = event_data.get("Name", "Unknown Event")
                competition = self._get_competition_name(event_data)

                # Parse start time (milliseconds timestamp)
                start_time = self._parse_start_time_ms(event_data.get("StartTime"))
                if not start_time:
                    start_time = datetime.now(timezone.utc) + timedelta(days=1)

                # Skip past events
                if start_time < datetime.now(timezone.utc):
                    continue

                # Extract teams.
                #
                # IMPORTANT: Prefer the event name separator semantics:
                # - "Home v Away"  -> Home/Away
                # - "Away @ Home"  -> Away/Home (rare on Punterstech, common on Betfair)
                #
                # This keeps home/away consistent across bookmakers and prevents false
                # arbitrage opportunities when selection_key is used for matching.
                home_team, away_team = self._parse_teams_from_name(event_name)
                if not home_team or not away_team:
                    competitors = event_data.get("Competitors", [])
                    if len(competitors) >= 2:
                        home_team = competitors[0].get("Name", "") or None
                        away_team = competitors[1].get("Name", "") or None

                # Create event
                event = ScrapedEvent(
                    external_id=str(event_key),
                    name=event_name,
                    sport=target_sport,
                    competition=competition,
                    start_time=start_time,
                    home_team=home_team,
                    away_team=away_team,
                    odds=[]
                )

                event_url = self._get_sport_url(target_sport)
                if event_url:
                    event_url = f"{event_url}/{event_key}"
                else:
                    event_url = self.base_url

                # Parse markets for this event
                # Supports both /markets and /quick-markets response formats
                markets = markets_by_key.get(event_key, [])
                for market_data in markets:
                    # /markets endpoint returns flat structure
                    # /quick-markets wraps in {"Type": ..., "Market": {...}}
                    if "Market" in market_data:
                        # quick-markets format
                        market = market_data.get("Market", {})
                        market_type = market_data.get("Type", "")
                        market_desc = market.get("Description", "")
                        outcomes = market.get("Outcomes", [])
                    else:
                        # /markets format (flat structure)
                        market_desc = market_data.get("Description", "")
                        market_ref = market_data.get("ExternalRef", "")
                        outcomes = market_data.get("Outcomes", [])
                        # MW = Match Winner, H2H = Head to Head
                        market_type = "HeadToHead" if market_ref in ["MW", "H2H"] else ""

                    # Only process Head to Head / Match Result / Match Winner markets
                    market_desc_lower = market_desc.lower()
                    # NOTE: Punterstech uses different names per sport:
                    # - Soccer: "Match Result"
                    # - Basketball/Ice hockey: "Money Line" (and sometimes also "Match Winner")
                    # - Boxing: "Fight Betting"/"Fight Result"
                    #
                    # We explicitly EXCLUDE partial-game markets like "1st Half Money Line"
                    # so we don't accidentally treat quarters/periods as full-time match winner.
                    is_partial_market = any(
                        token in market_desc_lower
                        for token in (
                            "1st half",
                            "first half",
                            "2nd half",
                            "second half",
                            "half time",
                            "halftime",
                            "1st quarter",
                            "first quarter",
                            "2nd quarter",
                            "second quarter",
                            "3rd quarter",
                            "third quarter",
                            "4th quarter",
                            "fourth quarter",
                            "period",
                            "set",
                            "map",
                            "innings",
                        )
                    )

                    is_money_line = ("money line" in market_desc_lower) or ("moneyline" in market_desc_lower)
                    is_head_to_head = (
                        market_type == "HeadToHead"
                        or "head to head" in market_desc_lower
                        or "head-to-head" in market_desc_lower
                        or "h2h" in market_desc_lower
                    )
                    is_match_result = ("match winner" in market_desc_lower) or ("match result" in market_desc_lower)
                    is_boxing = "fight" in market_desc_lower
                    is_match_winner = (
                        not is_partial_market
                        and (
                            is_head_to_head
                            or is_match_result
                            or is_money_line
                            or is_boxing
                            or market_data.get("ExternalRef") == "MW"
                        )
                    )

                    if not is_match_winner:
                        continue

                    for outcome in outcomes:
                        if outcome.get("Scratched"):
                            continue

                        sel_name = outcome.get("Name", "")
                        prices = outcome.get("Prices", [])

                        for price_data in prices:
                            win_price = price_data.get("WinPrice", 0)
                            if win_price and win_price > 1:
                                selection_key = self._get_selection_key(sel_name, event)
                                if selection_key == "other":
                                    continue

                                canonical_name = self._canonicalize_selection_name(sel_name, selection_key, event)

                                odds = ScrapedOdds(
                                    event_external_id=event.external_id,
                                    event_name=event.name,
                                    sport=event.sport,
                                    competition=event.competition,
                                    start_time=event.start_time,
                                    market_type="match_winner",
                                    market_name=market_desc or "Match Result",
                                    selection_name=canonical_name,
                                    selection_key=selection_key,
                                    decimal_odds=Decimal(str(win_price)).quantize(Decimal("0.01")),
                                    bookmaker_code=self.bookmaker_code,
                                    source_url=event_url,
                                    scraped_at=datetime.now(timezone.utc)
                                )
                                event.odds.append(odds)

                if event.odds:
                    parsed_events.append(event)
                    self.logger.debug(f"[{self.bookmaker_code}] Parsed event: {event.name} with {len(event.odds)} odds")

            except Exception as e:
                self.logger.debug(f"[{self.bookmaker_code}] Failed to parse event {event_key}: {e}")
                continue

        return parsed_events

    def _parse_events(self, events_list: List[Dict], target_sport: str) -> List[ScrapedEvent]:
        """
        Parse events list from Punterstech API.

        The API returns events in various formats. We need to handle:
        - Different sport name formats
        - Different market structures
        - Various date formats
        """
        parsed_events = []

        for event_data in events_list:
            try:
                # Get sport and check if it matches
                event_sport = event_data.get("Sport", "").lower()
                event_type = event_data.get("EventType", "").lower()

                # Map to internal sport name
                mapped_sport = self.SPORT_MAPPINGS.get(event_sport) or self.SPORT_MAPPINGS.get(event_type)

                if not mapped_sport or mapped_sport != target_sport:
                    continue

                # Parse event details
                external_id = event_data.get("ExternalEventId") or event_data.get("EventId") or event_data.get("Id", "")
                event_name = event_data.get("EventName") or event_data.get("Name", "Unknown Event")
                competition = event_data.get("Competition") or event_data.get("CompetitionName", "Unknown")

                # Parse start time
                start_str = event_data.get("StartTime") or event_data.get("AdvertisedStartTime", "")
                try:
                    if isinstance(start_str, str) and start_str:
                        # Handle various ISO formats
                        start_str = start_str.replace("Z", "+00:00")
                        start_time = datetime.fromisoformat(start_str)
                    else:
                        start_time = datetime.now(timezone.utc) + timedelta(days=1)
                except:
                    start_time = datetime.now(timezone.utc) + timedelta(days=1)

                # Skip past events
                if start_time < datetime.now(timezone.utc):
                    continue

                # Extract home/away teams from event name
                home_team, away_team = self._parse_teams_from_name(event_name)

                # Create event
                event = ScrapedEvent(
                    external_id=str(external_id),
                    name=event_name,
                    sport=target_sport,
                    competition=competition,
                    start_time=start_time,
                    home_team=home_team,
                    away_team=away_team,
                    odds=[]
                )

                # Parse markets/selections
                markets = event_data.get("Markets", [])
                if not markets:
                    # Try alternate structure
                    markets = event_data.get("Selections", [])

                for market_data in markets:
                    self._parse_market(market_data, event)

                # Also check for inline selections (some events have odds directly)
                if not event.odds:
                    selections = event_data.get("Selections", [])
                    if selections:
                        self._parse_inline_selections(selections, event)

                if event.odds:
                    parsed_events.append(event)

            except Exception as e:
                self.logger.debug(f"[{self.bookmaker_code}] Failed to parse event: {e}")
                continue

        return parsed_events

    def _parse_teams_from_name(self, event_name: str) -> tuple:
        """Extract home and away teams from event name."""
        home_team = None
        away_team = None

        # Try various separators
        for sep in [" v ", " vs ", " V ", " VS ", " @ "]:
            if sep in event_name:
                parts = event_name.split(sep, 1)
                if len(parts) == 2:
                    if sep == " @ ":
                        # @ format: Away @ Home
                        away_team = parts[0].strip()
                        home_team = parts[1].strip()
                    else:
                        # v/vs format: Home v Away
                        home_team = parts[0].strip()
                        away_team = parts[1].strip()
                    break

        return home_team, away_team

    def _parse_market(self, market_data: Dict, event: ScrapedEvent):
        """Parse a market and add odds to the event."""
        market_name = market_data.get("MarketName") or market_data.get("Name", "")
        market_type_raw = market_data.get("MarketType", "")

        # Check if this is a market we care about
        market_lower = market_name.lower()
        is_target_market = any(t in market_lower for t in self.TARGET_MARKET_TYPES)

        if not is_target_market:
            return

        # Get selections
        selections = market_data.get("Selections", [])
        if not selections:
            selections = market_data.get("Outcomes", [])

        for sel_data in selections:
            self._parse_selection(sel_data, market_name, event)

    def _parse_inline_selections(self, selections: List[Dict], event: ScrapedEvent):
        """Parse selections that are directly on the event (not in markets)."""
        for sel_data in selections:
            # Default to match result market
            self._parse_selection(sel_data, "Match Result", event)

    def _parse_selection(self, sel_data: Dict, market_name: str, event: ScrapedEvent):
        """Parse a single selection and add odds to the event."""
        try:
            sel_name = sel_data.get("Name") or sel_data.get("SelectionName", "")

            # Get price - try multiple field names
            price = None
            for price_field in ["Price", "Odds", "DecimalOdds", "WinPrice", "FixedOdds"]:
                if price_field in sel_data:
                    price = sel_data[price_field]
                    break

            if not price or not sel_name:
                return

            try:
                decimal_odds = Decimal(str(price))
                if decimal_odds <= 1:
                    return  # Invalid odds
            except:
                return

            # Determine selection key
            selection_key = self._get_selection_key(sel_name, event)
            if selection_key == "other":
                return

            canonical_name = self._canonicalize_selection_name(sel_name, selection_key, event)

            odds = ScrapedOdds(
                event_external_id=event.external_id,
                event_name=event.name,
                sport=event.sport,
                competition=event.competition,
                start_time=event.start_time,
                market_type="match_winner",
                market_name=market_name,
                selection_name=canonical_name,
                selection_key=selection_key,
                decimal_odds=decimal_odds.quantize(Decimal("0.01")),
                bookmaker_code=self.bookmaker_code,
                source_url=f"{self.base_url}/event/{event.external_id}",
                scraped_at=datetime.now(timezone.utc)
            )

            event.odds.append(odds)

        except Exception as e:
            self.logger.debug(f"[{self.bookmaker_code}] Failed to parse selection: {e}")

    def _get_selection_key(self, selection_name: str, event: ScrapedEvent) -> str:
        """Determine selection key (home/away/draw) from selection name."""
        name_lower = selection_name.lower().strip()

        if self._is_disallowed_match_winner_selection(name_lower):
            return "other"

        # Check for draw (handles "Draw", "The Draw", "Tie", "X")
        if name_lower in ["draw", "the draw", "tie", "x"]:
            return "draw"

        if self._is_simple_team_selection(selection_name, event.home_team):
            return "home"
        if self._is_simple_team_selection(selection_name, event.away_team):
            return "away"

        def normalize_team(name: str) -> str:
            if not name:
                return ""
            n = name.lower().strip()
            # Strip common suffixes
            for suffix in [" fc", " afc", " cf", " sc", " united", " city", " win"]:
                if n.endswith(suffix):
                    n = n[:-len(suffix)].strip()
            return n

        sel_norm = normalize_team(selection_name)
        home_norm = normalize_team(event.home_team) if event.home_team else ""
        away_norm = normalize_team(event.away_team) if event.away_team else ""

        # Exact match
        if home_norm and sel_norm == home_norm:
            return "home"
        if away_norm and sel_norm == away_norm:
            return "away"

        # Substring match
        if home_norm and (home_norm in sel_norm or sel_norm in home_norm):
            return "home"
        if away_norm and (away_norm in sel_norm or sel_norm in away_norm):
            return "away"

        # Full name match
        if event.home_team and event.home_team.lower() in name_lower:
            return "home"
        if event.away_team and event.away_team.lower() in name_lower:
            return "away"

        # Boxing (and some individual sports) sometimes abbreviate outcomes like "Lopez, T".
        # Fall back to a surname match so selection_key stays stable across bookmakers.
        if "," in selection_name and (event.home_team or event.away_team):
            def surname(text: str) -> str:
                if not text:
                    return ""
                norm_text = self._normalize_selection_text(text)
                parts = norm_text.split()
                if not parts:
                    return ""
                # If the original had a comma ("Last, F"), treat the first token as surname.
                if "," in text:
                    return parts[0]
                # Otherwise treat the last token as surname (e.g., "Teofimo Lopez" -> "lopez")
                return parts[-1]

            sel_surname = surname(selection_name)
            home_surname = surname(event.home_team) if event.home_team else ""
            away_surname = surname(event.away_team) if event.away_team else ""

            if sel_surname and home_surname and sel_surname == home_surname:
                return "home"
            if sel_surname and away_surname and sel_surname == away_surname:
                return "away"

        return "other"

    def _canonicalize_selection_name(self, selection_name: str, selection_key: str, event: ScrapedEvent) -> str:
        """
        Prefer full competitor names for H2H selections.

        Punterstech outcome names are sometimes abbreviated (e.g., "Wild", "Kings Win").
        Using the event's full competitor names improves cross-bookmaker matching.
        """
        if selection_key == "home" and event.home_team:
            return event.home_team
        if selection_key == "away" and event.away_team:
            return event.away_team
        if selection_key == "draw":
            return "Draw"
        return selection_name

    def _is_simple_team_selection(self, selection_name: str, team_name: str) -> bool:
        """Return True if selection is just the team (optionally with a win suffix)."""
        if not selection_name or not team_name:
            return False

        sel_norm = self._normalize_selection_text(selection_name)
        team_norm = self._normalize_selection_text(team_name)
        if not sel_norm or not team_norm or team_norm not in sel_norm:
            return False

        remainder = sel_norm.replace(team_norm, " ").strip()
        remainder = " ".join(remainder.split())

        allowed_suffixes = {"", "win", "to win", "winner", "win only"}
        return remainder in allowed_suffixes

    def _normalize_selection_text(self, text: str) -> str:
        """Normalize text for team/selection comparison."""
        if not text:
            return ""
        cleaned = text.lower().replace("&", "and")
        for ch in [".", ",", "-", "(", ")", "'", "\""]:
            cleaned = cleaned.replace(ch, " ")
        return " ".join(cleaned.split())

    def _is_disallowed_match_winner_selection(self, name_lower: str) -> bool:
        """Filter out non-match-winner selections that include extra conditions."""
        for phrase in self.DISALLOWED_SELECTION_PHRASES:
            if phrase in name_lower:
                return True
        return False

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
        """Required abstract method - not used directly."""
        raise NotImplementedError("Use _parse_events instead")

    def parse_odds(self, odds_data: Any, event: ScrapedEvent) -> List[ScrapedOdds]:
        """Required abstract method - not used directly."""
        raise NotImplementedError("Use _parse_events instead")


# Factory functions for common Punterstech bookmakers
def create_tradiebet_scraper(config: Optional[Dict[str, Any]] = None) -> PunterstechScraper:
    """Create TradieBET scraper (Punterstech platform)."""
    cfg = config or {}
    cfg["website_url"] = "https://www.tradie.bet"
    return PunterstechScraper("tradiebet", "https://api.public.tradie.bet", cfg)


def create_mintbet_scraper(config: Optional[Dict[str, Any]] = None) -> PunterstechScraper:
    """Create MintBet scraper (Punterstech platform)."""
    cfg = config or {}
    cfg["website_url"] = "https://www.mintbet.com.au"
    return PunterstechScraper("mintbet", "https://api.public.mintbet.au", cfg)
