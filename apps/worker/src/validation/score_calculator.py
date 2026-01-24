"""
Phase 4: Scoring & Anomaly Output

Combines all validation phases into final score:
- Per bookmaker x league: PASS / WARN / FAIL
- Coverage %, anomaly count, top N outliers
- Human review = "check top anomalies" only
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Optional, Literal

from validation.config import (
    ValidationConfig,
    COVERAGE_WARN_THRESHOLD,
    COVERAGE_FAIL_THRESHOLD,
    EVENT_COVERAGE_WARN_THRESHOLD,
    EVENT_COVERAGE_FAIL_THRESHOLD,
    MAX_ANOMALIES_WARN,
    MAX_CRITICAL_ANOMALIES,
)
from validation.structural_validator import StructuralValidation
from validation.probability_validator import ProbabilityValidation, OddsAnomaly
from validation.golden_fixtures import GoldenFixturesValidation

logger = logging.getLogger(__name__)


@dataclass
class ValidationScore:
    """
    Final validation score for bookmaker x league.

    Combines all phase results into a single PASS/WARN/FAIL status.
    """
    bookmaker_code: str
    competition: str
    status: Literal["PASS", "WARN", "FAIL"]

    # Is this bookmaker an exchange? (structure-only validation)
    is_exchange: bool = False

    # Phase 1 metrics
    event_count: int = 0
    structural_passed: bool = True
    structural_issues: List[str] = field(default_factory=list)
    event_coverage_percent: Optional[Decimal] = None

    # Phase 2 metrics
    coverage_percent: Decimal = Decimal("100")
    match_rate: Decimal = Decimal("100")
    anomaly_count: int = 0
    critical_anomaly_count: int = 0
    worst_anomalies: List[OddsAnomaly] = field(default_factory=list)

    # Phase 3 metrics
    golden_fixtures_found: int = 0
    golden_fixtures_total: int = 0
    golden_fixtures_passed: int = 0

    # Metadata
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scrape_duration_seconds: Optional[float] = None

    # Failure reasons (human-readable)
    failure_reasons: List[str] = field(default_factory=list)
    warning_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "bookmaker_code": self.bookmaker_code,
            "competition": self.competition,
            "status": self.status,
            "is_exchange": self.is_exchange,
            "event_count": self.event_count,
            "structural_passed": self.structural_passed,
            "structural_issues": self.structural_issues,
            "event_coverage_percent": (
                str(self.event_coverage_percent)
                if self.event_coverage_percent is not None else None
            ),
            "coverage_percent": str(self.coverage_percent),
            "match_rate": str(self.match_rate),
            "anomaly_count": self.anomaly_count,
            "critical_anomaly_count": self.critical_anomaly_count,
            "worst_anomalies": [a.to_dict() for a in self.worst_anomalies],
            "golden_fixtures_found": self.golden_fixtures_found,
            "golden_fixtures_total": self.golden_fixtures_total,
            "golden_fixtures_passed": self.golden_fixtures_passed,
            "failure_reasons": self.failure_reasons,
            "warning_reasons": self.warning_reasons,
            "validated_at": self.validated_at.isoformat(),
            "scrape_duration_seconds": self.scrape_duration_seconds,
        }


class ScoreCalculator:
    """
    Calculates final validation score from all phase results.

    Scoring logic:
    - FAIL: Critical issues that indicate broken scraper
    - WARN: Minor issues that should be investigated
    - PASS: All validations passed within thresholds
    """

    def __init__(self, config: Optional[ValidationConfig] = None):
        """
        Initialize score calculator.

        Args:
            config: Validation configuration (uses defaults if None)
        """
        self.config = config or ValidationConfig()

    def calculate(
        self,
        structural: Optional[StructuralValidation],
        probability: Optional[ProbabilityValidation],
        golden: Optional[GoldenFixturesValidation],
        bookmaker_code: str,
        competition: str,
        scrape_duration_seconds: Optional[float] = None,
    ) -> ValidationScore:
        """
        Calculate final validation score from all phase results.

        Args:
            structural: Phase 1 structural validation result
            probability: Phase 2 probability validation result
            golden: Phase 3 golden fixtures validation result
            bookmaker_code: Bookmaker being scored
            competition: Competition being scored
            scrape_duration_seconds: Time taken to scrape (for metrics)

        Returns:
            ValidationScore with final status
        """
        is_exchange = self.config.is_exchange(bookmaker_code)

        # Initialize score
        score = ValidationScore(
            bookmaker_code=bookmaker_code,
            competition=competition,
            status="PASS",  # Will be updated based on checks
            is_exchange=is_exchange,
            scrape_duration_seconds=scrape_duration_seconds,
        )

        # Apply Phase 1 results
        if structural:
            self._apply_structural(score, structural)

        # Apply Phase 2 results (skip for exchanges)
        if probability and not is_exchange:
            self._apply_probability(score, probability)

        # Apply Phase 3 results
        if golden:
            self._apply_golden(score, golden)

        # Determine final status
        status = self._determine_status(score)
        score.status = status

        # Log result
        log_level = {
            "PASS": logging.INFO,
            "WARN": logging.WARNING,
            "FAIL": logging.ERROR,
        }.get(status, logging.INFO)

        logger.log(
            log_level,
            f"[{bookmaker_code}] Final score: {status} | "
            f"events={score.event_count} | "
            f"coverage={score.coverage_percent}% | "
            f"anomalies={score.anomaly_count}"
        )

        return score

    def _apply_structural(
        self,
        score: ValidationScore,
        structural: StructuralValidation
    ):
        """Apply Phase 1 structural validation results to score."""
        score.event_count = structural.event_count
        score.structural_passed = structural.passed
        score.event_coverage_percent = structural.matching_rate

        if not structural.event_count_valid:
            score.structural_issues.append(
                f"Event count {structural.event_count} outside "
                f"expected range [{structural.expected_min}-{structural.expected_max}]"
            )

        if structural.odds_out_of_bounds:
            score.structural_issues.append(
                f"{len(structural.odds_out_of_bounds)} odds outside valid bounds"
            )

        if not structural.is_fresh:
            score.structural_issues.append("Data is stale (>15 min old)")

    def _apply_probability(
        self,
        score: ValidationScore,
        probability: ProbabilityValidation
    ):
        """Apply Phase 2 probability validation results to score."""
        score.coverage_percent = probability.coverage_percent
        score.match_rate = probability.match_rate
        score.anomaly_count = len(probability.anomalies)
        score.critical_anomaly_count = probability.odds_critical
        score.worst_anomalies = probability.worst_anomalies

    def _apply_golden(
        self,
        score: ValidationScore,
        golden: GoldenFixturesValidation
    ):
        """Apply Phase 3 golden fixtures validation results to score."""
        score.golden_fixtures_total = golden.fixtures_expected
        score.golden_fixtures_found = golden.fixtures_found
        score.golden_fixtures_passed = golden.fixtures_passed

    def _determine_status(self, score: ValidationScore) -> Literal["PASS", "WARN", "FAIL"]:
        """
        Determine final status based on all metrics.

        FAIL conditions (critical):
        - Structural validation failed
        - Coverage below 70%
        - More than 2 critical anomalies
        - More than half of golden fixtures failed

        WARN conditions (investigate):
        - Coverage below 85%
        - More than 5 total anomalies
        - Any golden fixtures missing

        PASS conditions:
        - All checks within thresholds
        """
        # ========== FAIL CONDITIONS ==========

        # Structural failure
        if not score.structural_passed:
            score.failure_reasons.append("Structural validation failed")
            if self.config.strict_mode:
                return "FAIL"

            # In non-strict mode, structural issues are warnings
            # unless there are no events at all
            if score.event_count == 0:
                return "FAIL"
            score.warning_reasons.extend(score.structural_issues)

        # Coverage too low (for non-exchanges)
        if not score.is_exchange:
            if score.coverage_percent < COVERAGE_FAIL_THRESHOLD:
                score.failure_reasons.append(
                    f"Coverage {score.coverage_percent}% < {COVERAGE_FAIL_THRESHOLD}%"
                )
                return "FAIL"

        if not score.is_exchange and score.event_coverage_percent is not None:
            if score.event_coverage_percent < EVENT_COVERAGE_FAIL_THRESHOLD:
                score.failure_reasons.append(
                    f"Event coverage {score.event_coverage_percent}% < {EVENT_COVERAGE_FAIL_THRESHOLD}%"
                )
                return "FAIL"

        # Too many critical anomalies
        if score.critical_anomaly_count > MAX_CRITICAL_ANOMALIES:
            score.failure_reasons.append(
                f"{score.critical_anomaly_count} critical anomalies "
                f"(max: {MAX_CRITICAL_ANOMALIES})"
            )
            return "FAIL"

        # Most golden fixtures failed
        if score.golden_fixtures_total > 0:
            min_required = score.golden_fixtures_total // 2 + 1
            if score.golden_fixtures_passed < min_required:
                score.failure_reasons.append(
                    f"Only {score.golden_fixtures_passed}/{score.golden_fixtures_total} "
                    f"golden fixtures passed (need {min_required})"
                )
                return "FAIL"

        # ========== WARN CONDITIONS ==========

        # Coverage below threshold (for non-exchanges)
        if not score.is_exchange:
            if score.coverage_percent < COVERAGE_WARN_THRESHOLD:
                score.warning_reasons.append(
                    f"Coverage {score.coverage_percent}% < {COVERAGE_WARN_THRESHOLD}%"
                )

        if not score.is_exchange and score.event_coverage_percent is not None:
            if score.event_coverage_percent < EVENT_COVERAGE_WARN_THRESHOLD:
                score.warning_reasons.append(
                    f"Event coverage {score.event_coverage_percent}% < {EVENT_COVERAGE_WARN_THRESHOLD}%"
                )

        # Too many anomalies
        if score.anomaly_count > MAX_ANOMALIES_WARN:
            score.warning_reasons.append(
                f"{score.anomaly_count} anomalies (warn threshold: {MAX_ANOMALIES_WARN})"
            )

        # Any missing golden fixtures
        if score.golden_fixtures_total > 0:
            missing = score.golden_fixtures_total - score.golden_fixtures_found
            if missing > 0:
                score.warning_reasons.append(
                    f"{missing} golden fixtures not found"
                )

        # ========== FINAL STATUS ==========

        if score.failure_reasons:
            return "FAIL"

        if score.warning_reasons:
            return "WARN"

        return "PASS"

    def calculate_batch(
        self,
        structural_results: Dict[str, StructuralValidation],
        probability_results: Dict[str, ProbabilityValidation],
        golden_results: Dict[str, GoldenFixturesValidation],
        competition: str,
        scrape_durations: Optional[Dict[str, float]] = None,
    ) -> Dict[str, ValidationScore]:
        """
        Calculate scores for multiple bookmakers.

        Args:
            structural_results: Dict of {bookmaker_code: StructuralValidation}
            probability_results: Dict of {bookmaker_code: ProbabilityValidation}
            golden_results: Dict of {bookmaker_code: GoldenFixturesValidation}
            competition: Competition being scored
            scrape_durations: Dict of {bookmaker_code: duration_seconds}

        Returns:
            Dict of {bookmaker_code: ValidationScore}
        """
        scores: Dict[str, ValidationScore] = {}
        durations = scrape_durations or {}

        # Get all bookmakers from any result set
        all_bookmakers = set()
        all_bookmakers.update(structural_results.keys())
        all_bookmakers.update(probability_results.keys())
        all_bookmakers.update(golden_results.keys())

        for bookmaker_code in all_bookmakers:
            scores[bookmaker_code] = self.calculate(
                structural=structural_results.get(bookmaker_code),
                probability=probability_results.get(bookmaker_code),
                golden=golden_results.get(bookmaker_code),
                bookmaker_code=bookmaker_code,
                competition=competition,
                scrape_duration_seconds=durations.get(bookmaker_code),
            )

        return scores

    def summarize(
        self,
        scores: Dict[str, ValidationScore]
    ) -> Dict[str, any]:
        """
        Generate summary statistics from batch scores.

        Args:
            scores: Dict of {bookmaker_code: ValidationScore}

        Returns:
            Summary dict with pass/warn/fail counts and average metrics
        """
        pass_count = 0
        warn_count = 0
        fail_count = 0

        total_coverage = Decimal("0")
        total_anomalies = 0

        failed_bookmakers = []
        warned_bookmakers = []

        for bookmaker_code, score in scores.items():
            if score.status == "PASS":
                pass_count += 1
            elif score.status == "WARN":
                warn_count += 1
                warned_bookmakers.append(bookmaker_code)
            else:
                fail_count += 1
                failed_bookmakers.append(bookmaker_code)

            total_coverage += score.coverage_percent
            total_anomalies += score.anomaly_count

        avg_coverage = total_coverage / len(scores) if scores else Decimal("0")

        return {
            "total_bookmakers": len(scores),
            "pass_count": pass_count,
            "warn_count": warn_count,
            "fail_count": fail_count,
            "average_coverage": str(avg_coverage.quantize(Decimal("0.1"))),
            "total_anomalies": total_anomalies,
            "failed_bookmakers": failed_bookmakers,
            "warned_bookmakers": warned_bookmakers,
        }
