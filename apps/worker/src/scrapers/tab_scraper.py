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
        self.sports_endpoint = f"{self.api_base}/v1/tab-info-service/sports/events"

        # Sport mapping (TAB codes to our codes)
        self.sport_mapping = {
            "australian-rules": "afl",
            "rugby-league": "nrl",
            "cricket": "cricket",
            "tennis": "tennis",
            "soccer": "soccer",
            "basketball": "basketball",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_json(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Fetch JSON data from TAB API with retry logic"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self.headers,
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

            # Fetch events from TAB API
            # Note: This is a simplified version. Real implementation needs
            # to handle TAB's actual API structure
            self.logger.info(f"Scraping TAB for sport: {sport} ({tab_sport_code})")

            # Placeholder: TAB API structure varies by sport
            # For sports betting, they typically have:
            # GET /v1/tab-info-service/sports/{sport}/meetings
            url = f"{self.api_base}/v1/tab-info-service/sports/{tab_sport_code}/meetings"

            try:
                data = await self.fetch_json(url)
                events = self.parse_tab_events(data, sport)

                if limit:
                    events = events[:limit]

            except Exception as e:
                errors.append(f"Failed to fetch events: {str(e)}")
                self.logger.error(f"TAB API error: {e}")

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

    def parse_tab_events(self, api_data: Dict, sport: str) -> List[ScrapedEvent]:
        """
        Parse TAB API response into ScrapedEvent objects.

        TAB API structure (example):
        {
            "meetings": [
                {
                    "meetingId": "123",
                    "meetingName": "AFL - Round 1",
                    "events": [
                        {
                            "eventId": "456",
                            "eventName": "Richmond vs Collingwood",
                            "startTime": "2025-03-15T19:20:00Z",
                            "markets": [...]
                        }
                    ]
                }
            ]
        }
        """
        events = []

        # This is a placeholder - actual TAB API structure needs to be discovered
        # by inspecting network requests on tab.com.au
        meetings = api_data.get("meetings", [])

        for meeting in meetings:
            competition = meeting.get("meetingName", "Unknown Competition")

            for event_data in meeting.get("events", []):
                try:
                    event = self.parse_event(event_data)
                    event.sport = sport
                    event.competition = competition

                    # Parse odds for this event
                    odds = self.parse_odds(event_data.get("markets", []), event)
                    event.odds = odds

                    events.append(event)

                except Exception as e:
                    self.logger.error(f"Failed to parse TAB event: {e}")
                    continue

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

    def parse_odds(self, markets_data: List[Dict], event: ScrapedEvent) -> List[ScrapedOdds]:
        """
        Parse odds from TAB markets data.

        TAB markets structure (example):
        [
            {
                "marketId": "789",
                "marketName": "Head To Head",
                "marketType": "WIN",
                "selections": [
                    {
                        "selectionId": "1",
                        "name": "Richmond",
                        "odds": 1.85
                    },
                    {
                        "selectionId": "2",
                        "name": "Collingwood",
                        "odds": 2.10
                    }
                ]
            }
        ]
        """
        odds_list = []

        for market in markets_data:
            market_name = market.get("marketName", "Unknown")
            market_type = self.normalize_market_type(market_name)

            for selection in market.get("selections", []):
                try:
                    odds_value = selection.get("odds") or selection.get("price")
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
                        selection_name=selection.get("name", "Unknown"),
                        selection_key=self.get_selection_key(selection.get("name", ""), event),
                        decimal_odds=Decimal(str(odds_value)),
                        bookmaker_code=self.bookmaker_code,
                        source_url=f"{self.api_base}/event/{event.external_id}",
                        scraped_at=datetime.now(timezone.utc)
                    )

                    odds_list.append(odds)

                except Exception as e:
                    self.logger.error(f"Failed to parse TAB odds: {e}")
                    continue

        return odds_list

    def get_tab_sport_code(self, our_code: str) -> Optional[str]:
        """Convert our sport code to TAB's sport code"""
        reverse_mapping = {v: k for k, v in self.sport_mapping.items()}
        return reverse_mapping.get(our_code)

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
