"""
Validation Framework Configuration

Contains all configurable thresholds, expected counts, and golden fixtures.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Tuple, Optional, Set, Literal


# =============================================================================
# EXPECTED EVENT COUNTS PER COMPETITION
# =============================================================================
# These are configurable baselines for structural validation.
# min: minimum expected events (below = FAIL)
# max: maximum reasonable events (above = WARN)
# typical: average expected (for scoring)
EXPECTED_EVENTS: Dict[str, Dict[str, int]] = {
    # Soccer Leagues
    "epl": {"min": 3, "max": 50, "typical": 20},
    "laliga": {"min": 3, "max": 20, "typical": 10},
    "bundesliga": {"min": 3, "max": 18, "typical": 9},
    "seriea": {"min": 3, "max": 20, "typical": 10},
    "ligue1": {"min": 3, "max": 20, "typical": 10},
    "aleague": {"min": 3, "max": 12, "typical": 6},
    "ucl": {"min": 2, "max": 16, "typical": 8},
    "mls": {"min": 3, "max": 30, "typical": 12},
    # US Sports (seasonal; slates can be very small day-to-day)
    "nba": {"min": 0, "max": 60, "typical": 20},
    "nbl": {"min": 0, "max": 20, "typical": 8},
    "nhl": {"min": 0, "max": 60, "typical": 20},
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

# Some competitions (e.g. boxing) have genuinely variable fixture coverage across
# bookmakers. Use per-competition overrides so we don't mark a scraper as
# "broken" just because a bookmaker lists fewer events than the reference.
EVENT_COVERAGE_THRESHOLDS_BY_COMPETITION: Dict[str, Dict[str, Decimal]] = {
    # EPL: Punterstech platform books can be materially narrower than Entain
    # reference windows. Keep hard fail for severe drop while reducing false fails.
    "epl": {"warn": Decimal("70"), "fail": Decimal("55")},
    # NBL windows can be shallow with platform-specific omissions.
    "nbl": {"warn": Decimal("65"), "fail": Decimal("45")},
    # NHL cross-platform overlap varies by listing cadence.
    "nhl": {"warn": Decimal("70"), "fail": Decimal("60")},
    # Boxing fight cards differ by bookmaker; require only minimal overlap.
    "boxing": {"warn": Decimal("30"), "fail": Decimal("15")},
    # NBA slates can be small (e.g. only a handful of games today). A single
    # missing game can drop coverage below 85% even when the scraper is healthy.
    "nba": {"warn": Decimal("80"), "fail": Decimal("60")},
}

# Anomaly thresholds for final scoring
MAX_ANOMALIES_WARN = 5   # More than 5 anomalies = WARN
MAX_CRITICAL_ANOMALIES = 2  # More than 2 critical = FAIL

# Competition-specific anomaly tolerance calibration for Phase A stabilization.
# These thresholds only affect final scoring classification (not anomaly detection).
ANOMALY_THRESHOLDS_BY_COMPETITION: Dict[str, Dict[str, int]] = {
    "epl": {"warn": 25, "critical": 5},
    "nba": {"warn": 60, "critical": 50},
    "nhl": {"warn": 20, "critical": 6},
}


# =============================================================================
# REFERENCE BOOKMAKER
# =============================================================================
# Bootstrap reference bookmaker (used for Phase 2 probability comparison)
REFERENCE_BOOKMAKER = "ladbrokes"

# Bookmakers that are exchanges (structure-only validation, no odds comparison)
EXCHANGE_BOOKMAKERS = ["betfair"]


# =============================================================================
# ELIGIBLE FIXTURE REQUIREMENTS
# =============================================================================
# Validation should only compare fixtures that have the expected market shape in
# the reference bookmaker feed for the target competition window.
REFERENCE_SELECTION_KEYS_BY_COMPETITION: Dict[str, Set[str]] = {
    # Soccer competitions are 3-way (home/away/draw)
    "epl": {"home", "away", "draw"},
    "laliga": {"home", "away", "draw"},
    "bundesliga": {"home", "away", "draw"},
    "seriea": {"home", "away", "draw"},
    "ligue1": {"home", "away", "draw"},
    "aleague": {"home", "away", "draw"},
    "ucl": {"home", "away", "draw"},
    "mls": {"home", "away", "draw"},
    # 2-way competitions
    "afl": {"home", "away"},
    "nrl": {"home", "away"},
    "nba": {"home", "away"},
    "nbl": {"home", "away"},
    "nhl": {"home", "away"},
    # Boxing can expose draw in some books, but home/away are the minimum shape.
    "boxing": {"home", "away"},
}

# =============================================================================
# BOOKMAKER X COMPETITION COVERAGE POLICY
# =============================================================================
# Explicit scope policy for expected coverage by competition.
# - "in_scope": bookmaker is expected to provide coverage and can FAIL on 0 events
# - "out_of_scope": bookmaker is not expected to provide coverage and should SKIP
#   for that competition window.
BOOKMAKER_COMPETITION_COVERAGE_POLICY: Dict[str, Dict[str, Set[str]]] = {
    "boxing": {
        # Boxing market depth differs significantly by provider. During Phase A
        # we only gate in-scope coverage on core books with demonstrated depth.
        "in_scope": {"ladbrokes", "neds", "betfair"},
    },
    "nbl": {
        # Punterstech-derived books currently not in scope for NBL coverage.
        # Keep this explicit so 0-event windows are classified as SKIP, not FAIL.
        "out_of_scope": {"betblitz", "starsports", "truebet", "wizbet"},
    },
}


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

    # Bookmaker x competition coverage scope policy override
    bookmaker_competition_coverage_policy: Optional[Dict[str, Dict[str, Set[str]]]] = None

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

    def get_reference_selection_keys(self, competition: str) -> Set[str]:
        """
        Get required selection keys for a reference fixture to be eligible.

        Defaults to 2-way market shape when competition is unknown.
        """
        comp = (competition or "").strip().lower()
        return REFERENCE_SELECTION_KEYS_BY_COMPETITION.get(comp, {"home", "away"})

    def get_event_coverage_thresholds(self, competition: str) -> Tuple[Decimal, Decimal]:
        """
        Get event coverage thresholds (warn, fail) for a competition.

        Defaults to the global thresholds when no override is defined.
        """
        comp = (competition or "").strip().lower()
        overrides = EVENT_COVERAGE_THRESHOLDS_BY_COMPETITION.get(comp)
        if overrides:
            return overrides["warn"], overrides["fail"]
        return EVENT_COVERAGE_WARN_THRESHOLD, EVENT_COVERAGE_FAIL_THRESHOLD

    def get_anomaly_thresholds(self, competition: str) -> Tuple[int, int]:
        """
        Get anomaly thresholds (warn_total, fail_critical) for a competition.

        Returns global defaults when no override exists.
        """
        comp = (competition or "").strip().lower()
        overrides = ANOMALY_THRESHOLDS_BY_COMPETITION.get(comp)
        if overrides:
            return overrides["warn"], overrides["critical"]
        return MAX_ANOMALIES_WARN, MAX_CRITICAL_ANOMALIES

    def get_bookmaker_competition_scope(
        self,
        bookmaker_code: str,
        competition: str,
    ) -> Literal["in_scope", "out_of_scope"]:
        """
        Return coverage scope for bookmaker x competition.

        Defaults to "in_scope" when no explicit policy entry exists.
        """
        comp = (competition or "").strip().lower()
        code = (bookmaker_code or "").strip().lower()
        policy = (
            self.bookmaker_competition_coverage_policy
            or BOOKMAKER_COMPETITION_COVERAGE_POLICY
        )
        comp_policy = policy.get(comp, {})

        out_of_scope_codes = {
            str(item).strip().lower()
            for item in comp_policy.get("out_of_scope", set())
            if item is not None
        }
        if code in out_of_scope_codes:
            return "out_of_scope"

        in_scope_codes = {
            str(item).strip().lower()
            for item in comp_policy.get("in_scope", set())
            if item is not None
        }
        if in_scope_codes and code not in in_scope_codes:
            return "out_of_scope"

        return "in_scope"
