"""
Phase 2: Odds Sanity via Implied Probability

Validates odds by comparing implied probabilities:
- Convert odds -> implied probability: p = 1/odds
- Compare to reference (Ladbrokes) or consensus median
- Flag if gap > threshold (market-type aware)

Catches: mis-parsed odds, swapped runners, stale data
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional, Tuple, Literal
from statistics import median

from validation.config import (
    ValidationConfig,
    PROBABILITY_THRESHOLDS,
    LONGSHOT_THRESHOLD,
)

logger = logging.getLogger(__name__)


@dataclass
class OddsAnomaly:
    """Details of an anomalous odds value."""
    event_name: str
    event_key: str  # Normalized event key
    selection_name: str
    selection_key: str

    # Bookmaker odds
    bookmaker_code: str
    bookmaker_odds: Decimal
    bookmaker_probability: Decimal

    # Reference odds
    reference_odds: Decimal
    reference_probability: Decimal
    reference_source: str  # "ladbrokes" or "consensus"

    # Gap analysis
    probability_gap: Decimal  # Absolute gap in percentage points
    severity: Literal["warn", "critical"]

    def __str__(self) -> str:
        return (
            f"{self.event_name}: {self.selection_name} = {self.bookmaker_odds} "
            f"(ref: {self.reference_odds}, {self.probability_gap:.1f}pp gap)"
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_name": self.event_name,
            "event_key": self.event_key,
            "selection_name": self.selection_name,
            "selection_key": self.selection_key,
            "bookmaker_code": self.bookmaker_code,
            "bookmaker_odds": str(self.bookmaker_odds),
            "bookmaker_probability": str(self.bookmaker_probability),
            "reference_odds": str(self.reference_odds),
            "reference_probability": str(self.reference_probability),
            "reference_source": self.reference_source,
            "probability_gap": str(self.probability_gap),
            "severity": self.severity,
        }


@dataclass
class ProbabilityValidation:
    """Phase 2 validation results for a single bookmaker."""
    bookmaker_code: str
    competition: str

    # Comparison statistics
    odds_compared: int = 0
    odds_matched: int = 0  # Within threshold
    odds_warn: int = 0
    odds_critical: int = 0

    # Anomalies (sorted by severity, then gap)
    anomalies: List[OddsAnomaly] = field(default_factory=list)

    # Reference info
    reference_source: str = "ladbrokes"
    reference_events: int = 0

    # Timing
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def coverage_percent(self) -> Decimal:
        """Percentage of odds that could be compared to reference."""
        if self.odds_compared == 0:
            return Decimal("0")
        return Decimal(self.odds_matched + self.odds_warn + self.odds_critical) / Decimal(self.odds_compared) * 100

    @property
    def match_rate(self) -> Decimal:
        """Percentage of compared odds within threshold."""
        total_compared = self.odds_matched + self.odds_warn + self.odds_critical
        if total_compared == 0:
            return Decimal("100")
        return Decimal(self.odds_matched) / Decimal(total_compared) * 100

    @property
    def passed(self) -> bool:
        """Check if probability validation passed (no critical anomalies)."""
        return self.odds_critical <= 2  # Allow up to 2 critical anomalies

    @property
    def worst_anomalies(self) -> List[OddsAnomaly]:
        """Get top 5 worst anomalies by severity and gap."""
        sorted_anomalies = sorted(
            self.anomalies,
            key=lambda a: (0 if a.severity == "critical" else 1, -float(a.probability_gap))
        )
        return sorted_anomalies[:5]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "bookmaker_code": self.bookmaker_code,
            "competition": self.competition,
            "odds_compared": self.odds_compared,
            "odds_matched": self.odds_matched,
            "odds_warn": self.odds_warn,
            "odds_critical": self.odds_critical,
            "coverage_percent": str(self.coverage_percent),
            "match_rate": str(self.match_rate),
            "passed": self.passed,
            "anomaly_count": len(self.anomalies),
            "worst_anomalies": [a.to_dict() for a in self.worst_anomalies],
            "reference_source": self.reference_source,
            "validated_at": self.validated_at.isoformat(),
        }


class ProbabilityValidator:
    """
    Phase 2: Probability-based odds validation.

    Compares odds to reference (Ladbrokes or consensus) using implied probability.
    Market-type aware thresholds account for different spreads in favorites vs longshots.
    """

    def __init__(self, config: Optional[ValidationConfig] = None):
        """
        Initialize probability validator.

        Args:
            config: Validation configuration (uses defaults if None)
        """
        self.config = config or ValidationConfig()

    @staticmethod
    def odds_to_probability(odds: Decimal) -> Decimal:
        """
        Convert decimal odds to implied probability (0-100).

        Args:
            odds: Decimal odds (e.g., 1.50)

        Returns:
            Implied probability as percentage (e.g., 66.67)
        """
        if odds <= 0:
            return Decimal("0")
        return (Decimal("1") / odds * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @staticmethod
    def probability_gap(odds1: Decimal, odds2: Decimal) -> Decimal:
        """
        Calculate gap in percentage points between two odds.

        Args:
            odds1: First odds value
            odds2: Second odds value

        Returns:
            Absolute difference in implied probability (percentage points)
        """
        p1 = ProbabilityValidator.odds_to_probability(odds1)
        p2 = ProbabilityValidator.odds_to_probability(odds2)
        return abs(p1 - p2)

    def get_thresholds(
        self,
        odds: Decimal,
        market_type: str
    ) -> Tuple[Decimal, Decimal]:
        """
        Get warn/fail thresholds based on odds level and market type.

        Args:
            odds: The odds value being validated
            market_type: Type of market (match_winner, draw, etc.)

        Returns:
            Tuple of (warn_threshold, fail_threshold) in percentage points
        """
        # Exchanges get infinite thresholds (structure-only validation)
        if market_type == "exchange":
            return (Decimal("999"), Decimal("999"))

        # Determine if longshot
        is_longshot = odds > LONGSHOT_THRESHOLD

        # Get base thresholds
        if market_type in ("match_winner", "moneyline"):
            if is_longshot:
                thresholds = self.config.get_probability_thresholds("moneyline_longshot")
            else:
                thresholds = self.config.get_probability_thresholds("moneyline_favorite")
        elif market_type == "draw":
            thresholds = self.config.get_probability_thresholds("draw")
        elif market_type in ("handicap", "spread"):
            thresholds = self.config.get_probability_thresholds("handicap")
        elif market_type in ("total", "totals", "over_under"):
            thresholds = self.config.get_probability_thresholds("totals")
        else:
            thresholds = self.config.get_probability_thresholds("default")

        return (thresholds["warn"], thresholds["fail"])

    def validate(
        self,
        bookmaker_odds: Dict[str, Dict[str, Dict]],
        reference_odds: Dict[str, Dict[str, Dict]],
        bookmaker_code: str,
        competition: str,
    ) -> ProbabilityValidation:
        """
        Validate bookmaker odds against reference.

        Args:
            bookmaker_odds: Dict of {event_key: {selection_key: odds_dict}}
            reference_odds: Dict of {event_key: {selection_key: odds_dict}}
            bookmaker_code: Bookmaker being validated
            competition: Competition being validated

        Returns:
            ProbabilityValidation with all comparison results
        """
        result = ProbabilityValidation(
            bookmaker_code=bookmaker_code,
            competition=competition,
            reference_source=self.config.reference_bookmaker,
            reference_events=len(reference_odds),
        )

        # Skip if exchange (structure-only validation)
        if self.config.is_exchange(bookmaker_code):
            logger.info(
                f"[{bookmaker_code}] Skipping probability validation (exchange)"
            )
            return result

        # Compare each odds point
        for event_key, selections in bookmaker_odds.items():
            # Check if event exists in reference
            ref_selections = reference_odds.get(event_key, {})
            if not ref_selections:
                continue

            for selection_key, odds_data in selections.items():
                result.odds_compared += 1

                # Get reference odds for this selection
                ref_odds_data = ref_selections.get(selection_key)
                if not ref_odds_data:
                    continue

                # Extract odds values
                bm_odds = self._extract_odds(odds_data)
                ref_odds = self._extract_odds(ref_odds_data)

                if bm_odds is None or ref_odds is None:
                    continue

                # Calculate probability gap
                gap = self.probability_gap(bm_odds, ref_odds)

                # Get market type
                market_type = odds_data.get("market_type", "match_winner")

                # Get thresholds
                warn_threshold, fail_threshold = self.get_thresholds(bm_odds, market_type)

                # Categorize
                if gap >= fail_threshold:
                    result.odds_critical += 1
                    severity = "critical"
                elif gap >= warn_threshold:
                    result.odds_warn += 1
                    severity = "warn"
                else:
                    result.odds_matched += 1
                    continue  # No anomaly to record

                # Record anomaly
                anomaly = OddsAnomaly(
                    event_name=odds_data.get("event_name", event_key),
                    event_key=event_key,
                    selection_name=odds_data.get("selection_name", selection_key),
                    selection_key=selection_key,
                    bookmaker_code=bookmaker_code,
                    bookmaker_odds=bm_odds,
                    bookmaker_probability=self.odds_to_probability(bm_odds),
                    reference_odds=ref_odds,
                    reference_probability=self.odds_to_probability(ref_odds),
                    reference_source=self.config.reference_bookmaker,
                    probability_gap=gap,
                    severity=severity,
                )
                result.anomalies.append(anomaly)

        # Log result
        log_level = logging.INFO if result.passed else logging.WARNING
        logger.log(
            log_level,
            f"[{bookmaker_code}] Probability validation: "
            f"compared={result.odds_compared} "
            f"matched={result.odds_matched} "
            f"warn={result.odds_warn} "
            f"critical={result.odds_critical} "
            f"passed={result.passed}"
        )

        return result

    def _extract_odds(self, odds_data: Dict) -> Optional[Decimal]:
        """Extract odds value from odds dictionary."""
        value = odds_data.get("decimal_odds") or odds_data.get("odds")
        if value is None:
            return None

        if isinstance(value, Decimal):
            return value

        try:
            return Decimal(str(value))
        except Exception:
            return None

    def calculate_consensus(
        self,
        all_bookmaker_odds: Dict[str, Dict[str, Dict[str, Dict]]],
        event_key: str,
        selection_key: str,
    ) -> Optional[Decimal]:
        """
        Calculate consensus median probability from multiple bookmakers.

        Args:
            all_bookmaker_odds: Dict of {bookmaker: {event_key: {selection_key: odds}}}
            event_key: Event to get consensus for
            selection_key: Selection to get consensus for

        Returns:
            Median implied probability, or None if insufficient data
        """
        probs = []

        for bookmaker_code, events in all_bookmaker_odds.items():
            # Skip exchanges
            if self.config.is_exchange(bookmaker_code):
                continue

            if event_key in events and selection_key in events[event_key]:
                odds = self._extract_odds(events[event_key][selection_key])
                if odds:
                    probs.append(float(self.odds_to_probability(odds)))

        if len(probs) < 3:  # Need at least 3 bookmakers for meaningful consensus
            return None

        return Decimal(str(median(probs)))

    def validate_with_consensus(
        self,
        all_bookmaker_odds: Dict[str, Dict[str, Dict[str, Dict]]],
        bookmaker_code: str,
        competition: str,
    ) -> ProbabilityValidation:
        """
        Validate bookmaker odds against consensus median.

        Used when we have enough bookmakers to calculate meaningful consensus.

        Args:
            all_bookmaker_odds: Dict of {bookmaker: {event_key: {selection_key: odds}}}
            bookmaker_code: Bookmaker being validated
            competition: Competition being validated

        Returns:
            ProbabilityValidation with all comparison results
        """
        result = ProbabilityValidation(
            bookmaker_code=bookmaker_code,
            competition=competition,
            reference_source="consensus",
            reference_events=0,
        )

        # Skip if exchange
        if self.config.is_exchange(bookmaker_code):
            logger.info(
                f"[{bookmaker_code}] Skipping probability validation (exchange)"
            )
            return result

        bookmaker_odds = all_bookmaker_odds.get(bookmaker_code, {})

        for event_key, selections in bookmaker_odds.items():
            for selection_key, odds_data in selections.items():
                result.odds_compared += 1

                # Calculate consensus
                consensus_prob = self.calculate_consensus(
                    all_bookmaker_odds, event_key, selection_key
                )
                if consensus_prob is None:
                    continue

                # Extract bookmaker odds
                bm_odds = self._extract_odds(odds_data)
                if bm_odds is None:
                    continue

                # Calculate gap (using probability directly)
                bm_prob = self.odds_to_probability(bm_odds)
                gap = abs(bm_prob - consensus_prob)

                # Get market type
                market_type = odds_data.get("market_type", "match_winner")

                # Get thresholds
                warn_threshold, fail_threshold = self.get_thresholds(bm_odds, market_type)

                # Categorize
                if gap >= fail_threshold:
                    result.odds_critical += 1
                    severity = "critical"
                elif gap >= warn_threshold:
                    result.odds_warn += 1
                    severity = "warn"
                else:
                    result.odds_matched += 1
                    continue

                # Convert consensus probability back to odds for display
                consensus_odds = Decimal("1") / (consensus_prob / Decimal("100"))

                # Record anomaly
                anomaly = OddsAnomaly(
                    event_name=odds_data.get("event_name", event_key),
                    event_key=event_key,
                    selection_name=odds_data.get("selection_name", selection_key),
                    selection_key=selection_key,
                    bookmaker_code=bookmaker_code,
                    bookmaker_odds=bm_odds,
                    bookmaker_probability=bm_prob,
                    reference_odds=consensus_odds.quantize(Decimal("0.01")),
                    reference_probability=consensus_prob,
                    reference_source="consensus",
                    probability_gap=gap,
                    severity=severity,
                )
                result.anomalies.append(anomaly)

        logger.info(
            f"[{bookmaker_code}] Consensus validation: "
            f"compared={result.odds_compared} "
            f"matched={result.odds_matched} "
            f"warn={result.odds_warn} "
            f"critical={result.odds_critical}"
        )

        return result
