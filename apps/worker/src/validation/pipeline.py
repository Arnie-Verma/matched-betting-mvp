"""
Validation Pipeline

Orchestrates all 4 phases of validation into a single pipeline.
Designed for integration with scrape service.
"""
import sys
sys.path.insert(0, "apps/api/src")

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Optional, Any

from validation.config import ValidationConfig
from validation.structural_validator import StructuralValidator, StructuralValidation
from validation.probability_validator import ProbabilityValidator, ProbabilityValidation
from validation.golden_fixtures import GoldenFixturesValidator, GoldenFixturesValidation
from validation.score_calculator import ScoreCalculator, ValidationScore
from validation.report_generator import ReportGenerator, ValidationReport

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of running the validation pipeline."""
    competition: str
    bookmaker_results: Dict[str, ValidationScore] = field(default_factory=dict)
    has_failures: bool = False
    has_warnings: bool = False
    report: Optional[ValidationReport] = None
    duration_seconds: float = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "competition": self.competition,
            "bookmaker_results": {k: v.to_dict() for k, v in self.bookmaker_results.items()},
            "has_failures": self.has_failures,
            "has_warnings": self.has_warnings,
            "duration_seconds": self.duration_seconds,
        }

    @property
    def failed_bookmakers(self) -> List[str]:
        """Get list of failed bookmakers."""
        return [k for k, v in self.bookmaker_results.items() if v.status == "FAIL"]

    @property
    def warned_bookmakers(self) -> List[str]:
        """Get list of warned bookmakers."""
        return [k for k, v in self.bookmaker_results.items() if v.status == "WARN"]


class ValidationPipeline:
    """
    Orchestrates the 4-phase validation pipeline.

    Phases:
    1. Structural validation (event counts, odds bounds, freshness)
    2. Probability validation (implied probability comparison)
    3. Golden fixtures validation (curated fixture checks)
    4. Score calculation (final PASS/WARN/FAIL)

    Usage:
        pipeline = ValidationPipeline()

        # From scrape results
        result = pipeline.validate_scrape_results(
            scrape_results={"ladbrokes": result1, "mintbet": result2},
            competition="laliga"
        )

        # Print report
        pipeline.print_report(result)
    """

    def __init__(self, config: Optional[ValidationConfig] = None):
        """
        Initialize validation pipeline.

        Args:
            config: Validation configuration (uses defaults if None)
        """
        self.config = config or ValidationConfig()
        self.structural_validator = StructuralValidator(config)
        self.probability_validator = ProbabilityValidator(config)
        self.golden_validator = GoldenFixturesValidator(config)
        self.score_calculator = ScoreCalculator(config)
        self.report_generator = ReportGenerator()

    def validate_scrape_results(
        self,
        scrape_results: Dict[str, Any],  # Dict of bookmaker_code -> ScrapeResult
        competition: str,
    ) -> PipelineResult:
        """
        Run full validation pipeline on scrape results.

        Args:
            scrape_results: Dict of {bookmaker_code: ScrapeResult}
            competition: Competition being validated

        Returns:
            PipelineResult with all validation results
        """
        start_time = time.time()
        logger.info(f"Starting validation pipeline for {competition}")

        # Import here to avoid circular dependency
        from api.services.normalization_service import normalize_event_name

        # Phase 1: Structural validation
        structural_results: Dict[str, StructuralValidation] = {}
        for bookmaker_code, scrape_result in scrape_results.items():
            try:
                structural_results[bookmaker_code] = \
                    self.structural_validator.validate_from_scrape_result(
                        scrape_result, competition
                    )
            except Exception as e:
                logger.error(f"[{bookmaker_code}] Structural validation failed: {e}")

        # Prepare odds data for probability validation
        all_odds_data = self._prepare_odds_data(scrape_results)

        # Get reference odds
        reference_bookmaker = self.config.reference_bookmaker
        reference_odds = all_odds_data.get(reference_bookmaker, {})
        reference_events = len(reference_odds)

        # Phase 2: Probability validation
        probability_results: Dict[str, ProbabilityValidation] = {}
        for bookmaker_code in scrape_results.keys():
            if bookmaker_code == reference_bookmaker:
                continue  # Skip reference bookmaker

            try:
                bookmaker_odds = all_odds_data.get(bookmaker_code, {})

                if self.config.use_consensus:
                    probability_results[bookmaker_code] = \
                        self.probability_validator.validate_with_consensus(
                            all_odds_data, bookmaker_code, competition
                        )
                else:
                    probability_results[bookmaker_code] = \
                        self.probability_validator.validate(
                            bookmaker_odds, reference_odds,
                            bookmaker_code, competition
                        )
            except Exception as e:
                logger.error(f"[{bookmaker_code}] Probability validation failed: {e}")

        # Phase 3: Golden fixtures validation
        golden_results: Dict[str, GoldenFixturesValidation] = {}
        for bookmaker_code, scrape_result in scrape_results.items():
            try:
                golden_results[bookmaker_code] = \
                    self.golden_validator.validate_from_scrape_result(
                        scrape_result, competition
                    )
            except Exception as e:
                logger.error(f"[{bookmaker_code}] Golden fixtures validation failed: {e}")

        # Get scrape durations
        scrape_durations = {
            bookmaker_code: getattr(result, 'duration_seconds', 0)
            for bookmaker_code, result in scrape_results.items()
        }

        # Phase 4: Score calculation
        scores = self.score_calculator.calculate_batch(
            structural_results=structural_results,
            probability_results=probability_results,
            golden_results=golden_results,
            competition=competition,
            scrape_durations=scrape_durations,
        )

        # Generate golden fixtures summary
        golden_summary = self.golden_validator.get_golden_fixture_summary(
            golden_results, competition
        )

        duration = time.time() - start_time

        # Create report
        report = self.report_generator.create_report(
            scores=scores,
            competition=competition,
            reference_bookmaker=reference_bookmaker,
            reference_events=reference_events,
            golden_fixtures_summary=golden_summary,
            validation_duration_seconds=duration,
        )

        # Build result
        result = PipelineResult(
            competition=competition,
            bookmaker_results=scores,
            has_failures=any(s.status == "FAIL" for s in scores.values()),
            has_warnings=any(s.status == "WARN" for s in scores.values()),
            report=report,
            duration_seconds=duration,
        )

        logger.info(
            f"Validation pipeline completed: "
            f"PASS={report.pass_count} WARN={report.warn_count} FAIL={report.fail_count} "
            f"({duration:.2f}s)"
        )

        return result

    def _prepare_odds_data(
        self,
        scrape_results: Dict[str, Any]
    ) -> Dict[str, Dict[str, Dict[str, Dict]]]:
        """
        Prepare odds data for probability validation.

        Converts ScrapeResult format to:
        {bookmaker: {event_key: {selection_key: odds_dict}}}

        Args:
            scrape_results: Dict of {bookmaker_code: ScrapeResult}

        Returns:
            Nested dict of odds data
        """
        from api.services.normalization_service import normalize_event_name

        all_odds: Dict[str, Dict[str, Dict[str, Dict]]] = {}

        for bookmaker_code, scrape_result in scrape_results.items():
            bookmaker_odds: Dict[str, Dict[str, Dict]] = {}

            for event in scrape_result.events:
                event_key = normalize_event_name(event.name)

                if event_key not in bookmaker_odds:
                    bookmaker_odds[event_key] = {}

                for odds in event.odds:
                    selection_key = odds.selection_key.lower()
                    bookmaker_odds[event_key][selection_key] = {
                        "decimal_odds": odds.decimal_odds,
                        "selection_name": odds.selection_name,
                        "market_type": odds.market_type,
                        "event_name": event.name,
                    }

            all_odds[bookmaker_code] = bookmaker_odds

        return all_odds

    def validate_from_database(
        self,
        competition: str,
        bookmaker_codes: Optional[List[str]] = None,
    ) -> PipelineResult:
        """
        Run validation on data already in database.

        Useful for validating historical data or re-validating after fixes.

        Args:
            competition: Competition to validate
            bookmaker_codes: Optional list of bookmakers to validate (None = all)

        Returns:
            PipelineResult with all validation results
        """
        from api.core.database import SessionLocal
        from api.models import Bookmaker, Event, Selection, OddsSnapshot, Competition as CompetitionModel

        start_time = time.time()
        logger.info(f"Starting database validation for {competition}")

        db = SessionLocal()
        try:
            # Get competition from database
            comp = db.query(CompetitionModel).filter(
                CompetitionModel.code == competition
            ).first()

            if not comp:
                logger.error(f"Competition not found: {competition}")
                return PipelineResult(competition=competition)

            # Get active bookmakers
            if bookmaker_codes:
                bookmakers = db.query(Bookmaker).filter(
                    Bookmaker.code.in_(bookmaker_codes)
                ).all()
            else:
                bookmakers = db.query(Bookmaker).filter(
                    Bookmaker.is_active == True
                ).all()

            # Build odds data from database
            all_odds: Dict[str, Dict[str, Dict[str, Dict]]] = {}

            for bookmaker in bookmakers:
                # Query current odds for this bookmaker and competition
                odds_query = db.query(
                    OddsSnapshot, Selection, Event
                ).join(
                    Selection, OddsSnapshot.selection_id == Selection.id
                ).join(
                    Event, Selection.event_id == Event.id
                ).filter(
                    Event.competition_id == comp.id,
                    OddsSnapshot.bookmaker_id == bookmaker.id,
                    OddsSnapshot.is_current == True,
                )

                bookmaker_odds: Dict[str, Dict[str, Dict]] = {}

                for odds, selection, event in odds_query.all():
                    from api.services.normalization_service import normalize_event_name
                    event_key = normalize_event_name(event.name)

                    if event_key not in bookmaker_odds:
                        bookmaker_odds[event_key] = {}

                    selection_key = selection.selection_key.lower() if selection.selection_key else selection.name.lower()
                    bookmaker_odds[event_key][selection_key] = {
                        "decimal_odds": odds.odds,
                        "selection_name": selection.name,
                        "market_type": "match_winner",  # Default
                        "event_name": event.name,
                    }

                all_odds[bookmaker.code] = bookmaker_odds

            # Now run probability validation
            reference_bookmaker = self.config.reference_bookmaker
            reference_odds = all_odds.get(reference_bookmaker, {})

            probability_results: Dict[str, ProbabilityValidation] = {}
            for bookmaker_code, bookmaker_odds in all_odds.items():
                if bookmaker_code == reference_bookmaker:
                    continue

                probability_results[bookmaker_code] = self.probability_validator.validate(
                    bookmaker_odds, reference_odds,
                    bookmaker_code, competition
                )

            # Calculate scores
            scores = self.score_calculator.calculate_batch(
                structural_results={},  # No structural validation for DB data
                probability_results=probability_results,
                golden_results={},  # No golden fixtures for DB data
                competition=competition,
            )

            duration = time.time() - start_time

            # Create report
            report = self.report_generator.create_report(
                scores=scores,
                competition=competition,
                reference_bookmaker=reference_bookmaker,
                reference_events=len(reference_odds),
                validation_duration_seconds=duration,
            )

            return PipelineResult(
                competition=competition,
                bookmaker_results=scores,
                has_failures=any(s.status == "FAIL" for s in scores.values()),
                has_warnings=any(s.status == "WARN" for s in scores.values()),
                report=report,
                duration_seconds=duration,
            )

        finally:
            db.close()

    def print_report(
        self,
        result: PipelineResult,
        output_format: str = "terminal",
        show_anomalies: bool = True,
    ):
        """
        Print validation report.

        Args:
            result: PipelineResult from validation
            output_format: "terminal" or "json"
            show_anomalies: Whether to show individual anomalies
        """
        if result.report:
            self.report_generator.print_report(
                result.report,
                output_format=output_format,
                show_anomalies=show_anomalies,
            )
        else:
            logger.warning("No report available")
