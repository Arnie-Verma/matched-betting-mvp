"""
Betfair API integration for lay odds on the exchange.

Betfair has an official API that requires authentication. For matched betting,
we primarily need:
- Market data (events, markets, selections)
- Current prices (back and lay odds)
- Liquidity at each price point
"""
import asyncio
import httpx
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from .base import BaseScraper, ScrapeResult, ScrapedEvent, ScrapedOdds, ScraperStatus


class BetfairAPI(BaseScraper):
    """
    Betfair Exchange API client.

    Requires:
    - App Key (from Betfair developer portal)
    - Session Token (login credentials)

    API Docs: https://docs.developer.betfair.com/display/1smk3cen4v3lu3yomq5qye0ni
    """

    def __init__(self, app_key: str, session_token: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__(
            bookmaker_code="betfair",
            base_url="https://api.betfair.com",
            config=config
        )

        self.app_key = app_key
        self.session_token = session_token

        # Betfair API endpoints
        self.api_base = "https://api.betfair.com/exchange/betting/rest/v1.0"
        self.auth_endpoint = "https://identitysso-cert.betfair.com/api/certlogin"

        # Update headers for Betfair
        self.headers.update({
            "X-Application": self.app_key,
            "X-Authentication": self.session_token or "",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    async def login(self, username: str, password: str) -> str:
        """
        Login to Betfair and get session token.

        Note: Betfair requires certificate-based auth for production.
        This is a simplified version for development.
        """
        # Betfair login requires SSL cert - this is placeholder
        # Real implementation needs proper cert authentication
        raise NotImplementedError("Betfair login requires SSL certificate authentication")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def api_request(self, method: str, params: Dict) -> Dict:
        """
        Make Betfair API request using JSON-RPC style.

        Args:
            method: API method (e.g., "listEventTypes")
            params: Method parameters

        Returns:
            API response data
        """
        url = f"{self.api_base}/{method}/"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self.headers,
                json=params,
                timeout=self.timeout_seconds
            )
            response.raise_for_status()
            return response.json()

    async def list_event_types(self) -> List[Dict]:
        """Get all available event types (sports)"""
        response = await self.api_request("listEventTypes", {"filter": {}})
        return response.get("result", [])

    async def list_competitions(self, event_type_id: str) -> List[Dict]:
        """Get competitions for a sport"""
        response = await self.api_request("listCompetitions", {
            "filter": {"eventTypeIds": [event_type_id]}
        })
        return response.get("result", [])

    async def list_market_catalogue(
        self,
        event_type_id: str,
        market_type_codes: Optional[List[str]] = None,
        competition_ids: Optional[List[str]] = None,
        max_results: int = 100
    ) -> List[Dict]:
        """
        Get market catalogue (events and markets).

        Args:
            event_type_id: Sport ID (e.g., "1" for Soccer, "61420" for AFL)
            market_type_codes: Market types (e.g., ["MATCH_ODDS", "OVER_UNDER_25"])
            competition_ids: Filter by competitions
            max_results: Max markets to return

        Returns:
            List of market catalogues
        """
        filter_params = {"eventTypeIds": [event_type_id]}

        if market_type_codes:
            filter_params["marketTypeCodes"] = market_type_codes

        if competition_ids:
            filter_params["competitionIds"] = competition_ids

        response = await self.api_request("listMarketCatalogue", {
            "filter": filter_params,
            "marketProjection": [
                "COMPETITION",
                "EVENT",
                "EVENT_TYPE",
                "MARKET_START_TIME",
                "MARKET_DESCRIPTION",
                "RUNNER_DESCRIPTION",
                "RUNNER_METADATA"
            ],
            "sort": "FIRST_TO_START",
            "maxResults": max_results
        })

        return response.get("result", [])

    async def list_market_book(self, market_ids: List[str]) -> List[Dict]:
        """
        Get current prices for markets.

        Args:
            market_ids: List of market IDs

        Returns:
            List of market books with current prices
        """
        response = await self.api_request("listMarketBook", {
            "marketIds": market_ids,
            "priceProjection": {
                "priceData": ["EX_BEST_OFFERS", "EX_TRADED"],  # Exchange prices
                "exBestOffersOverrides": {
                    "bestPricesDepth": 3  # Get top 3 price levels
                },
                "virtualise": False,
                "rolloverStakes": False
            }
        })

        return response.get("result", [])

    async def scrape_sport(self, sport: str, limit: Optional[int] = None) -> ScrapeResult:
        """
        Scrape Betfair for a specific sport.

        Args:
            sport: Our sport code ("afl", "nrl", etc.)
            limit: Max events to scrape

        Returns:
            ScrapeResult with events and lay odds
        """
        started_at = datetime.now(timezone.utc)
        events = []
        errors = []

        try:
            # Map sport to Betfair event type ID
            event_type_id = self.get_betfair_event_type_id(sport)
            if not event_type_id:
                errors.append(f"Unsupported sport for Betfair: {sport}")
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

            self.logger.info(f"Scraping Betfair for sport: {sport} (eventTypeId: {event_type_id})")

            # Get market catalogue (upcoming events)
            markets = await self.list_market_catalogue(
                event_type_id=event_type_id,
                market_type_codes=["MATCH_ODDS"],  # Head to head markets
                max_results=limit or 100
            )

            # Get current prices for markets
            market_ids = [m["marketId"] for m in markets]
            if market_ids:
                market_books = await self.list_market_book(market_ids)

                # Combine catalogue and book data
                events = self.parse_betfair_markets(markets, market_books, sport)

        except Exception as e:
            errors.append(f"Betfair scrape failed: {str(e)}")
            self.logger.exception(f"Betfair error for {sport}")

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

    def parse_betfair_markets(
        self,
        market_catalogues: List[Dict],
        market_books: List[Dict],
        sport: str
    ) -> List[ScrapedEvent]:
        """Parse Betfair market data into ScrapedEvent objects"""
        events = []

        # Create lookup dict for market books
        book_lookup = {book["marketId"]: book for book in market_books}

        for catalogue in market_catalogues:
            try:
                market_id = catalogue["marketId"]
                book = book_lookup.get(market_id)
                if not book:
                    continue

                event = self.parse_event(catalogue)
                event.sport = sport

                # Parse lay odds from market book
                odds = self.parse_odds(catalogue, book, event)
                event.odds = odds

                events.append(event)

            except Exception as e:
                self.logger.error(f"Failed to parse Betfair market: {e}")
                continue

        return events

    def parse_event(self, market_catalogue: Dict) -> ScrapedEvent:
        """Parse Betfair market catalogue into ScrapedEvent"""
        event_data = market_catalogue.get("event", {})
        competition = market_catalogue.get("competition", {}).get("name", "Unknown")

        return ScrapedEvent(
            external_id=event_data.get("id", ""),
            name=event_data.get("name", "Unknown Event"),
            sport="",  # Set by caller
            competition=competition,
            start_time=datetime.fromisoformat(market_catalogue.get("marketStartTime", "").replace("Z", "+00:00")),
            odds=[]
        )

    def parse_odds(self, catalogue: Dict, book: Dict, event: ScrapedEvent) -> List[ScrapedOdds]:
        """Parse Betfair lay odds from market book"""
        odds_list = []

        runners = catalogue.get("runners", [])
        runner_books = {r["selectionId"]: r for r in book.get("runners", [])}

        for runner in runners:
            selection_id = runner["selectionId"]
            runner_book = runner_books.get(selection_id)
            if not runner_book:
                continue

            # Get best available lay price
            lay_prices = runner_book.get("ex", {}).get("availableToLay", [])
            if not lay_prices:
                continue

            best_lay = lay_prices[0]  # First item is best price

            try:
                odds = ScrapedOdds(
                    event_external_id=event.external_id,
                    event_name=event.name,
                    sport=event.sport,
                    competition=event.competition,
                    start_time=event.start_time,
                    market_type="match_winner",
                    market_name=catalogue.get("marketName", "Unknown"),
                    selection_name=runner.get("runnerName", "Unknown"),
                    selection_key="other",  # Betfair uses selection IDs
                    decimal_odds=Decimal(str(best_lay["price"])),
                    bookmaker_code=self.bookmaker_code,
                    source_url=f"https://www.betfair.com.au/exchange/plus/market/{catalogue['marketId']}",
                    scraped_at=datetime.now(timezone.utc),
                    liquidity=Decimal(str(best_lay["size"]))  # Available liquidity in AUD
                )

                odds_list.append(odds)

            except Exception as e:
                self.logger.error(f"Failed to parse Betfair runner: {e}")
                continue

        return odds_list

    def get_betfair_event_type_id(self, sport: str) -> Optional[str]:
        """Map our sport codes to Betfair event type IDs"""
        mapping = {
            "afl": "61420",  # Australian Rules
            "nrl": "1477",   # Rugby League
            "cricket": "4",  # Cricket
            "tennis": "2",   # Tennis
            "soccer": "1",   # Soccer
            "basketball": "7522"  # Basketball
        }
        return mapping.get(sport)
