"""
Tests for the Validation Framework

Tests all 4 phases of validation:
- Phase 1: Structural validation
- Phase 2: Probability validation
- Phase 3: Golden fixtures validation
- Phase 4: Score calculation
"""
import pytest
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Add paths for imports
sys.path.insert(0, "apps/worker/src")
sys.path.insert(0, "apps/api/src")

from validation.config import (
    ValidationConfig,
    EXPECTED_EVENTS,
    PROBABILITY_THRESHOLDS,
    GOLDEN_FIXTURES,
    ODDS_MIN,
    ODDS_MAX,
    EVENT_COVERAGE_FAIL_THRESHOLD,
    EVENT_COVERAGE_WARN_THRESHOLD,
)
from validation.structural_validator import StructuralValidator, StructuralValidation
from validation.probability_validator import ProbabilityValidator, ProbabilityValidation
from validation.golden_fixtures import GoldenFixturesValidator, GoldenFixturesValidation
from validation.score_calculator import ScoreCalculator, ValidationScore
from validation.report_generator import ReportGenerator, ValidationReport
from validation.pipeline import ValidationPipeline
from scrapers.base import ScrapeResult, ScrapedEvent, ScrapedOdds, ScraperStatus
from api.services.normalization_service import normalize_competition_name, normalize_event_name


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def config():
    """Default validation config."""
    return ValidationConfig()


@pytest.fixture
def structural_validator(config):
    """Structural validator instance."""
    return StructuralValidator(config)


@pytest.fixture
def probability_validator(config):
    """Probability validator instance."""
    return ProbabilityValidator(config)


@pytest.fixture
def golden_validator(config):
    """Golden fixtures validator instance."""
    return GoldenFixturesValidator(config)


@pytest.fixture
def score_calculator(config):
    """Score calculator instance."""
    return ScoreCalculator(config)


@pytest.fixture
def sample_events():
    """Sample events for testing."""
    return [
        {
            "name": "Arsenal v Chelsea",
            "sport": "soccer",
            "odds": [
                {"decimal_odds": Decimal("2.10"), "selection_name": "Arsenal", "selection_key": "home", "market_type": "match_winner"},
                {"decimal_odds": Decimal("3.50"), "selection_name": "Draw", "selection_key": "draw", "market_type": "match_winner"},
                {"decimal_odds": Decimal("3.20"), "selection_name": "Chelsea", "selection_key": "away", "market_type": "match_winner"},
            ]
        },
        {
            "name": "Liverpool v Man Utd",
            "sport": "soccer",
            "odds": [
                {"decimal_odds": Decimal("1.80"), "selection_name": "Liverpool", "selection_key": "home", "market_type": "match_winner"},
                {"decimal_odds": Decimal("3.80"), "selection_name": "Draw", "selection_key": "draw", "market_type": "match_winner"},
                {"decimal_odds": Decimal("4.50"), "selection_name": "Man Utd", "selection_key": "away", "market_type": "match_winner"},
            ]
        },
        {
            "name": "Man City v Tottenham",
            "sport": "soccer",
            "odds": [
                {"decimal_odds": Decimal("1.45"), "selection_name": "Man City", "selection_key": "home", "market_type": "match_winner"},
                {"decimal_odds": Decimal("4.50"), "selection_name": "Draw", "selection_key": "draw", "market_type": "match_winner"},
                {"decimal_odds": Decimal("7.00"), "selection_name": "Tottenham", "selection_key": "away", "market_type": "match_winner"},
            ]
        },
    ]


@pytest.fixture
def sample_events_with_invalid_odds(sample_events):
    """Sample events with some invalid odds."""
    events = sample_events.copy()
    # Add event with out-of-bounds odds
    events.append({
        "name": "Invalid Match",
        "sport": "soccer",
        "odds": [
            {"decimal_odds": Decimal("0.50"), "selection_name": "Team A", "selection_key": "home", "market_type": "match_winner"},
            {"decimal_odds": Decimal("1500"), "selection_name": "Team B", "selection_key": "away", "market_type": "match_winner"},
        ]
    })
    return events


def build_scrape_result(
    bookmaker_code: str,
    competition: str,
    events_data: list[dict],
) -> ScrapeResult:
    """Build a ScrapeResult with deterministic match-winner selections."""
    now = datetime.now(timezone.utc)
    events: list[ScrapedEvent] = []
    odds_count = 0

    for idx, event_data in enumerate(events_data):
        event_name = event_data["name"]
        sport = event_data.get("sport", "soccer")
        start_time = now + timedelta(days=1, minutes=idx)
        scraped_odds: list[ScrapedOdds] = []

        for selection in event_data["selections"]:
            selection_key = selection["selection_key"]
            selection_name = selection.get("selection_name", selection_key.title())
            decimal_odds = Decimal(str(selection["decimal_odds"]))

            scraped_odds.append(
                ScrapedOdds(
                    event_external_id=f"{bookmaker_code}-{idx}",
                    event_name=event_name,
                    sport=sport,
                    competition=competition,
                    start_time=start_time,
                    market_type="match_winner",
                    market_name="Match Winner",
                    selection_name=selection_name,
                    selection_key=selection_key,
                    decimal_odds=decimal_odds,
                    bookmaker_code=bookmaker_code,
                    source_url="https://example.com",
                    scraped_at=now,
                )
            )
            odds_count += 1

        events.append(
            ScrapedEvent(
                external_id=f"{bookmaker_code}-{idx}",
                name=event_name,
                sport=sport,
                competition=competition,
                start_time=start_time,
                odds=scraped_odds,
            )
        )

    return ScrapeResult(
        bookmaker_code=bookmaker_code,
        status=ScraperStatus.SUCCESS,
        events_scraped=len(events),
        odds_scraped=odds_count,
        events=events,
        errors=[],
        started_at=now - timedelta(seconds=3),
        completed_at=now,
    )


# =============================================================================
# Phase 1: Structural Validator Tests
# =============================================================================

class TestStructuralValidator:
    """Tests for Phase 1 structural validation."""

    def test_valid_event_count(self, structural_validator, sample_events):
        """Test validation passes with correct event count."""
        result = structural_validator.validate(
            events=sample_events,
            bookmaker_code="testbook",
            competition="epl",
            scraped_at=datetime.now(timezone.utc),
        )

        assert result.event_count == 3
        assert result.event_count_valid is True
        assert result.passed is True

    def test_event_count_too_low(self, structural_validator):
        """Test validation fails with too few events."""
        result = structural_validator.validate(
            events=[{"name": "Single Event", "sport": "soccer", "odds": []}],
            bookmaker_code="testbook",
            competition="epl",
            scraped_at=datetime.now(timezone.utc),
        )

        assert result.event_count == 1
        assert result.event_count_valid is False

    def test_event_count_too_high(self, structural_validator):
        """Test validation warns with too many events."""
        many_events = [
            {"name": f"Event {i}", "sport": "soccer", "odds": []}
            for i in range(25)
        ]

        result = structural_validator.validate(
            events=many_events,
            bookmaker_code="testbook",
            competition="laliga",
            scraped_at=datetime.now(timezone.utc),
        )

        assert result.event_count == 25
        assert result.event_count_valid is False

    def test_odds_bounds_validation(self, structural_validator, sample_events_with_invalid_odds):
        """Test odds bounds validation catches out-of-range values."""
        result = structural_validator.validate(
            events=sample_events_with_invalid_odds,
            bookmaker_code="testbook",
            competition="epl",
            scraped_at=datetime.now(timezone.utc),
        )

        assert len(result.odds_out_of_bounds) == 2
        assert result.passed is False

    def test_freshness_validation(self, structural_validator, sample_events):
        """Test freshness validation for stale data."""
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=20)

        result = structural_validator.validate(
            events=sample_events,
            bookmaker_code="testbook",
            competition="epl",
            scraped_at=stale_time,
        )

        assert result.is_fresh is False

    def test_fresh_data(self, structural_validator, sample_events):
        """Test freshness validation passes for recent data."""
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=5)

        result = structural_validator.validate(
            events=sample_events,
            bookmaker_code="testbook",
            competition="epl",
            scraped_at=recent_time,
        )

        assert result.is_fresh is True

    def test_to_dict(self, structural_validator, sample_events):
        """Test serialization to dictionary."""
        result = structural_validator.validate(
            events=sample_events,
            bookmaker_code="testbook",
            competition="epl",
            scraped_at=datetime.now(timezone.utc),
        )

        result_dict = result.to_dict()
        assert "bookmaker_code" in result_dict
        assert "event_count" in result_dict
        assert "passed" in result_dict


# =============================================================================
# Phase 2: Probability Validator Tests
# =============================================================================

class TestProbabilityValidator:
    """Tests for Phase 2 probability validation."""

    def test_odds_to_probability(self):
        """Test odds to probability conversion."""
        assert ProbabilityValidator.odds_to_probability(Decimal("2.00")) == Decimal("50.00")
        assert ProbabilityValidator.odds_to_probability(Decimal("4.00")) == Decimal("25.00")
        assert ProbabilityValidator.odds_to_probability(Decimal("1.50")) == Decimal("66.67")

    def test_probability_gap(self):
        """Test probability gap calculation."""
        # 2.00 (50%) vs 2.20 (45.45%) = 4.55pp
        gap = ProbabilityValidator.probability_gap(Decimal("2.00"), Decimal("2.20"))
        assert gap == Decimal("4.55")

    def test_valid_odds_comparison(self, probability_validator):
        """Test odds comparison within threshold."""
        bookmaker_odds = {
            "arsenalvchelsea": {
                "home": {"decimal_odds": Decimal("2.10"), "selection_name": "Arsenal", "market_type": "match_winner"},
            }
        }

        reference_odds = {
            "arsenalvchelsea": {
                "home": {"decimal_odds": Decimal("2.15"), "selection_name": "Arsenal", "market_type": "match_winner"},
            }
        }

        result = probability_validator.validate(
            bookmaker_odds=bookmaker_odds,
            reference_odds=reference_odds,
            bookmaker_code="testbook",
            competition="epl",
        )

        assert result.odds_compared == 1
        assert result.odds_matched == 1
        assert result.odds_warn == 0
        assert result.odds_critical == 0
        assert result.passed is True

    def test_odds_warn_threshold(self, probability_validator):
        """Test odds flagged as warning when exceeding warn threshold."""
        bookmaker_odds = {
            "arsenalvchelsea": {
                "home": {"decimal_odds": Decimal("2.00"), "selection_name": "Arsenal", "market_type": "match_winner"},
            }
        }

        # 2.00 (50%) vs 2.40 (41.67%) = 8.33pp gap - should be critical
        reference_odds = {
            "arsenalvchelsea": {
                "home": {"decimal_odds": Decimal("2.40"), "selection_name": "Arsenal", "market_type": "match_winner"},
            }
        }

        result = probability_validator.validate(
            bookmaker_odds=bookmaker_odds,
            reference_odds=reference_odds,
            bookmaker_code="testbook",
            competition="epl",
        )

        assert result.odds_compared == 1
        # 8.33pp gap exceeds 6pp fail threshold
        assert result.odds_critical == 1

    def test_exchange_skipped(self, probability_validator):
        """Test exchange bookmakers are skipped in probability validation."""
        result = probability_validator.validate(
            bookmaker_odds={},
            reference_odds={},
            bookmaker_code="betfair",
            competition="epl",
        )

        assert result.odds_compared == 0

    def test_get_thresholds_longshot(self, probability_validator):
        """Test thresholds are wider for longshots."""
        # Favorite odds (< 5.0)
        fav_warn, fav_fail = probability_validator.get_thresholds(
            Decimal("2.00"), "match_winner"
        )

        # Longshot odds (> 5.0)
        long_warn, long_fail = probability_validator.get_thresholds(
            Decimal("10.00"), "match_winner"
        )

        assert long_warn > fav_warn
        assert long_fail > fav_fail


# =============================================================================
# Phase 3: Golden Fixtures Validator Tests
# =============================================================================

class TestGoldenFixturesValidator:
    """Tests for Phase 3 golden fixtures validation."""

    def test_fixture_found(self, golden_validator):
        """Test golden fixture is found and validated."""
        events = {
            "arsenalvchelsea": {
                "name": "Arsenal v Chelsea",
                "odds": [
                    {"decimal_odds": Decimal("2.10"), "selection_key": "home"},
                    {"decimal_odds": Decimal("3.50"), "selection_key": "draw"},
                    {"decimal_odds": Decimal("3.20"), "selection_key": "away"},
                ]
            }
        }

        result = golden_validator.validate(
            events=events,
            bookmaker_code="testbook",
            competition="epl",
        )

        assert result.fixtures_found >= 1
        assert any(r.found for r in result.results if r.home_team == "arsenal")

    def test_fixture_not_found(self, golden_validator):
        """Test missing golden fixture is detected."""
        events = {}  # No events

        result = golden_validator.validate(
            events=events,
            bookmaker_code="testbook",
            competition="epl",
        )

        assert result.fixtures_found == 0
        assert not any(r.found for r in result.results)

    def test_missing_selections(self, golden_validator):
        """Test validation fails when selections are missing."""
        events = {
            "arsenalvchelsea": {
                "name": "Arsenal v Chelsea",
                "odds": [
                    {"decimal_odds": Decimal("2.10"), "selection_key": "home"},
                    # Missing draw and away
                ]
            }
        }

        result = golden_validator.validate(
            events=events,
            bookmaker_code="testbook",
            competition="epl",
        )

        arsenal_result = next(
            (r for r in result.results if r.home_team == "arsenal"),
            None
        )

        if arsenal_result:
            assert arsenal_result.found is True
            assert arsenal_result.selections_valid is False

    def test_odds_out_of_band(self, golden_validator):
        """Test odds outside reasonable band are flagged."""
        events = {
            "arsenalvchelsea": {
                "name": "Arsenal v Chelsea",
                "odds": [
                    {"decimal_odds": Decimal("200"), "selection_key": "home"},  # Too high
                    {"decimal_odds": Decimal("3.50"), "selection_key": "draw"},
                    {"decimal_odds": Decimal("3.20"), "selection_key": "away"},
                ]
            }
        }

        result = golden_validator.validate(
            events=events,
            bookmaker_code="testbook",
            competition="epl",
        )

        arsenal_result = next(
            (r for r in result.results if r.home_team == "arsenal"),
            None
        )

        if arsenal_result:
            assert arsenal_result.odds_in_band is False


# =============================================================================
# Phase 4: Score Calculator Tests
# =============================================================================

class TestScoreCalculator:
    """Tests for Phase 4 score calculation."""

    def test_pass_score(self, score_calculator, structural_validator, sample_events):
        """Test PASS score when all validations pass."""
        structural = structural_validator.validate(
            events=sample_events,
            bookmaker_code="testbook",
            competition="epl",
            scraped_at=datetime.now(timezone.utc),
        )
        structural.matching_rate = Decimal("100")

        # Mock probability validation result
        probability = ProbabilityValidation(
            bookmaker_code="testbook",
            competition="epl",
            odds_compared=10,
            odds_matched=10,
            odds_warn=0,
            odds_critical=0,
        )

        # Mock golden fixtures result
        golden = GoldenFixturesValidation(
            bookmaker_code="testbook",
            competition="epl",
            fixtures_expected=4,
            fixtures_found=4,
            fixtures_passed=4,
        )

        score = score_calculator.calculate(
            structural=structural,
            probability=probability,
            golden=golden,
            bookmaker_code="testbook",
            competition="epl",
        )

        assert score.status == "PASS"

    def test_fail_score_structural(self, score_calculator):
        """Test FAIL score when structural validation fails badly."""
        # No events = FAIL
        structural = StructuralValidation(
            bookmaker_code="testbook",
            competition="epl",
            event_count=0,
            expected_min=3,
            expected_max=20,
            event_count_valid=False,
        )

        score = score_calculator.calculate(
            structural=structural,
            probability=None,
            golden=None,
            bookmaker_code="testbook",
            competition="epl",
        )

        assert score.status == "FAIL"
        assert "Structural validation failed" in score.failure_reasons or score.event_count == 0

    def test_fail_score_critical_anomalies(self, score_calculator):
        """Test FAIL score when too many critical anomalies."""
        probability = ProbabilityValidation(
            bookmaker_code="testbook",
            competition="epl",
            odds_compared=10,
            odds_matched=5,
            odds_warn=2,
            odds_critical=6,  # More than epl critical anomaly threshold (5)
        )

        score = score_calculator.calculate(
            structural=None,
            probability=probability,
            golden=None,
            bookmaker_code="testbook",
            competition="laliga",
        )

        assert score.status == "FAIL"

    def test_warn_score_low_coverage(self, score_calculator):
        """Test WARN score when coverage is below threshold."""
        # Create probability with many anomalies to trigger WARN
        # The score calculator uses the anomaly count, not coverage directly
        from validation.probability_validator import OddsAnomaly

        anomalies = [
            OddsAnomaly(
                event_name=f"Event {i}",
                event_key=f"event{i}",
                selection_name="Home",
                selection_key="home",
                bookmaker_code="testbook",
                bookmaker_odds=Decimal("2.00"),
                bookmaker_probability=Decimal("50.00"),
                reference_odds=Decimal("2.50"),
                reference_probability=Decimal("40.00"),
                reference_source="ladbrokes",
                probability_gap=Decimal("10.0"),
                severity="warn",
            )
            for i in range(6)  # 6 anomalies > MAX_ANOMALIES_WARN (5)
        ]

        probability = ProbabilityValidation(
            bookmaker_code="testbook",
            competition="laliga",
            odds_compared=10,
            odds_matched=4,
            odds_warn=6,
            odds_critical=0,
            anomalies=anomalies,
        )

        score = score_calculator.calculate(
            structural=None,
            probability=probability,
            golden=None,
            bookmaker_code="testbook",
            competition="laliga",
        )

        assert score.status == "WARN"

    def test_fail_score_low_event_coverage(self, score_calculator):
        """Test FAIL score when event coverage is below threshold."""
        structural = StructuralValidation(
            bookmaker_code="testbook",
            competition="laliga",
            event_count=5,
            expected_min=3,
            expected_max=20,
            event_count_valid=True,
            matching_rate=EVENT_COVERAGE_FAIL_THRESHOLD - Decimal("1"),
        )

        score = score_calculator.calculate(
            structural=structural,
            probability=None,
            golden=None,
            bookmaker_code="testbook",
            competition="laliga",
        )

        assert score.status == "FAIL"

    def test_warn_score_low_event_coverage(self, score_calculator):
        """Test WARN score when event coverage is below warn threshold."""
        structural = StructuralValidation(
            bookmaker_code="testbook",
            competition="laliga",
            event_count=5,
            expected_min=3,
            expected_max=20,
            event_count_valid=True,
            matching_rate=EVENT_COVERAGE_WARN_THRESHOLD - Decimal("1"),
        )

        score = score_calculator.calculate(
            structural=structural,
            probability=None,
            golden=None,
            bookmaker_code="testbook",
            competition="laliga",
        )

        assert score.status == "WARN"

    def test_exchange_structure_only(self, score_calculator):
        """Test exchanges get structure-only validation."""
        score = score_calculator.calculate(
            structural=None,
            probability=None,
            golden=None,
            bookmaker_code="betfair",
            competition="epl",
        )

        assert score.is_exchange is True

    def test_skip_status_when_no_eligible_reference_window(self, score_calculator):
        """Non-reference bookmakers are SKIP when reference has no eligible fixtures."""
        score = score_calculator.calculate(
            structural=None,
            probability=None,
            golden=None,
            bookmaker_code="mintbet",
            competition="epl",
            eligible_reference_events=0,
        )

        assert score.status == "SKIP"
        assert score.no_eligible_reference_window is True

    def test_na_status_for_reference_when_no_eligible_reference_window(self, score_calculator):
        """Reference bookmaker is N_A when no eligible reference fixtures exist."""
        score = score_calculator.calculate(
            structural=None,
            probability=None,
            golden=None,
            bookmaker_code="ladbrokes",
            competition="epl",
            eligible_reference_events=0,
        )

        assert score.status == "N_A"
        assert score.no_eligible_reference_window is True

    def test_out_of_scope_zero_event_is_skip(self, score_calculator):
        """Out-of-scope bookmaker with zero events is SKIP (not FAIL)."""
        structural = StructuralValidation(
            bookmaker_code="betblitz",
            competition="nbl",
            event_count=0,
            expected_min=0,
            expected_max=20,
            event_count_valid=True,
            matching_rate=Decimal("0.00"),
        )
        probability = ProbabilityValidation(
            bookmaker_code="betblitz",
            competition="nbl",
            odds_compared=0,
            odds_matched=0,
            odds_warn=0,
            odds_critical=0,
        )

        score = score_calculator.calculate(
            structural=structural,
            probability=probability,
            golden=None,
            bookmaker_code="betblitz",
            competition="nbl",
            eligible_reference_events=10,
        )

        assert score.status == "SKIP"
        assert "Out-of-scope competition coverage policy" in score.warning_reasons[0]

    def test_out_of_scope_non_zero_event_is_skip(self, score_calculator):
        """Out-of-scope bookmaker remains SKIP even when it returns some events."""
        structural = StructuralValidation(
            bookmaker_code="betblitz",
            competition="boxing",
            event_count=3,
            expected_min=0,
            expected_max=20,
            event_count_valid=True,
            matching_rate=Decimal("0.00"),
        )
        probability = ProbabilityValidation(
            bookmaker_code="betblitz",
            competition="boxing",
            odds_compared=0,
            odds_matched=0,
            odds_warn=0,
            odds_critical=0,
        )

        score = score_calculator.calculate(
            structural=structural,
            probability=probability,
            golden=None,
            bookmaker_code="betblitz",
            competition="boxing",
            eligible_reference_events=20,
        )

        assert score.status == "SKIP"
        assert "Out-of-scope competition coverage policy" in score.warning_reasons[0]

    def test_in_scope_zero_event_remains_fail(self, score_calculator):
        """In-scope bookmaker with zero events still FAILs."""
        structural = StructuralValidation(
            bookmaker_code="mintbet",
            competition="nbl",
            event_count=0,
            expected_min=0,
            expected_max=20,
            event_count_valid=True,
            matching_rate=Decimal("0.00"),
        )
        probability = ProbabilityValidation(
            bookmaker_code="mintbet",
            competition="nbl",
            odds_compared=0,
            odds_matched=0,
            odds_warn=0,
            odds_critical=0,
        )

        score = score_calculator.calculate(
            structural=structural,
            probability=probability,
            golden=None,
            bookmaker_code="mintbet",
            competition="nbl",
            eligible_reference_events=10,
        )

        assert score.status == "FAIL"
        assert any("Coverage 0% < 70%" in reason for reason in score.failure_reasons)


# =============================================================================
# Report Generator Tests
# =============================================================================

class TestReportGenerator:
    """Tests for report generation."""

    def test_terminal_report_generation(self):
        """Test terminal report is generated."""
        generator = ReportGenerator(use_colors=False)

        report = ValidationReport(
            competition="epl",
            reference_bookmaker="ladbrokes",
            reference_events=10,
            pass_count=3,
            warn_count=1,
            fail_count=0,
            average_coverage=Decimal("95.0"),
        )

        output = generator.generate_terminal_report(report)

        assert "SCRAPER VALIDATION REPORT" in output
        assert "EPL" in output
        assert "SUMMARY" in output

    def test_json_report_generation(self):
        """Test JSON report is valid."""
        generator = ReportGenerator()

        report = ValidationReport(
            competition="epl",
            reference_bookmaker="ladbrokes",
            reference_events=10,
        )

        json_output = generator.generate_json_report(report)

        import json
        parsed = json.loads(json_output)

        assert parsed["competition"] == "epl"
        assert parsed["reference_bookmaker"] == "ladbrokes"

    def test_summary_line(self):
        """Test summary line generation."""
        generator = ReportGenerator()

        report = ValidationReport(
            competition="laliga",
            reference_bookmaker="ladbrokes",
            reference_events=10,
            pass_count=5,
            warn_count=2,
            fail_count=1,
            average_coverage=Decimal("85.5"),
            validation_duration_seconds=1.5,
        )

        summary = generator.generate_summary_line(report)

        assert "laliga" in summary
        assert "PASS=5" in summary
        assert "WARN=2" in summary
        assert "FAIL=1" in summary


# =============================================================================
# Config Tests
# =============================================================================

class TestValidationConfig:
    """Tests for validation configuration."""

    def test_expected_events_defaults(self, config):
        """Test expected events have sensible defaults."""
        epl = config.get_expected_events("epl")

        assert epl["min"] >= 1
        assert epl["max"] >= epl["min"]
        assert epl["typical"] >= epl["min"]
        assert epl["typical"] <= epl["max"]

    def test_probability_thresholds(self, config):
        """Test probability thresholds are valid."""
        thresholds = config.get_probability_thresholds("moneyline_favorite")

        assert thresholds["warn"] > 0
        assert thresholds["fail"] > thresholds["warn"]

    def test_exchange_detection(self, config):
        """Test exchange bookmaker detection."""
        assert config.is_exchange("betfair") is True
        assert config.is_exchange("ladbrokes") is False

    def test_golden_fixtures_present(self, config):
        """Test golden fixtures are configured for major leagues."""
        assert len(config.get_golden_fixtures("epl")) > 0
        assert len(config.get_golden_fixtures("laliga")) > 0

    def test_bookmaker_competition_scope_policy(self, config):
        """NBL out-of-scope list is applied explicitly."""
        assert config.get_bookmaker_competition_scope("ladbrokes", "boxing") == "in_scope"
        assert config.get_bookmaker_competition_scope("betblitz", "boxing") == "out_of_scope"
        assert config.get_bookmaker_competition_scope("betblitz", "nbl") == "out_of_scope"
        assert config.get_bookmaker_competition_scope("starsports", "nbl") == "out_of_scope"
        assert config.get_bookmaker_competition_scope("mintbet", "nbl") == "in_scope"


class TestNormalizationRegression:
    """Focused cross-platform normalization regression tests (Entain + Punterstech)."""

    @pytest.mark.parametrize(
        "raw_name,expected",
        [
            ("English Premier League", "epl"),
            ("National Basketball Association", "nba"),
            ("NBA Basketball", "nba"),
            ("National Hockey League", "nhl"),
            ("NHL Hockey", "nhl"),
            ("National Basketball League", "nbl"),
            ("Professional Boxing - Zayas vs. Baraou", "boxing"),
        ],
    )
    def test_priority_competition_aliases(self, raw_name, expected):
        assert normalize_competition_name(raw_name) == expected

    @pytest.mark.parametrize(
        "event_a,event_b,expected",
        [
            # EPL
            ("Manchester Utd v Tottenham Hotspur", "Tottenham vs Man United", "manutdvtottenham"),
            # NBA
            ("LA Lakers @ New York Knicks", "Los Angeles Lakers vs NY Knicks", "knicksvlalakers"),
            # NHL
            ("NY Rangers @ Toronto Maple Leafs", "New York Rangers vs Toronto Maple Leafs", "mapleleafsvnyrangers"),
            # Boxing
            ("Xander Zayas v Jorge Garcia Perez", "Xander Zayas Jr vs Jorge Garcia-Perez", "jorgegarciaperezvxanderzayas"),
            ("Naoya Inoue v Junto Nakatani", "N. Inoue vs J. Nakatani", "inouevnakatani"),
            # NBL
            ("SE Melbourne Phoenix v Illawarra Hawks", "South East Melbourne Phoenix vs Illawarra Hawks", "illawarrahawksvsemphoenix"),
        ],
    )
    def test_priority_event_aliases(self, event_a, event_b, expected):
        assert normalize_event_name(event_a) == expected
        assert normalize_event_name(event_b) == expected


class TestEntainMarketHygieneRegression:
    """Market hygiene regression checks for Entain matcher path."""

    @pytest.fixture
    def scraper(self):
        pytest.importorskip("playwright.async_api")
        from scrapers.entain_scraper import EntainScraper
        return EntainScraper("ladbrokes", "https://www.ladbrokes.com.au")

    def test_market_allow_deny_by_sport(self, scraper):
        assert scraper._is_matcher_market("Match Result", "soccer") is True
        assert scraper._is_matcher_market("1st Half Match Result", "soccer") is False
        assert scraper._is_matcher_market("Money Line", "basketball") is True
        assert scraper._is_matcher_market("2nd Quarter Money Line", "basketball") is False
        assert scraper._is_matcher_market("Fight Result", "boxing") is True
        assert scraper._is_matcher_market("Fight Winner By Decision", "boxing") is False

    def test_market_shape_soccer_requires_three_way(self, scraper):
        data = {
            "events": {
                "evt1": {
                    "name": "Arsenal v Chelsea",
                    "competition": {"name": "Premier League"},
                    "advertised_start": "2026-02-15T10:00:00Z",
                }
            },
            "markets": {
                "m1": {"name": "Match Result", "event_id": "evt1", "entrant_ids": ["e1", "e2"]},
            },
            "entrants": {
                "e1": {"name": "Arsenal"},
                "e2": {"name": "Chelsea"},
            },
            "prices": {
                "e1:m1": {"odds": {"numerator": 11, "denominator": 10}},
                "e2:m1": {"odds": {"numerator": 23, "denominator": 10}},
            },
        }

        events = scraper._parse_entain_response(data, "soccer")
        assert events == []

    def test_market_shape_two_way_for_basketball(self, scraper):
        data = {
            "events": {
                "evt2": {
                    "name": "Los Angeles Lakers v Boston Celtics",
                    "competition": {"name": "NBA"},
                    "advertised_start": "2026-02-15T10:00:00Z",
                }
            },
            "markets": {
                "m_good": {"name": "Money Line", "event_id": "evt2", "entrant_ids": ["e1", "e2"]},
                "m_partial": {"name": "1st Half Money Line", "event_id": "evt2", "entrant_ids": ["e1", "e2"]},
                "m_future": {"name": "NBA Championship Winner", "event_id": "evt2", "entrant_ids": ["e1", "e2"]},
            },
            "entrants": {
                "e1": {"name": "Los Angeles Lakers"},
                "e2": {"name": "Boston Celtics"},
            },
            "prices": {
                "e1:m_good": {"odds": {"numerator": 5, "denominator": 4}},
                "e2:m_good": {"odds": {"numerator": 4, "denominator": 5}},
                "e1:m_partial": {"odds": {"numerator": 5, "denominator": 4}},
                "e2:m_partial": {"odds": {"numerator": 4, "denominator": 5}},
                "e1:m_future": {"odds": {"numerator": 5, "denominator": 4}},
                "e2:m_future": {"odds": {"numerator": 4, "denominator": 5}},
            },
        }

        events = scraper._parse_entain_response(data, "basketball")
        assert len(events) == 1
        assert {odds.market_name for odds in events[0].odds} == {"Money Line"}
        assert {odds.selection_key for odds in events[0].odds} == {"home", "away"}

    @pytest.mark.parametrize(
        "selection_name,event_name,expected_key",
        [
            ("Tottenham", "Tottenham Hotspur v Manchester Utd", "home"),
            ("Man United", "Tottenham Hotspur v Manchester Utd", "away"),
            ("The Draw", "Arsenal v Chelsea", "draw"),
        ],
    )
    def test_selection_key_stability(self, scraper, selection_name, event_name, expected_key):
        home_team, away_team = scraper._extract_teams_from_name(event_name)
        event = ScrapedEvent(
            external_id="evt",
            name=event_name,
            sport="soccer",
            competition="test",
            start_time=datetime.now(timezone.utc) + timedelta(hours=24),
            home_team=home_team,
            away_team=away_team,
            odds=[],
        )
        assert scraper._get_selection_key(selection_name, event) == expected_key


# =============================================================================
# Integration Tests
# =============================================================================

class TestValidationIntegration:
    """Integration tests for the full validation pipeline."""

    def test_full_structural_to_score_flow(
        self,
        structural_validator,
        probability_validator,
        golden_validator,
        score_calculator,
        sample_events
    ):
        """Test full flow from structural validation to score."""
        # Phase 1
        structural = structural_validator.validate(
            events=sample_events,
            bookmaker_code="testbook",
            competition="epl",
            scraped_at=datetime.now(timezone.utc),
        )

        assert structural.passed is True

        # Phase 2 (mock - would need reference data)
        probability = ProbabilityValidation(
            bookmaker_code="testbook",
            competition="epl",
        )

        # Phase 3 (mock - golden fixtures)
        golden = GoldenFixturesValidation(
            bookmaker_code="testbook",
            competition="epl",
            fixtures_expected=0,
        )

        # Phase 4
        score = score_calculator.calculate(
            structural=structural,
            probability=probability,
            golden=golden,
            bookmaker_code="testbook",
            competition="epl",
        )

        assert score.status in ["PASS", "WARN", "FAIL", "SKIP", "N_A"]
        assert score.event_count == 3

    def test_pipeline_partial_eligibility_window_uses_only_eligible_reference_events(self):
        """Coverage denominator should use eligible reference fixtures only."""
        config = ValidationConfig(
            expected_events={"epl": {"min": 0, "max": 20, "typical": 10}}
        )
        pipeline = ValidationPipeline(config)

        scrape_results = {
            "ladbrokes": build_scrape_result(
                "ladbrokes",
                "epl",
                [
                    {
                        "name": "Arsenal v Chelsea",
                        "selections": [
                            {"selection_key": "home", "selection_name": "Arsenal", "decimal_odds": "2.10"},
                            {"selection_key": "draw", "selection_name": "Draw", "decimal_odds": "3.50"},
                            {"selection_key": "away", "selection_name": "Chelsea", "decimal_odds": "3.20"},
                        ],
                    },
                    {
                        "name": "Liverpool v Everton",
                        "selections": [
                            {"selection_key": "home", "selection_name": "Liverpool", "decimal_odds": "1.90"},
                            {"selection_key": "away", "selection_name": "Everton", "decimal_odds": "4.10"},
                        ],
                    },
                ],
            ),
            "mintbet": build_scrape_result(
                "mintbet",
                "epl",
                [
                    {
                        "name": "Arsenal v Chelsea",
                        "selections": [
                            {"selection_key": "home", "selection_name": "Arsenal", "decimal_odds": "2.15"},
                            {"selection_key": "draw", "selection_name": "Draw", "decimal_odds": "3.45"},
                            {"selection_key": "away", "selection_name": "Chelsea", "decimal_odds": "3.25"},
                        ],
                    },
                ],
            ),
        }

        result = pipeline.validate_scrape_results(scrape_results=scrape_results, competition="epl")

        mintbet_score = result.bookmaker_results["mintbet"]
        assert mintbet_score.event_coverage_percent == Decimal("100.00")
        assert result.report.reference_events == 1
        assert result.report.reference_total_events == 2

    def test_pipeline_empty_eligibility_window_marks_skip_and_na(self):
        """When no reference fixtures are eligible, score semantics are N_A/SKIP."""
        config = ValidationConfig(
            expected_events={"epl": {"min": 0, "max": 20, "typical": 10}}
        )
        pipeline = ValidationPipeline(config)

        scrape_results = {
            "ladbrokes": build_scrape_result(
                "ladbrokes",
                "epl",
                [
                    {
                        "name": "Arsenal v Chelsea",
                        "selections": [
                            {"selection_key": "home", "selection_name": "Arsenal", "decimal_odds": "2.10"},
                            {"selection_key": "away", "selection_name": "Chelsea", "decimal_odds": "3.20"},
                        ],
                    },
                ],
            ),
            "mintbet": build_scrape_result(
                "mintbet",
                "epl",
                [
                    {
                        "name": "Arsenal v Chelsea",
                        "selections": [
                            {"selection_key": "home", "selection_name": "Arsenal", "decimal_odds": "2.15"},
                            {"selection_key": "draw", "selection_name": "Draw", "decimal_odds": "3.45"},
                            {"selection_key": "away", "selection_name": "Chelsea", "decimal_odds": "3.25"},
                        ],
                    },
                ],
            ),
        }

        result = pipeline.validate_scrape_results(scrape_results=scrape_results, competition="epl")

        assert result.bookmaker_results["ladbrokes"].status == "N_A"
        assert result.bookmaker_results["mintbet"].status == "SKIP"
        assert result.report.skip_count == 1
        assert result.report.na_count == 1

    def test_pipeline_out_of_scope_zero_event_is_skip_and_not_failure(self):
        """Out-of-scope zero-event books should SKIP and not trigger fail alerts."""
        config = ValidationConfig(
            expected_events={"nbl": {"min": 0, "max": 20, "typical": 8}}
        )
        pipeline = ValidationPipeline(config)

        scrape_results = {
            "ladbrokes": build_scrape_result(
                "ladbrokes",
                "nbl",
                [
                    {
                        "name": "Sydney Kings v Tasmania JackJumpers",
                        "sport": "basketball",
                        "selections": [
                            {"selection_key": "home", "selection_name": "Sydney Kings", "decimal_odds": "1.80"},
                            {"selection_key": "away", "selection_name": "Tasmania JackJumpers", "decimal_odds": "2.05"},
                        ],
                    },
                ],
            ),
            "betblitz": build_scrape_result("betblitz", "nbl", []),
        }

        result = pipeline.validate_scrape_results(scrape_results=scrape_results, competition="nbl")

        assert result.bookmaker_results["betblitz"].status == "SKIP"
        assert result.report.fail_count == 0
        assert result.report.skip_count == 1
        assert result.has_failures is False

    def test_pipeline_out_of_scope_non_zero_boxing_is_skip(self):
        """Out-of-scope boxing books should SKIP even with non-zero events."""
        config = ValidationConfig(
            expected_events={"boxing": {"min": 0, "max": 20, "typical": 5}}
        )
        pipeline = ValidationPipeline(config)

        scrape_results = {
            "ladbrokes": build_scrape_result(
                "ladbrokes",
                "boxing",
                [
                    {
                        "name": "Ryan Garcia v Mario Barrios",
                        "sport": "boxing",
                        "selections": [
                            {"selection_key": "home", "selection_name": "Ryan Garcia", "decimal_odds": "1.80"},
                            {"selection_key": "away", "selection_name": "Mario Barrios", "decimal_odds": "2.05"},
                        ],
                    },
                ],
            ),
            "betblitz": build_scrape_result(
                "betblitz",
                "boxing",
                [
                    {
                        "name": "Regional Fighter A v Regional Fighter B",
                        "sport": "boxing",
                        "selections": [
                            {"selection_key": "home", "selection_name": "Regional Fighter A", "decimal_odds": "1.90"},
                            {"selection_key": "away", "selection_name": "Regional Fighter B", "decimal_odds": "1.95"},
                        ],
                    },
                ],
            ),
        }

        result = pipeline.validate_scrape_results(scrape_results=scrape_results, competition="boxing")

        assert result.bookmaker_results["betblitz"].status == "SKIP"
        assert result.report.fail_count == 0
        assert result.report.skip_count == 1
        assert result.has_failures is False

    def test_pipeline_in_scope_zero_event_is_failure(self):
        """In-scope zero-event books remain FAIL and set failure signal for alerts."""
        config = ValidationConfig(
            expected_events={"nbl": {"min": 0, "max": 20, "typical": 8}}
        )
        pipeline = ValidationPipeline(config)

        scrape_results = {
            "ladbrokes": build_scrape_result(
                "ladbrokes",
                "nbl",
                [
                    {
                        "name": "Sydney Kings v Tasmania JackJumpers",
                        "sport": "basketball",
                        "selections": [
                            {"selection_key": "home", "selection_name": "Sydney Kings", "decimal_odds": "1.80"},
                            {"selection_key": "away", "selection_name": "Tasmania JackJumpers", "decimal_odds": "2.05"},
                        ],
                    },
                ],
            ),
            "mintbet": build_scrape_result("mintbet", "nbl", []),
        }

        result = pipeline.validate_scrape_results(scrape_results=scrape_results, competition="nbl")

        assert result.bookmaker_results["mintbet"].status == "FAIL"
        assert result.report.fail_count == 1
        assert result.has_failures is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
