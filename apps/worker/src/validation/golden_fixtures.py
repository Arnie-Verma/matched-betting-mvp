"""
Phase 3: Golden Fixtures (Regression Safety)

Curated fixtures per league that ALWAYS get validated:
- 5-10 high-profile matches per league
- Always scrape, always validate
- Structure + odds band validation

Catches: regressions after code changes
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Optional, Set, Tuple

from validation.config import ValidationConfig, GOLDEN_FIXTURES

logger = logging.getLogger(__name__)


@dataclass
class GoldenFixtureResult:
    """Validation result for a single golden fixture."""
    fixture_name: str  # Human-readable name (e.g., "Arsenal v Chelsea")
    home_team: str
    away_team: str

    # Was the fixture found in scraped data?
    found: bool

    # Selection validation
    expected_selections: List[str]
    found_selections: List[str] = field(default_factory=list)
    selections_valid: bool = False

    # Odds validation
    odds_in_band: bool = False  # Are odds in reasonable range (1.01 - 100)?
    odds_values: Dict[str, Decimal] = field(default_factory=dict)  # selection -> odds

    @property
    def passed(self) -> bool:
        """Check if golden fixture validation passed."""
        return self.found and self.selections_valid and self.odds_in_band

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "fixture_name": self.fixture_name,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "found": self.found,
            "expected_selections": self.expected_selections,
            "found_selections": self.found_selections,
            "selections_valid": self.selections_valid,
            "odds_in_band": self.odds_in_band,
            "odds_values": {k: str(v) for k, v in self.odds_values.items()},
            "passed": self.passed,
        }


@dataclass
class GoldenFixturesValidation:
    """Phase 3 validation results for a single bookmaker."""
    bookmaker_code: str
    competition: str

    # Fixture results
    fixtures_expected: int
    fixtures_found: int = 0
    fixtures_passed: int = 0
    results: List[GoldenFixtureResult] = field(default_factory=list)

    # Timing
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def passed(self) -> bool:
        """Check if golden fixtures validation passed."""
        if self.fixtures_expected == 0:
            return True  # No golden fixtures defined for this competition

        # Fail if more than half of golden fixtures are missing/failed
        return self.fixtures_passed >= (self.fixtures_expected // 2 + 1)

    @property
    def coverage_percent(self) -> Decimal:
        """Percentage of golden fixtures found."""
        if self.fixtures_expected == 0:
            return Decimal("100")
        return Decimal(self.fixtures_found) / Decimal(self.fixtures_expected) * 100

    @property
    def pass_rate(self) -> Decimal:
        """Percentage of golden fixtures that passed all checks."""
        if self.fixtures_expected == 0:
            return Decimal("100")
        return Decimal(self.fixtures_passed) / Decimal(self.fixtures_expected) * 100

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "bookmaker_code": self.bookmaker_code,
            "competition": self.competition,
            "fixtures_expected": self.fixtures_expected,
            "fixtures_found": self.fixtures_found,
            "fixtures_passed": self.fixtures_passed,
            "coverage_percent": str(self.coverage_percent),
            "pass_rate": str(self.pass_rate),
            "passed": self.passed,
            "results": [r.to_dict() for r in self.results],
            "validated_at": self.validated_at.isoformat(),
        }


class GoldenFixturesValidator:
    """
    Phase 3: Golden fixtures validation.

    Validates that curated high-profile fixtures are:
    1. Present in scraped data
    2. Have all expected selections (home/away/draw)
    3. Have odds in reasonable range
    """

    def __init__(self, config: Optional[ValidationConfig] = None):
        """
        Initialize golden fixtures validator.

        Args:
            config: Validation configuration (uses defaults if None)
        """
        self.config = config or ValidationConfig()

    def validate(
        self,
        events: Dict[str, Dict],
        bookmaker_code: str,
        competition: str,
        fixtures_override: Optional[List[Tuple[str, str, List[str]]]] = None,
    ) -> GoldenFixturesValidation:
        """
        Validate golden fixtures for a bookmaker.

        Args:
            events: Dict of {event_key: event_data} with normalized keys
            bookmaker_code: Bookmaker being validated
            competition: Competition being validated

        Returns:
            GoldenFixturesValidation with all check results
        """
        golden_fixtures = (
            fixtures_override
            if fixtures_override is not None
            else self.config.get_golden_fixtures(competition)
        )

        result = GoldenFixturesValidation(
            bookmaker_code=bookmaker_code,
            competition=competition,
            fixtures_expected=len(golden_fixtures),
        )

        for home, away, expected_selections in golden_fixtures:
            fixture_result = self._validate_fixture(
                events=events,
                home_team=home,
                away_team=away,
                expected_selections=expected_selections,
            )
            result.results.append(fixture_result)

            if fixture_result.found:
                result.fixtures_found += 1
            if fixture_result.passed:
                result.fixtures_passed += 1

        # Log result
        if result.fixtures_expected > 0:
            log_level = logging.INFO if result.passed else logging.WARNING
            logger.log(
                log_level,
                f"[{bookmaker_code}] Golden fixtures: "
                f"found={result.fixtures_found}/{result.fixtures_expected} "
                f"passed={result.fixtures_passed}/{result.fixtures_expected}"
            )

        return result

    def _validate_fixture(
        self,
        events: Dict[str, Dict],
        home_team: str,
        away_team: str,
        expected_selections: List[str],
    ) -> GoldenFixtureResult:
        """
        Validate a single golden fixture.

        Args:
            events: Dict of {event_key: event_data}
            home_team: Normalized home team name
            away_team: Normalized away team name
            expected_selections: List of expected selections (home/away/draw)

        Returns:
            GoldenFixtureResult with validation details
        """
        fixture_name = f"{home_team} v {away_team}"

        # Generate possible event keys (both orderings)
        # Golden fixtures are stored as (home, away) but events might be sorted alphabetically
        possible_keys = [
            f"{home_team}v{away_team}",
            f"{away_team}v{home_team}",
            # Also try with sorting (how normalize_event works)
            "v".join(sorted([home_team, away_team])),
        ]

        # Find matching event
        matching_event = None
        for key in possible_keys:
            if key in events:
                matching_event = events[key]
                break

        if not matching_event:
            return GoldenFixtureResult(
                fixture_name=fixture_name,
                home_team=home_team,
                away_team=away_team,
                found=False,
                expected_selections=expected_selections,
            )

        # Extract selections from event
        found_selections: Set[str] = set()
        odds_values: Dict[str, Decimal] = {}

        odds_list = matching_event.get("odds", [])
        for odds in odds_list:
            selection_key = odds.get("selection_key", "").lower()
            if selection_key:
                found_selections.add(selection_key)

                # Get odds value
                odds_value = odds.get("decimal_odds") or odds.get("odds")
                if odds_value is not None:
                    if not isinstance(odds_value, Decimal):
                        try:
                            odds_value = Decimal(str(odds_value))
                        except Exception:
                            odds_value = None

                    if odds_value is not None:
                        odds_values[selection_key] = odds_value

        # Validate selections
        selections_valid = set(expected_selections).issubset(found_selections)

        # Validate odds in band (1.01 - 100 for golden fixtures)
        odds_in_band = all(
            Decimal("1.01") <= odds <= Decimal("100")
            for odds in odds_values.values()
        ) if odds_values else False

        return GoldenFixtureResult(
            fixture_name=fixture_name,
            home_team=home_team,
            away_team=away_team,
            found=True,
            expected_selections=expected_selections,
            found_selections=list(found_selections),
            selections_valid=selections_valid,
            odds_in_band=odds_in_band,
            odds_values=odds_values,
        )

    def validate_from_scrape_result(
        self,
        result,  # ScrapeResult
        competition: str,
        fixtures_override: Optional[List[Tuple[str, str, List[str]]]] = None,
    ) -> GoldenFixturesValidation:
        """
        Validate golden fixtures from a ScrapeResult object.

        Args:
            result: ScrapeResult from scraper
            competition: Competition being validated

        Returns:
            GoldenFixturesValidation with all check results
        """
        # Import here to avoid circular dependency
        import sys
        sys.path.insert(0, "apps/api/src")
        from api.services.normalization_service import normalize_event_name

        # Convert events to dict with normalized keys
        events: Dict[str, Dict] = {}
        for event in result.events:
            event_key = normalize_event_name(event.name)

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
            events[event_key] = event_dict

        return self.validate(
            events=events,
            bookmaker_code=result.bookmaker_code,
            competition=competition,
            fixtures_override=fixtures_override,
        )

    def get_golden_fixture_summary(
        self,
        all_results: Dict[str, GoldenFixturesValidation],
        competition: str,
        fixtures_override: Optional[List[Tuple[str, str, List[str]]]] = None,
    ) -> Dict[str, Dict]:
        """
        Get summary of golden fixture coverage across all bookmakers.

        Args:
            all_results: Dict of {bookmaker_code: validation_result}
            competition: Competition to summarize

        Returns:
            Dict with per-fixture summary across bookmakers
        """
        golden_fixtures = (
            fixtures_override
            if fixtures_override is not None
            else self.config.get_golden_fixtures(competition)
        )
        summary: Dict[str, Dict] = {}

        for home, away, _ in golden_fixtures:
            fixture_key = f"{home}v{away}"
            fixture_name = f"{home} v {away}"

            found_in = []
            passed_in = []

            for bookmaker_code, validation in all_results.items():
                for fixture_result in validation.results:
                    if (fixture_result.home_team == home and
                        fixture_result.away_team == away):
                        if fixture_result.found:
                            found_in.append(bookmaker_code)
                        if fixture_result.passed:
                            passed_in.append(bookmaker_code)

            summary[fixture_key] = {
                "fixture_name": fixture_name,
                "found_in": found_in,
                "found_count": len(found_in),
                "passed_in": passed_in,
                "passed_count": len(passed_in),
                "total_bookmakers": len(all_results),
            }

        return summary
