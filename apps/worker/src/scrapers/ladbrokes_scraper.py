"""
Ladbrokes (ladbrokes.com.au) scraper for Australian sports betting odds.

Ladbrokes uses a GraphQL API or REST endpoints. This scraper targets
their public API used by the website.
"""
import asyncio
import httpx
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseScraper, ScrapeResult, ScrapedEvent, ScrapedOdds, ScraperStatus


class LadbrokesScraper(BaseScraper):
    """
    Scraper for Ladbrokes (ladbrokes.com.au).

    Ladbrokes typically uses either:
    - GraphQL API
    - REST API at /api/v2/sports/...
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            bookmaker_code="ladbrokes",
            base_url="https://www.ladbrokes.com.au",
            config=config
        )

        # Ladbrokes API endpoints (need to verify actual structure)
        self.api_base = "https://api.ladbrokes.com.au"

        # Sport mapping
        self.sport_mapping = {
            "afl": "australian-rules",
            "nrl": "rugby-league",
            "cricket": "cricket",
            "tennis": "tennis",
            "soccer": "football",
            "basketball": "basketball",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_json(self, url: str, params: Optional[Dict] = None, json_body: Optional[Dict] = None) -> Dict:
        """Fetch JSON data from Ladbrokes API with retry logic"""
        async with httpx.AsyncClient() as client:
            if json_body:
                # POST request (for GraphQL)
                response = await client.post(
                    url,
                    headers={**self.headers, "Content-Type": "application/json"},
                    json=json_body,
                    timeout=self.timeout_seconds
                )
            else:
                # GET request
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
        Scrape Ladbrokes for a specific sport.

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
            # Map sport code
            ladbrokes_sport = self.sport_mapping.get(sport)
            if not ladbrokes_sport:
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

            self.logger.info(f"Scraping Ladbrokes for sport: {sport} ({ladbrokes_sport})")

            # Ladbrokes API structure varies - this is a placeholder
            # Real implementation needs network inspection
            url = f"{self.api_base}/v2/sports/{ladbrokes_sport}/events"

            try:
                data = await self.fetch_json(url)
                events = self.parse_ladbrokes_events(data, sport)

                if limit:
                    events = events[:limit]

            except Exception as e:
                errors.append(f"Failed to fetch events: {str(e)}")
                self.logger.error(f"Ladbrokes API error: {e}")

        except Exception as e:
            errors.append(f"Scrape failed: {str(e)}")
            self.logger.exception(f"Ladbrokes scraper error for {sport}")

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

    def parse_ladbrokes_events(self, api_data: Dict, sport: str) -> List[ScrapedEvent]:
        """Parse Ladbrokes API response into ScrapedEvent objects"""
        events = []

        # Placeholder - actual structure depends on Ladbrokes API
        events_data = api_data.get("events", [])

        for event_data in events_data:
            try:
                event = self.parse_event(event_data)
                event.sport = sport

                # Parse odds
                odds = self.parse_odds(event_data.get("markets", []), event)
                event.odds = odds

                events.append(event)

            except Exception as e:
                self.logger.error(f"Failed to parse Ladbrokes event: {e}")
                continue

        return events

    def parse_event(self, event_data: Dict) -> ScrapedEvent:
        """Parse single event from Ladbrokes API"""
        event_id = str(event_data.get("id", ""))
        event_name = event_data.get("name", "Unknown Event")
        competition = event_data.get("competition", {}).get("name", "Unknown Competition")

        # Parse start time
        start_time_str = event_data.get("startTime", "")
        try:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except:
            start_time = datetime.now(timezone.utc)

        # Extract participants
        participants = event_data.get("participants", [])
        home_team = participants[0].get("name") if len(participants) > 0 else None
        away_team = participants[1].get("name") if len(participants) > 1 else None

        return ScrapedEvent(
            external_id=event_id,
            name=event_name,
            sport="",  # Set by caller
            competition=competition,
            start_time=start_time,
            home_team=home_team,
            away_team=away_team,
            odds=[]
        )

    def parse_odds(self, markets_data: List[Dict], event: ScrapedEvent) -> List[ScrapedOdds]:
        """Parse odds from Ladbrokes markets data"""
        odds_list = []

        for market in markets_data:
            market_name = market.get("name", "Unknown")
            market_type = self.normalize_market_type(market_name)

            for selection in market.get("selections", []):
                try:
                    # Ladbrokes may use "price" or "odds"
                    odds_value = selection.get("price") or selection.get("odds")
                    if not odds_value:
                        continue

                    # Handle different price formats
                    if isinstance(odds_value, dict):
                        odds_value = odds_value.get("decimal") or odds_value.get("value")

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
                        source_url=f"{self.base_url}/sports/event/{event.external_id}",
                        scraped_at=datetime.now(timezone.utc)
                    )

                    odds_list.append(odds)

                except Exception as e:
                    self.logger.error(f"Failed to parse Ladbrokes odds: {e}")
                    continue

        return odds_list

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
