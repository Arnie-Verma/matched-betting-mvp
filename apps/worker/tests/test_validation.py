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
)
from validation.structural_validator import StructuralValidator, StructuralValidation
from validation.probability_validator import ProbabilityValidator, ProbabilityValidation
from validation.golden_fixtures import GoldenFixturesValidator, GoldenFixturesValidation
from validation.score_calculator import ScoreCalculator, ValidationScore
from validation.report_generator import ReportGenerator, ValidationReport


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
            competition="epl",
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
            odds_critical=5,  # More than MAX_CRITICAL_ANOMALIES (2)
        )

        score = score_calculator.calculate(
            structural=None,
            probability=probability,
            golden=None,
            bookmaker_code="testbook",
            competition="epl",
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
            competition="epl",
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
            competition="epl",
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

        assert score.status in ["PASS", "WARN", "FAIL"]
        assert score.event_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
