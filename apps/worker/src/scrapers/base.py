"""
Base scraper class for Australian bookmakers.
All scrapers inherit from this to ensure consistent interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ScraperStatus(str, Enum):
    """Status of a scraping operation"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass
class ScrapedOdds:
    """Single odds data point from a bookmaker"""
    # Event identification
    event_external_id: str
    event_name: str
    sport: str  # "afl", "nrl", etc.
    competition: str
    start_time: datetime

    # Market identification
    market_type: str  # "match_winner", "handicap", etc.
    market_name: str

    # Selection identification
    selection_name: str
    selection_key: str  # "home", "away", "draw"

    # Odds data
    decimal_odds: Decimal

    # Metadata
    bookmaker_code: str
    source_url: str
    scraped_at: datetime
    liquidity: Optional[Decimal] = None  # For exchanges


@dataclass
class ScrapedEvent:
    """Complete event with all markets and odds"""
    external_id: str
    name: str
    sport: str
    competition: str
    start_time: datetime
    home_team: Optional[str] = None
    away_team: Optional[str] = None
    venue: Optional[str] = None
    odds: List[ScrapedOdds] = None

    def __post_init__(self):
        if self.odds is None:
            self.odds = []


@dataclass
class ScrapeResult:
    """Result of a scraping operation"""
    bookmaker_code: str
    status: ScraperStatus
    events_scraped: int
    odds_scraped: int
    events: List[ScrapedEvent]
    errors: List[str]
    started_at: datetime
    completed_at: datetime

    @property
    def duration_seconds(self) -> float:
        """Calculate scrape duration in seconds"""
        return (self.completed_at - self.started_at).total_seconds()


class BaseScraper(ABC):
    """
    Base scraper class for Australian bookmakers.

    Each bookmaker scraper must implement:
    - scrape_sport(): Scrape all events for a given sport
    - parse_event(): Parse event HTML/JSON into ScrapedEvent
    - parse_odds(): Parse odds HTML/JSON into ScrapedOdds
    """

    def __init__(self, bookmaker_code: str, base_url: str, config: Optional[Dict[str, Any]] = None):
        self.bookmaker_code = bookmaker_code
        self.base_url = base_url
        self.config = config or {}
        self.logger = logging.getLogger(f"scraper.{bookmaker_code}")

        # Rate limiting
        self.rate_limit_seconds = self.config.get("rate_limit_seconds", 2)
        self.max_retries = self.config.get("max_retries", 3)
        self.timeout_seconds = self.config.get("timeout_seconds", 30)

        # Headers for requests
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        self.headers.update(self.config.get("headers", {}))

    @abstractmethod
    async def scrape_sport(self, sport: str, limit: Optional[int] = None) -> ScrapeResult:
        """
        Scrape all events for a given sport.

        Args:
            sport: Sport code (e.g., "afl", "nrl")
            limit: Optional limit on number of events to scrape

        Returns:
            ScrapeResult with all events and odds
        """
        pass

    @abstractmethod
    def parse_event(self, event_data: Any) -> ScrapedEvent:
        """
        Parse event data into ScrapedEvent.

        Args:
            event_data: Raw event data (HTML element, JSON, etc.)

        Returns:
            ScrapedEvent object
        """
        pass

    @abstractmethod
    def parse_odds(self, odds_data: Any, event: ScrapedEvent) -> List[ScrapedOdds]:
        """
        Parse odds data into list of ScrapedOdds.

        Args:
            odds_data: Raw odds data
            event: Parent event

        Returns:
            List of ScrapedOdds objects
        """
        pass

    def normalize_team_name(self, name: str) -> str:
        """
        Normalize team name for matching across bookmakers.

        Args:
            name: Raw team name from bookmaker

        Returns:
            Normalized team name
        """
        # Basic normalization
        normalized = name.strip()

        # Common replacements for Australian teams
        replacements = {
            "St Kilda": "St. Kilda",
            "GWS Giants": "Greater Western Sydney",
            "Western Bulldogs": "Footscray",
        }

        return replacements.get(normalized, normalized)

    def normalize_market_type(self, market_name: str) -> str:
        """
        Normalize market name to standard type.

        Args:
            market_name: Raw market name from bookmaker

        Returns:
            Standardized market type code
        """
        market_name_lower = market_name.lower()

        if any(x in market_name_lower for x in ["head to head", "h2h", "match winner", "winner", "match result", "result", "fight betting", "bout betting"]):
            return "match_winner"
        elif any(x in market_name_lower for x in ["line", "handicap", "spread"]):
            return "handicap"
        elif any(x in market_name_lower for x in ["total", "over/under", "o/u"]):
            return "total_points"
        else:
            return "other"

    def log_scrape_stats(self, result: ScrapeResult):
        """Log scraping statistics"""
        self.logger.info(
            f"Scrape completed: {result.bookmaker_code} | "
            f"Status: {result.status} | "
            f"Events: {result.events_scraped} | "
            f"Odds: {result.odds_scraped} | "
            f"Duration: {result.duration_seconds:.2f}s | "
            f"Errors: {len(result.errors)}"
        )

        if result.errors:
            for error in result.errors[:5]:  # Log first 5 errors
                self.logger.error(f"Scrape error: {error}")
