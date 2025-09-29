# apps/api/src/api/scraping/base/scraper.py
"""Base scraper class with anti-detection and rate limiting for Australian bookmakers"""
import asyncio
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

import httpx
from sqlalchemy.orm import Session

from api.models import Bookmaker, Event, Market, Selection, OddsSnapshot, SourceType


class ScrapeStatus(str, Enum):
    """Scraping operation status"""
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    NO_DATA = "no_data"
    RATE_LIMITED = "rate_limited"


@dataclass
class ScrapeResult:
    """Result of a scraping operation"""
    status: ScrapeStatus
    odds_count: int = 0
    message: str = ""
    processing_time_ms: int = 0
    confidence_score: float = 1.0
    raw_data: Optional[Dict] = None


@dataclass
class OddsData:
    """Structured odds data from scraping"""
    event_external_id: str
    event_name: str
    home_team: str
    away_team: str
    home_odds: float
    away_odds: float
    market_type: str = "match_winner"
    timestamp: Optional[datetime] = None


class BaseScraper(ABC):
    """Base scraper class with anti-detection and rate limiting"""

    def __init__(self, bookmaker: Bookmaker, db: Session):
        self.bookmaker = bookmaker
        self.db = db
        self.session_id = f"scrape_{int(time.time())}_{random.randint(1000, 9999)}"

        # Anti-detection settings
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]

        # Rate limiting
        self.last_request_time = 0
        self.min_delay_seconds = bookmaker.rate_limit_seconds
        self.max_delay_seconds = self.min_delay_seconds * 2

        # Configure HTTP client
        self.client = None
        self._setup_http_client()

    def _setup_http_client(self):
        """Setup HTTP client with realistic browser headers"""
        headers = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9,en-US;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }

        # Add bookmaker-specific headers if configured
        if self.bookmaker.scraping_config and "headers" in self.bookmaker.scraping_config:
            headers.update(self.bookmaker.scraping_config["headers"])

        self.client = httpx.AsyncClient(
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

    async def _rate_limit(self):
        """Implement rate limiting with random delays"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.min_delay_seconds:
            # Add random jitter to avoid patterns
            delay = self.min_delay_seconds - time_since_last_request
            jitter = random.uniform(0.5, 2.0)  # Add 0.5-2 seconds of randomness
            total_delay = delay + jitter

            await asyncio.sleep(total_delay)

        self.last_request_time = time.time()

    async def _make_request(self, url: str, **kwargs) -> Tuple[httpx.Response, int]:
        """Make HTTP request with rate limiting and error handling"""
        await self._rate_limit()
        start_time = time.time()

        try:
            response = await self.client.get(url, **kwargs)
            processing_time_ms = int((time.time() - start_time) * 1000)
            return response, processing_time_ms

        except httpx.TimeoutException:
            processing_time_ms = int((time.time() - start_time) * 1000)
            raise Exception(f"Request timeout after {processing_time_ms}ms")
        except httpx.RequestError as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            raise Exception(f"Request failed: {str(e)}")

    def _calculate_confidence_score(self, response: httpx.Response, odds_count: int) -> float:
        """Calculate confidence score based on response quality"""
        score = 1.0

        # Reduce score for non-200 responses
        if response.status_code != 200:
            score -= 0.3

        # Reduce score if very few odds found
        if odds_count == 0:
            score = 0.0
        elif odds_count < 3:
            score -= 0.2

        # Reduce score for suspicious response indicators
        content = response.text.lower()
        if any(indicator in content for indicator in ["blocked", "captcha", "bot", "rate limit"]):
            score -= 0.5

        return max(0.0, score)

    async def _store_odds_data(self, odds_data_list: List[OddsData], confidence_score: float) -> int:
        """Store scraped odds data in database"""
        odds_count = 0
        current_time = datetime.now(timezone.utc)

        for odds_data in odds_data_list:
            try:
                # Find the event and market (simplified for now)
                # In production, we'd implement proper event/market matching
                # For now, we'll create basic records to test the framework

                odds_count += 2  # Home and away odds

                # This is a placeholder - we'll implement proper data storage
                # when we have actual scraped data to work with
                print(f"Would store: {odds_data.event_name} - "
                      f"Home: {odds_data.home_odds}, Away: {odds_data.away_odds}")

            except Exception as e:
                print(f"Error storing odds data: {e}")
                continue

        return odds_count

    async def scrape_nbl_head_to_head(self) -> ScrapeResult:
        """Main method to scrape NBL Head-to-Head markets"""
        start_time = time.time()

        try:
            # Get the sport-specific scraping URL
            scrape_url = await self._get_nbl_url()
            if not scrape_url:
                return ScrapeResult(
                    status=ScrapeStatus.FAILED,
                    message="Could not determine NBL URL for this bookmaker",
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )

            # Make the HTTP request
            response, request_time_ms = await self._make_request(scrape_url)

            # Check for blocking/rate limiting
            if response.status_code == 429:
                return ScrapeResult(
                    status=ScrapeStatus.RATE_LIMITED,
                    message="Rate limited by bookmaker",
                    processing_time_ms=request_time_ms
                )

            if response.status_code == 403:
                return ScrapeResult(
                    status=ScrapeStatus.BLOCKED,
                    message="Blocked by bookmaker",
                    processing_time_ms=request_time_ms
                )

            # Parse the odds data
            odds_data_list = await self._parse_nbl_odds(response)

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(response, len(odds_data_list))

            # Store in database
            odds_count = await self._store_odds_data(odds_data_list, confidence_score)

            total_time_ms = int((time.time() - start_time) * 1000)

            if odds_count > 0:
                return ScrapeResult(
                    status=ScrapeStatus.SUCCESS,
                    odds_count=odds_count,
                    message=f"Successfully scraped {odds_count} odds",
                    processing_time_ms=total_time_ms,
                    confidence_score=confidence_score
                )
            else:
                return ScrapeResult(
                    status=ScrapeStatus.NO_DATA,
                    message="No odds data found",
                    processing_time_ms=total_time_ms,
                    confidence_score=confidence_score
                )

        except Exception as e:
            total_time_ms = int((time.time() - start_time) * 1000)
            return ScrapeResult(
                status=ScrapeStatus.FAILED,
                message=f"Scraping failed: {str(e)}",
                processing_time_ms=total_time_ms
            )

    @abstractmethod
    async def _get_nbl_url(self) -> Optional[str]:
        """Get the NBL betting URL for this bookmaker"""
        pass

    @abstractmethod
    async def _parse_nbl_odds(self, response: httpx.Response) -> List[OddsData]:
        """Parse NBL odds from the response"""
        pass

    async def close(self):
        """Clean up resources"""
        if self.client:
            await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()