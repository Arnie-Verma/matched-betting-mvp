"""
TAB (tab.com.au) scraper for Australian sports betting odds.

TAB typically uses a JSON API for odds data. This scraper targets their
public API endpoints used by their website.
"""
import asyncio
import httpx
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseScraper, ScrapeResult, ScrapedEvent, ScrapedOdds, ScraperStatus


class TABScraper(BaseScraper):
    """
    Scraper for TAB (tab.com.au).

    TAB exposes a public API that their website uses. We can access:
    - /v1/tab-info-service/racing/dates/{sport}/meetings
    - /v1/tab-info-service/sports/events
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            bookmaker_code="tab",
            base_url="https://api.beta.tab.com.au",
            config=config
        )

        # TAB API endpoints
        self.api_base = "https://api.beta.tab.com.au"
        self.jurisdiction = "VIC"  # Can be VIC, NSW, QLD, etc.

        # Sport mapping (our codes to TAB codes - TAB uses capitalized names)
        self.sport_mapping = {
            "afl": "Australian Rules",
            "nrl": "Rugby League",
            "cricket": "Cricket",
            "tennis": "Tennis",
            "soccer": "Soccer",
            "basketball": "Basketball",
        }

        # Competition mapping for popular leagues
        self.competition_mapping = {
            "epl": "English Premier League",
            "ucl": "UEFA Champions League",
            "nba": "NBA",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_json(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Fetch JSON data from TAB API with retry logic and anti-bot headers"""
        # TAB-specific headers to mimic browser requests
        tab_headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-AU,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Origin": "https://www.tab.com.au",
            "Referer": "https://www.tab.com.au/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "Connection": "keep-alive",
        }

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(
                url,
                headers=tab_headers,
                params=params,
                timeout=self.timeout_seconds
            )
            response.raise_for_status()
            return response.json()

    async def scrape_sport(self, sport: str, limit: Optional[int] = None) -> ScrapeResult:
        """
        Scrape TAB for a specific sport.

        Args:
            sport: Our sport code ("afl", "nrl", etc.)
            limit: Max events to scrape

        Returns:
            ScrapeResult with events and odds
        """
        started_at = datetime.now(timezone.utc)
        events = []
        errors = []

        try:
            # Map our sport code to TAB's sport code
            tab_sport_code = self.get_tab_sport_code(sport)
            if not tab_sport_code:
                errors.append(f"Unsupported sport: {sport}")
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

            # Fetch competitions for this sport first
            self.logger.info(f"Scraping TAB for sport: {sport} ({tab_sport_code})")

            # For EPL specifically, fetch matches from the competition
            # https://api.beta.tab.com.au/v1/tab-info-service/sports/Soccer/competitions/English%20Premier%20League/matches?jurisdiction=VIC

            if sport == "soccer":
                # Hardcode EPL for now
                competition_name = "English%20Premier%20League"
                matches_url = f"{self.api_base}/v1/tab-info-service/sports/{tab_sport_code}/competitions/{competition_name}/matches"
                params = {"jurisdiction": self.jurisdiction}

                try:
                    data = await self.fetch_json(matches_url, params)
                    events = await self.parse_tab_matches(data, sport, "English Premier League")

                    if limit:
                        events = events[:limit]

                except Exception as e:
                    errors.append(f"Failed to fetch matches: {str(e)}")
                    self.logger.error(f"TAB API error: {e}")
            else:
                errors.append(f"Sport {sport} not yet implemented for TAB scraper")
                self.logger.warning(f"TAB scraper doesn't support {sport} yet")

        except Exception as e:
            errors.append(f"Scrape failed: {str(e)}")
            self.logger.exception(f"TAB scraper error for {sport}")

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

    async def parse_tab_matches(self, api_data: Dict, sport: str, competition: str) -> List[ScrapedEvent]:
        """
        Parse TAB matches API response into ScrapedEvent objects.

        TAB matches structure:
        {
            "matches": [
                {
                    "id": "NForvChls",
                    "name": "Nottinghm Forest v Chelsea",
                    "startTime": "2025-10-18T11:30:00.000Z",
                    "contestants": [
                        {"name": "Nottinghm Forest", "position": "HOME"},
                        {"name": "Chelsea", "position": "AWAY"}
                    ],
                    "markets": [
                        {
                            "name": "EPL Result",
                            "propositions": [
                                {"name": "Nottinghm Forest", "returnWin": 3.4},
                                {"name": "Draw", "returnWin": 3.5},
                                {"name": "Chelsea", "returnWin": 1.92}
                            ]
                        }
                    ]
                }
            ]
        }
        """
        events = []
        matches = api_data.get("matches", [])
        markets_tasks = []
        events_temp = []

        # First pass: create events and collect markets URLs for parallel fetching
        for match_data in matches:
            try:
                # Parse match details
                match_id = str(match_data.get("id", ""))
                match_name = match_data.get("name", "Unknown Match")
                start_time_str = match_data.get("startTime", "")

                # Parse start time
                try:
                    start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                except:
                    start_time = datetime.now(timezone.utc)

                # Extract teams from contestants
                contestants = match_data.get("contestants", [])
                home_team = None
                away_team = None

                for contestant in contestants:
                    if contestant.get("position") == "HOME":
                        home_team = contestant.get("name")
                    elif contestant.get("position") == "AWAY":
                        away_team = contestant.get("name")

                # Create event
                event = ScrapedEvent(
                    external_id=match_id,
                    name=match_name,
                    sport=sport,
                    competition=competition,
                    start_time=start_time,
                    home_team=home_team,
                    away_team=away_team,
                    odds=[]
                )

                # Collect markets URL for parallel fetching
                markets_url = match_data.get("_links", {}).get("markets")
                if markets_url:
                    markets_tasks.append((event, markets_url))

                events_temp.append(event)

            except Exception as e:
                self.logger.error(f"Failed to parse TAB match: {e}")
                continue

        # Second pass: fetch all markets in parallel for significant speedup
        if markets_tasks:
            import asyncio

            async def fetch_markets_for_event(event_and_url):
                event, url = event_and_url
                try:
                    markets_data = await self.fetch_json(url)
                    markets = markets_data.get("markets", [])
                    if markets:
                        event.odds = self.parse_tab_markets(markets, event)
                except Exception as e:
                    self.logger.error(f"Failed to fetch markets for {event.name}: {e}")
                return event

            # Fetch all markets concurrently - MUCH faster than sequential
            events = await asyncio.gather(*[fetch_markets_for_event(task) for task in markets_tasks])
        else:
            events = events_temp

        return events

    def parse_event(self, event_data: Dict) -> ScrapedEvent:
        """Parse single event from TAB API"""
        event_id = str(event_data.get("eventId", ""))
        event_name = event_data.get("eventName", "Unknown Event")
        start_time_str = event_data.get("startTime", "")

        # Parse start time
        try:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except:
            start_time = datetime.now(timezone.utc)

        # Extract teams if possible
        home_team = event_data.get("homeTeam", None)
        away_team = event_data.get("awayTeam", None)

        return ScrapedEvent(
            external_id=event_id,
            name=event_name,
            sport="",  # Set by caller
            competition="",  # Set by caller
            start_time=start_time,
            home_team=home_team,
            away_team=away_team,
            odds=[]
        )

    def parse_odds(self, odds_data: Any, event: ScrapedEvent) -> List[ScrapedOdds]:
        """Parse odds data (for abstract method compliance)"""
        if isinstance(odds_data, list):
            return self.parse_tab_markets(odds_data, event)
        return []

    def parse_tab_markets(self, markets_data: List[Dict], event: ScrapedEvent) -> List[ScrapedOdds]:
        """
        Parse odds from TAB markets data.

        TAB propositions structure:
        [
            {
                "id": "122045315",
                "name": "EPL Nott For-Chelsea Result",
                "propositions": [
                    {
                        "id": "362615",
                        "name": "Nottinghm Forest",
                        "returnWin": 3.4,
                        "position": "HOME"
                    },
                    {
                        "id": "362624",
                        "name": "Draw",
                        "returnWin": 3.5,
                        "position": "DRAW"
                    },
                    {
                        "id": "362653",
                        "name": "Chelsea",
                        "returnWin": 1.92,
                        "position": "AWAY"
                    }
                ]
            }
        ]
        """
        odds_list = []

        for market in markets_data:
            market_name = market.get("name", "Unknown")
            market_type = self.normalize_market_type(market_name)

            for proposition in market.get("propositions", []):
                try:
                    # TAB uses "returnWin" for decimal odds
                    odds_value = proposition.get("returnWin")
                    if not odds_value:
                        continue

                    odds = ScrapedOdds(
                        event_external_id=event.external_id,
                        event_name=event.name,
                        sport=event.sport,
                        competition=event.competition,
                        start_time=event.start_time,
                        market_type=market_type,
                        market_name=market_name,
                        selection_name=proposition.get("name", "Unknown"),
                        selection_key=self.get_selection_key(proposition.get("name", ""), event),
                        decimal_odds=Decimal(str(odds_value)),
                        bookmaker_code=self.bookmaker_code,
                        source_url=f"{self.api_base}/sports/Soccer/competitions/English%20Premier%20League",
                        scraped_at=datetime.now(timezone.utc)
                    )

                    odds_list.append(odds)

                except Exception as e:
                    self.logger.error(f"Failed to parse TAB odds: {e}")
                    continue

        return odds_list

    def get_tab_sport_code(self, our_code: str) -> Optional[str]:
        """Convert our sport code to TAB's sport code"""
        return self.sport_mapping.get(our_code)

    def get_selection_key(self, selection_name: str, event: ScrapedEvent) -> str:
        """Determine selection key (home/away/draw) from selection name"""
        name_lower = selection_name.lower()

        if event.home_team and event.home_team.lower() in name_lower:
            return "home"
        elif event.away_team and event.away_team.lower() in name_lower:
            return "away"
        elif "draw" in name_lower or "tie" in name_lower:
            return "draw"
        else:
            return "other"
