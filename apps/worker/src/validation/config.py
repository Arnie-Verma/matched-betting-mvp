"""
Validation Framework Configuration

Contains all configurable thresholds, expected counts, and golden fixtures.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Tuple, Optional


# =============================================================================
# EXPECTED EVENT COUNTS PER COMPETITION
# =============================================================================
# These are configurable baselines for structural validation.
# min: minimum expected events (below = FAIL)
# max: maximum reasonable events (above = WARN)
# typical: average expected (for scoring)
EXPECTED_EVENTS: Dict[str, Dict[str, int]] = {
    # Soccer Leagues
    "epl": {"min": 3, "max": 20, "typical": 10},
    "laliga": {"min": 3, "max": 20, "typical": 10},
    "bundesliga": {"min": 3, "max": 18, "typical": 9},
    "seriea": {"min": 3, "max": 20, "typical": 10},
    "ligue1": {"min": 3, "max": 20, "typical": 10},
    "aleague": {"min": 3, "max": 12, "typical": 6},
    "ucl": {"min": 2, "max": 16, "typical": 8},
    "mls": {"min": 3, "max": 30, "typical": 12},
    # US Sports
    "nba": {"min": 5, "max": 30, "typical": 15},
    "nbl": {"min": 2, "max": 10, "typical": 4},
    "nhl": {"min": 5, "max": 30, "typical": 15},
    # Australian Sports (seasonal)
    "afl": {"min": 0, "max": 18, "typical": 9},  # Off-season Oct-Mar
    "nrl": {"min": 0, "max": 16, "typical": 8},  # Off-season Oct-Mar
    # Boxing (variable)
    "boxing": {"min": 0, "max": 20, "typical": 5},
}


# =============================================================================
# PROBABILITY THRESHOLDS (in percentage points)
# =============================================================================
# warn: Threshold to flag as suspicious (yellow)
# fail: Threshold to flag as critical (red)
#
# These are probability-point gaps, not percentage differences.
# Example: odds 1.50 = 66.67% prob, odds 1.60 = 62.50% prob, gap = 4.17pp
PROBABILITY_THRESHOLDS: Dict[str, Dict[str, Decimal]] = {
    # Moneyline favorites (odds 1.01 - 5.00, implied prob > 20%)
    "moneyline_favorite": {
        "warn": Decimal("3"),   # 3pp gap is suspicious
        "fail": Decimal("6"),   # 6pp gap is critical
    },
    # Moneyline longshots (odds > 5.00, implied prob < 20%)
    "moneyline_longshot": {
        "warn": Decimal("5"),   # 5pp gap is suspicious
        "fail": Decimal("10"),  # 10pp gap is critical
    },
    # Draw market
    "draw": {
        "warn": Decimal("4"),
        "fail": Decimal("8"),
    },
    # Handicap/spread
    "handicap": {
        "warn": Decimal("3"),
        "fail": Decimal("6"),
    },
    # Totals (over/under)
    "totals": {
        "warn": Decimal("4"),
        "fail": Decimal("8"),
    },
    # Default for unknown market types
    "default": {
        "warn": Decimal("4"),
        "fail": Decimal("8"),
    },
}


# =============================================================================
# GOLDEN FIXTURES
# =============================================================================
# Curated fixtures per league for regression safety.
# These are high-profile matches that should ALWAYS be present.
# Format: (home_team_normalized, away_team_normalized, expected_selections)
#
# NOTE: These need to be updated periodically as fixtures change.
# Focus on: major rivalries, consistent fixtures, high-liquidity events
GOLDEN_FIXTURES: Dict[str, List[Tuple[str, str, List[str]]]] = {
    "epl": [
        ("arsenal", "chelsea", ["home", "away", "draw"]),
        ("manutd", "liverpool", ["home", "away", "draw"]),
        ("mancity", "tottenham", ["home", "away", "draw"]),
        ("liverpool", "everton", ["home", "away", "draw"]),
    ],
    "laliga": [
        ("realmadrid", "barcelona", ["home", "away", "draw"]),
        ("atletico", "sevilla", ["home", "away", "draw"]),
        ("barcelona", "atletico", ["home", "away", "draw"]),
    ],
    "bundesliga": [
        ("bayern", "dortmund", ["home", "away", "draw"]),
        ("leverkusen", "bayern", ["home", "away", "draw"]),
    ],
    "seriea": [
        ("juventus", "inter", ["home", "away", "draw"]),
        ("acmilan", "inter", ["home", "away", "draw"]),
        ("napoli", "roma", ["home", "away", "draw"]),
    ],
    "ligue1": [
        ("psg", "marseille", ["home", "away", "draw"]),
        ("lyon", "psg", ["home", "away", "draw"]),
    ],
    "nba": [
        ("lalakers", "celtics", ["home", "away"]),
        ("warriors", "bucks", ["home", "away"]),
        ("sixers", "knicks", ["home", "away"]),
    ],
    "nhl": [
        ("mapleleafs", "canadiens", ["home", "away"]),
        ("bruins", "nyrangers", ["home", "away"]),
    ],
    "afl": [
        ("collingwood", "essendon", ["home", "away"]),
        ("richmond", "carlton", ["home", "away"]),
    ],
    "nrl": [
        ("broncos", "cowboys", ["home", "away"]),
        ("roosters", "rabbitohs", ["home", "away"]),
    ],
}


# =============================================================================
# ODDS BOUNDS
# =============================================================================
ODDS_MIN = Decimal("1.01")
ODDS_MAX = Decimal("1001")

# Longshot threshold (odds above this get wider thresholds)
LONGSHOT_THRESHOLD = Decimal("5.0")


# =============================================================================
# FRESHNESS
# =============================================================================
# Maximum age in seconds for scraped data to be considered "fresh"
FRESHNESS_THRESHOLD_SECONDS = 900  # 15 minutes


# =============================================================================
# SCORING THRESHOLDS
# =============================================================================
# Coverage thresholds for final scoring
COVERAGE_WARN_THRESHOLD = Decimal("85")  # Below 85% = WARN
COVERAGE_FAIL_THRESHOLD = Decimal("70")  # Below 70% = FAIL

# Event coverage thresholds vs reference bookmaker
EVENT_COVERAGE_WARN_THRESHOLD = Decimal("85")  # Below 85% = WARN
EVENT_COVERAGE_FAIL_THRESHOLD = Decimal("70")  # Below 70% = FAIL

# Anomaly thresholds for final scoring
MAX_ANOMALIES_WARN = 5   # More than 5 anomalies = WARN
MAX_CRITICAL_ANOMALIES = 2  # More than 2 critical = FAIL


# =============================================================================
# REFERENCE BOOKMAKER
# =============================================================================
# Bootstrap reference bookmaker (used for Phase 2 probability comparison)
REFERENCE_BOOKMAKER = "ladbrokes"

# Bookmakers that are exchanges (structure-only validation, no odds comparison)
EXCHANGE_BOOKMAKERS = ["betfair"]


# =============================================================================
# VALIDATION CONFIG DATACLASS
# =============================================================================
@dataclass
class ValidationConfig:
    """
    Runtime configuration for validation pipeline.

    Allows customization of thresholds and behavior at runtime.
    """
    # Reference bookmaker for probability comparison
    reference_bookmaker: str = REFERENCE_BOOKMAKER

    # Whether to use consensus median instead of single reference
    use_consensus: bool = False

    # Exchange bookmakers (structure-only validation)
    exchange_bookmakers: List[str] = field(default_factory=lambda: EXCHANGE_BOOKMAKERS.copy())

    # Validation strictness
    strict_mode: bool = False  # If True, WARN becomes FAIL

    # Expected events override
    expected_events: Optional[Dict[str, Dict[str, int]]] = None

    # Probability thresholds override
    probability_thresholds: Optional[Dict[str, Dict[str, Decimal]]] = None

    # Golden fixtures override
    golden_fixtures: Optional[Dict[str, List[Tuple[str, str, List[str]]]]] = None

    def get_expected_events(self, competition: str) -> Dict[str, int]:
        """Get expected event counts for competition."""
        events = self.expected_events or EXPECTED_EVENTS
        return events.get(competition, {"min": 1, "max": 50, "typical": 10})

    def get_probability_thresholds(self, market_type: str) -> Dict[str, Decimal]:
        """Get probability thresholds for market type."""
        thresholds = self.probability_thresholds or PROBABILITY_THRESHOLDS
        return thresholds.get(market_type, thresholds["default"])

    def get_golden_fixtures(self, competition: str) -> List[Tuple[str, str, List[str]]]:
        """Get golden fixtures for competition."""
        fixtures = self.golden_fixtures or GOLDEN_FIXTURES
        return fixtures.get(competition, [])

    def is_exchange(self, bookmaker_code: str) -> bool:
        """Check if bookmaker is an exchange (structure-only validation)."""
        return bookmaker_code.lower() in [b.lower() for b in self.exchange_bookmakers]
