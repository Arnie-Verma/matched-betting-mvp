"""
Phase 1: Structural & Coverage Validation

Validates basic structure of scraped data:
- Event count sanity (vs expected per league)
- Event matching rate (normalized teams + start time)
- Market presence (moneyline has 2-3 outcomes)
- Odds bounds (1.01 <= odds <= 1001)
- Timestamp freshness (not stale)

Catches: dead scrapers, wrong pages, parsing failures (70-80% of issues)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Optional, Set

from validation.config import (
    ValidationConfig,
    ODDS_MIN,
    ODDS_MAX,
    FRESHNESS_THRESHOLD_SECONDS,
)

logger = logging.getLogger(__name__)


@dataclass
class OddsBoundsError:
    """Details of an odds value outside valid bounds."""
    event_name: str
    selection_name: str
    odds_value: Decimal
    bookmaker_code: str

    def __str__(self) -> str:
        return f"{self.event_name}: {self.selection_name} = {self.odds_value}"


@dataclass
class MarketValidation:
    """Validation result for a single market."""
    market_type: str
    expected_selections: int  # 2 for tennis/basketball, 3 for soccer
    actual_selections: int
    is_valid: bool
    missing_selections: List[str] = field(default_factory=list)


@dataclass
class StructuralValidation:
    """
    Phase 1 validation results for a single bookmaker.

    Contains all structural checks performed and their results.
    """
    bookmaker_code: str
    competition: str

    # Event count validation
    event_count: int
    expected_min: int
    expected_max: int
    event_count_valid: bool

    # Matching rate (calculated after comparison with reference)
    matching_rate: Decimal = Decimal("0")

    # Market validation
    markets_checked: int = 0
    markets_valid: int = 0
    market_errors: List[MarketValidation] = field(default_factory=list)

    # Odds bounds validation
    odds_checked: int = 0
    odds_in_bounds: int = 0
    odds_out_of_bounds: List[OddsBoundsError] = field(default_factory=list)

    # Selection coverage
    selections_expected: int = 0
    selections_found: int = 0
    missing_selections: List[str] = field(default_factory=list)

    # Freshness
    scraped_at: Optional[datetime] = None
    is_fresh: bool = True

    # Timing
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def passed(self) -> bool:
        """Check if all structural validations passed."""
        return (
            self.event_count_valid and
            len(self.odds_out_of_bounds) == 0 and
            self.is_fresh
        )

    @property
    def odds_valid_percent(self) -> Decimal:
        """Percentage of odds within valid bounds."""
        if self.odds_checked == 0:
            return Decimal("100")
        return Decimal(self.odds_in_bounds) / Decimal(self.odds_checked) * 100

    @property
    def market_valid_percent(self) -> Decimal:
        """Percentage of markets with correct structure."""
        if self.markets_checked == 0:
            return Decimal("100")
        return Decimal(self.markets_valid) / Decimal(self.markets_checked) * 100

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "bookmaker_code": self.bookmaker_code,
            "competition": self.competition,
            "event_count": self.event_count,
            "expected_min": self.expected_min,
            "expected_max": self.expected_max,
            "event_count_valid": self.event_count_valid,
            "matching_rate": str(self.matching_rate),
            "markets_checked": self.markets_checked,
            "markets_valid": self.markets_valid,
            "odds_checked": self.odds_checked,
            "odds_in_bounds": self.odds_in_bounds,
            "odds_out_of_bounds_count": len(self.odds_out_of_bounds),
            "is_fresh": self.is_fresh,
            "passed": self.passed,
            "validated_at": self.validated_at.isoformat(),
        }


class StructuralValidator:
    """
    Phase 1: Structural validation of scraped data.

    Validates:
    1. Event count sanity (min/max per competition)
    2. Odds bounds (1.01 - 1001)
    3. Market structure (correct number of selections)
    4. Timestamp freshness
    """

    def __init__(self, config: Optional[ValidationConfig] = None):
        """
        Initialize structural validator.

        Args:
            config: Validation configuration (uses defaults if None)
        """
        self.config = config or ValidationConfig()

    def validate(
        self,
        events: List[Dict],
        bookmaker_code: str,
        competition: str,
        scraped_at: Optional[datetime] = None
    ) -> StructuralValidation:
        """
        Run structural validation on scraped events.

        Args:
            events: List of scraped event dictionaries
            bookmaker_code: Bookmaker code being validated
            competition: Competition being validated
            scraped_at: When data was scraped (for freshness check)

        Returns:
            StructuralValidation with all check results
        """
        expected = self.config.get_expected_events(competition)

        # Initialize result
        result = StructuralValidation(
            bookmaker_code=bookmaker_code,
            competition=competition,
            event_count=len(events),
            expected_min=expected["min"],
            expected_max=expected["max"],
            event_count_valid=expected["min"] <= len(events) <= expected["max"],
            scraped_at=scraped_at,
        )

        # Check freshness
        if scraped_at:
            age_seconds = (datetime.now(timezone.utc) - scraped_at).total_seconds()
            result.is_fresh = age_seconds < FRESHNESS_THRESHOLD_SECONDS

        # Validate odds bounds and market structure
        for event in events:
            self._validate_event(event, result)

        # Log result
        log_level = logging.INFO if result.passed else logging.WARNING
        logger.log(
            log_level,
            f"[{bookmaker_code}] Structural validation: "
            f"events={result.event_count}/{expected['min']}-{expected['max']} "
            f"odds_valid={result.odds_in_bounds}/{result.odds_checked} "
            f"fresh={result.is_fresh} "
            f"passed={result.passed}"
        )

        return result

    def _validate_event(self, event: Dict, result: StructuralValidation):
        """
        Validate a single event's structure.

        Args:
            event: Event dictionary with odds data
            result: StructuralValidation to update
        """
        event_name = event.get("name", event.get("event_name", "Unknown"))
        odds_list = event.get("odds", [])

        # Track selections for this event
        selections_found: Set[str] = set()

        for odds in odds_list:
            result.odds_checked += 1

            # Get odds value
            odds_value = odds.get("decimal_odds") or odds.get("odds")
            if odds_value is None:
                continue

            # Convert to Decimal if needed
            if not isinstance(odds_value, Decimal):
                try:
                    odds_value = Decimal(str(odds_value))
                except Exception:
                    result.odds_out_of_bounds.append(OddsBoundsError(
                        event_name=event_name,
                        selection_name=odds.get("selection_name", "Unknown"),
                        odds_value=Decimal("0"),
                        bookmaker_code=result.bookmaker_code,
                    ))
                    continue

            # Check bounds
            if ODDS_MIN <= odds_value <= ODDS_MAX:
                result.odds_in_bounds += 1
            else:
                result.odds_out_of_bounds.append(OddsBoundsError(
                    event_name=event_name,
                    selection_name=odds.get("selection_name", "Unknown"),
                    odds_value=odds_value,
                    bookmaker_code=result.bookmaker_code,
                ))

            # Track selection
            selection_key = odds.get("selection_key", "").lower()
            if selection_key:
                selections_found.add(selection_key)

        # Validate market structure (for match_winner markets)
        market_type = self._get_primary_market_type(event)
        if market_type == "match_winner":
            result.markets_checked += 1
            expected_selections = self._get_expected_selections(event)

            if len(selections_found) >= expected_selections:
                result.markets_valid += 1
            else:
                result.market_errors.append(MarketValidation(
                    market_type=market_type,
                    expected_selections=expected_selections,
                    actual_selections=len(selections_found),
                    is_valid=False,
                    missing_selections=self._get_missing_selections(
                        selections_found, expected_selections
                    ),
                ))

    def _get_primary_market_type(self, event: Dict) -> str:
        """Determine primary market type for an event."""
        odds_list = event.get("odds", [])
        if not odds_list:
            return "unknown"

        # Check first odds item for market type
        first_odds = odds_list[0]
        market_type = first_odds.get("market_type", "").lower()

        if "winner" in market_type or "result" in market_type:
            return "match_winner"
        return market_type or "unknown"

    def _get_expected_selections(self, event: Dict) -> int:
        """
        Determine expected number of selections for an event.

        Soccer: 3 (home, away, draw)
        Basketball/Tennis/etc: 2 (home, away)
        """
        sport = event.get("sport", "").lower()

        if sport in ["soccer", "football"]:
            return 3
        else:
            return 2

    def _get_missing_selections(
        self,
        found: Set[str],
        expected_count: int
    ) -> List[str]:
        """Determine which selections are missing."""
        if expected_count == 3:
            expected = {"home", "away", "draw"}
        else:
            expected = {"home", "away"}

        return list(expected - found)

    def validate_from_scrape_result(
        self,
        result,  # ScrapeResult
        competition: str
    ) -> StructuralValidation:
        """
        Validate directly from a ScrapeResult object.

        Args:
            result: ScrapeResult from scraper
            competition: Competition being validated

        Returns:
            StructuralValidation with all check results
        """
        # Convert ScrapedEvents to dicts
        events = []
        for event in result.events:
            event_dict = {
                "name": event.name,
                "sport": event.sport,
                "odds": [
                    {
                        "decimal_odds": o.decimal_odds,
                        "selection_name": o.selection_name,
                        "selection_key": o.selection_key,
                        "market_type": o.market_type,
                    }
                    for o in event.odds
                ]
            }
            events.append(event_dict)

        return self.validate(
            events=events,
            bookmaker_code=result.bookmaker_code,
            competition=competition,
            scraped_at=result.completed_at,
        )
