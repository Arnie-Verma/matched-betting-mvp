"""
Scraper Validation Framework

4-Phase validation pipeline for ensuring scraper quality at scale:
- Phase 1: Structural & Coverage Validation
- Phase 2: Odds Sanity via Implied Probability
- Phase 3: Golden Fixtures (Regression Safety)
- Phase 4: Scoring & Anomaly Output

Usage:
    from validation import ValidationPipeline

    pipeline = ValidationPipeline()
    result = await pipeline.validate_scrape_results(results, "laliga")
    print(result.summary())
"""

from validation.config import (
    EXPECTED_EVENTS,
    PROBABILITY_THRESHOLDS,
    GOLDEN_FIXTURES,
    ValidationConfig,
)
from validation.structural_validator import StructuralValidator, StructuralValidation
from validation.probability_validator import ProbabilityValidator, OddsAnomaly
from validation.golden_fixtures import GoldenFixturesValidator, GoldenFixtureResult
from validation.score_calculator import ScoreCalculator, ValidationScore
from validation.report_generator import ReportGenerator, ValidationReport
from validation.pipeline import ValidationPipeline

__all__ = [
    # Config
    "EXPECTED_EVENTS",
    "PROBABILITY_THRESHOLDS",
    "GOLDEN_FIXTURES",
    "ValidationConfig",
    # Validators
    "StructuralValidator",
    "StructuralValidation",
    "ProbabilityValidator",
    "OddsAnomaly",
    "GoldenFixturesValidator",
    "GoldenFixtureResult",
    "ScoreCalculator",
    "ValidationScore",
    # Report
    "ReportGenerator",
    "ValidationReport",
    # Pipeline
    "ValidationPipeline",
]
