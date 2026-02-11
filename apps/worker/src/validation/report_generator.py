"""
Report Generator

Generates human-readable validation reports for terminal and JSON output.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Optional, Literal

from validation.score_calculator import ValidationScore
from validation.probability_validator import OddsAnomaly
from validation.golden_fixtures import GoldenFixturesValidator

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    """Complete validation report for a competition."""
    competition: str
    reference_bookmaker: str
    reference_events: int
    reference_total_events: Optional[int] = None

    # Per-bookmaker scores
    scores: Dict[str, ValidationScore] = field(default_factory=dict)

    # Golden fixtures summary
    golden_fixtures_summary: Dict[str, Dict] = field(default_factory=dict)

    # Summary stats
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    skip_count: int = 0
    na_count: int = 0
    average_coverage: Decimal = Decimal("0")

    # Timing
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    validation_duration_seconds: float = 0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "competition": self.competition,
            "reference_bookmaker": self.reference_bookmaker,
            "reference_events": self.reference_events,
            "reference_total_events": self.reference_total_events,
            "scores": {k: v.to_dict() for k, v in self.scores.items()},
            "golden_fixtures_summary": self.golden_fixtures_summary,
            "summary": {
                "total_bookmakers": len(self.scores),
                "pass_count": self.pass_count,
                "warn_count": self.warn_count,
                "fail_count": self.fail_count,
                "skip_count": self.skip_count,
                "na_count": self.na_count,
                "average_coverage": str(self.average_coverage),
            },
            "generated_at": self.generated_at.isoformat(),
            "validation_duration_seconds": self.validation_duration_seconds,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


class ReportGenerator:
    """
    Generates validation reports in various formats.

    Supports:
    - Terminal (human-readable with colors)
    - JSON (machine-readable for CI/CD)
    """

    # Terminal colors (ANSI escape codes)
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "cyan": "\033[96m",
        "dim": "\033[2m",
    }

    # Status symbols
    STATUS_SYMBOLS = {
        "PASS": ("OK ", "green"),
        "WARN": ("!  ", "yellow"),
        "FAIL": ("X  ", "red"),
        "SKIP": ("SKP", "dim"),
        "N_A": ("N/A", "cyan"),
    }

    def __init__(self, use_colors: bool = True):
        """
        Initialize report generator.

        Args:
            use_colors: Whether to use ANSI colors in terminal output
        """
        self.use_colors = use_colors

    def _color(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if not self.use_colors:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['reset']}"

    def generate_terminal_report(
        self,
        report: ValidationReport,
        show_anomalies: bool = True,
        max_anomalies: int = 3,
    ) -> str:
        """
        Generate human-readable terminal report.

        Args:
            report: ValidationReport to format
            show_anomalies: Whether to show individual anomalies
            max_anomalies: Maximum anomalies to show per bookmaker

        Returns:
            Formatted string for terminal output
        """
        lines = []

        # Header
        lines.append(self._generate_header(report))

        # Reference info
        reference_note = ""
        if report.reference_total_events is not None and report.reference_total_events != report.reference_events:
            reference_note = f" ({report.reference_events} eligible / {report.reference_total_events} total)"

        lines.append(self._color(
            f"REFERENCE: {report.reference_bookmaker.upper()} - "
            f"{report.reference_events} events indexed{reference_note}",
            "cyan"
        ))
        lines.append("")

        # Competition header
        lines.append("=" * 75)
        lines.append(self._color(
            f"{report.competition.upper()} ({report.reference_events} events reference)",
            "bold"
        ))
        lines.append("=" * 75)
        lines.append("")

        # Sort scores: reference first, then exchanges, then by status
        sorted_scores = self._sort_scores(report.scores, report.reference_bookmaker)

        # Bookmaker results
        for bookmaker_code, score in sorted_scores:
            lines.append(self._format_bookmaker_line(score, report.reference_bookmaker))

            # Show anomalies if requested
            if show_anomalies and score.worst_anomalies:
                for anomaly in score.worst_anomalies[:max_anomalies]:
                    lines.append(self._format_anomaly_line(anomaly))

        lines.append("")

        # Golden fixtures summary
        if report.golden_fixtures_summary:
            lines.append("GOLDEN FIXTURES:")
            for fixture_key, fixture_data in report.golden_fixtures_summary.items():
                found_count = fixture_data["found_count"]
                total = fixture_data["total_bookmakers"]
                symbol = self._color("OK ", "green") if found_count > total * 0.8 else self._color("!  ", "yellow")
                lines.append(
                    f"  {symbol} {fixture_data['fixture_name']}: "
                    f"Found in {found_count}/{total} bookmakers"
                )
            lines.append("")

        # Summary
        lines.append("=" * 75)
        lines.append("SUMMARY")
        lines.append("=" * 75)
        lines.append(
            f"Bookmakers: "
            f"{self._color(f'{report.pass_count} PASS', 'green')} | "
            f"{self._color(f'{report.warn_count} WARN', 'yellow')} | "
            f"{self._color(f'{report.fail_count} FAIL', 'red')} | "
            f"{self._color(f'{report.skip_count} SKIP', 'dim')} | "
            f"{self._color(f'{report.na_count} N_A', 'cyan')}"
        )
        lines.append(f"Coverage: {report.average_coverage}% average across all bookmakers")

        # Action required
        if report.fail_count > 0:
            failed = [k for k, v in report.scores.items() if v.status == "FAIL"]
            lines.append(self._color(
                f"Action Required: Review {', '.join(failed)} anomalies (possible parsing bug)",
                "red"
            ))

        lines.append("=" * 75)

        return "\n".join(lines)

    def _generate_header(self, report: ValidationReport) -> str:
        """Generate report header."""
        header_lines = [
            "=" * 75,
            self._color("                    SCRAPER VALIDATION REPORT", "bold"),
            f"                    {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "=" * 75,
            "",
        ]
        return "\n".join(header_lines)

    def _sort_scores(
        self,
        scores: Dict[str, ValidationScore],
        reference_bookmaker: str
    ) -> List[tuple]:
        """Sort scores for display order."""
        def sort_key(item):
            code, score = item
            # Reference first
            if code == reference_bookmaker:
                return (0, code)
            # Exchanges second
            if score.is_exchange:
                return (1, code)
            # Then by status: PASS, WARN, FAIL
            status_order = {"PASS": 2, "WARN": 3, "FAIL": 4, "SKIP": 5, "N_A": 6}
            return (status_order.get(score.status, 5), code)

        return sorted(scores.items(), key=sort_key)

    def _format_bookmaker_line(
        self,
        score: ValidationScore,
        reference_bookmaker: str
    ) -> str:
        """Format a single bookmaker result line."""
        symbol, color = self.STATUS_SYMBOLS.get(score.status, ("?  ", "reset"))
        symbol_colored = self._color(symbol, color)

        # Build status info
        name = score.bookmaker_code.upper()
        events = f"{score.event_count} events"
        odds_count = f"odds validated"

        # Special labels
        if score.bookmaker_code == reference_bookmaker:
            extra = " (reference)"
        elif score.is_exchange:
            extra = " (exchange)"
        else:
            extra = f" | {score.coverage_percent}% coverage"

        status = score.status
        if score.is_exchange:
            status = "PASS (structure only)"
        elif score.status in {"SKIP", "N_A"}:
            if score.bookmaker_code == reference_bookmaker:
                extra = " (reference, no eligible reference fixtures)"
            else:
                extra = " (no eligible reference fixtures)"

        return f"  {symbol_colored} {name:<20} {events:>10} | {status}{extra}"

    def _format_anomaly_line(self, anomaly: OddsAnomaly) -> str:
        """Format an anomaly detail line."""
        severity_color = "red" if anomaly.severity == "critical" else "yellow"
        return self._color(
            f"     -> {anomaly.event_name}: {anomaly.selection_name} = "
            f"{anomaly.bookmaker_odds} (ref: {anomaly.reference_odds}, "
            f"{anomaly.probability_gap:.1f}pp gap)",
            severity_color
        )

    def generate_json_report(self, report: ValidationReport) -> str:
        """
        Generate JSON report for CI/CD integration.

        Args:
            report: ValidationReport to format

        Returns:
            JSON string
        """
        return report.to_json()

    def generate_summary_line(self, report: ValidationReport) -> str:
        """
        Generate a single-line summary for logs.

        Args:
            report: ValidationReport to summarize

        Returns:
            Single line summary string
        """
        return (
            f"[{report.competition}] "
            f"PASS={report.pass_count} WARN={report.warn_count} FAIL={report.fail_count} "
            f"SKIP={report.skip_count} N_A={report.na_count} | "
            f"Coverage={report.average_coverage}% | "
            f"Duration={report.validation_duration_seconds:.2f}s"
        )

    def create_report(
        self,
        scores: Dict[str, ValidationScore],
        competition: str,
        reference_bookmaker: str,
        reference_events: int,
        reference_total_events: Optional[int] = None,
        golden_fixtures_summary: Optional[Dict[str, Dict]] = None,
        validation_duration_seconds: float = 0,
    ) -> ValidationReport:
        """
        Create a ValidationReport from scores.

        Args:
            scores: Dict of {bookmaker_code: ValidationScore}
            competition: Competition name
            reference_bookmaker: Reference bookmaker code
            reference_events: Number of events in reference
            golden_fixtures_summary: Optional golden fixtures summary
            validation_duration_seconds: Time taken for validation

        Returns:
            ValidationReport object
        """
        # Calculate summary stats
        pass_count = sum(1 for s in scores.values() if s.status == "PASS")
        warn_count = sum(1 for s in scores.values() if s.status == "WARN")
        fail_count = sum(1 for s in scores.values() if s.status == "FAIL")
        skip_count = sum(1 for s in scores.values() if s.status == "SKIP")
        na_count = sum(1 for s in scores.values() if s.status == "N_A")

        total_coverage = sum(s.coverage_percent for s in scores.values())
        avg_coverage = total_coverage / len(scores) if scores else Decimal("0")

        return ValidationReport(
            competition=competition,
            reference_bookmaker=reference_bookmaker,
            reference_events=reference_events,
            reference_total_events=reference_total_events,
            scores=scores,
            golden_fixtures_summary=golden_fixtures_summary or {},
            pass_count=pass_count,
            warn_count=warn_count,
            fail_count=fail_count,
            skip_count=skip_count,
            na_count=na_count,
            average_coverage=avg_coverage.quantize(Decimal("0.1")),
            validation_duration_seconds=validation_duration_seconds,
        )

    def print_report(
        self,
        report: ValidationReport,
        output_format: Literal["terminal", "json"] = "terminal",
        show_anomalies: bool = True,
    ):
        """
        Print report to stdout.

        Args:
            report: ValidationReport to print
            output_format: "terminal" or "json"
            show_anomalies: Whether to show individual anomalies (terminal only)
        """
        if output_format == "json":
            print(self.generate_json_report(report))
        else:
            print(self.generate_terminal_report(report, show_anomalies=show_anomalies))
