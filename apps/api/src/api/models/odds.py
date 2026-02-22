# apps/api/src/api/models/odds.py
"""Core odds and betting models for Australian matched betting platform"""
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, ForeignKey,
    Text, JSON, Numeric, Index, UniqueConstraint, event
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from api.core.database import Base
from api.core.bookmaker_freeze import is_bookmaker_frozen


class SourceType(str, Enum):
    """Data source types"""
    SCRAPE = "scrape"
    API = "api"
    MANUAL = "manual"


class SportType(str, Enum):
    """Australian sports coverage"""
    AFL = "afl"
    NRL = "nrl"
    CRICKET = "cricket"
    TENNIS = "tennis"
    HORSE_RACING = "horse_racing"
    SOCCER = "soccer"
    BASKETBALL = "basketball"
    RUGBY_UNION = "rugby_union"


class MarketType(str, Enum):
    """Standard Australian betting markets"""
    MATCH_WINNER = "match_winner"  # Head to head
    HANDICAP = "handicap"  # Line betting
    TOTAL_POINTS = "total_points"  # Over/Under
    FIRST_GOALSCORER = "first_goalscorer"
    CORRECT_SCORE = "correct_score"
    EACH_WAY = "each_way"  # Horse racing
    WIN_PLACE = "win_place"  # Horse racing
    MULTI_BET = "multi_bet"  # Combinations


class EventStatus(str, Enum):
    """Event lifecycle status"""
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"


class BookmakerLifecycleState(str, Enum):
    """Bookmaker onboarding and runtime lifecycle states."""
    BACKLOG = "backlog"
    DISCOVERY_COMPLETE = "discovery_complete"
    ADAPTER_READY = "adapter_ready"
    CONFIG_READY = "config_ready"
    VALIDATION_PASSED = "validation_passed"
    CANARY_ACTIVE = "canary_active"
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISABLED = "disabled"


class Sport(Base):
    """Sports taxonomy for Australian betting"""
    __tablename__ = "sports"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)  # SportType enum
    name = Column(String(100), nullable=False)  # "Australian Football League"
    display_name = Column(String(50), nullable=False)  # "AFL"
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    # Australian-specific metadata
    season_format = Column(JSON, nullable=True)  # {"start_month": 3, "end_month": 9}
    common_markets = Column(JSON, nullable=True)  # ["match_winner", "handicap", "total_points"]

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    competitions = relationship("Competition", back_populates="sport", cascade="all, delete-orphan")


class Competition(Base):
    """Competitions within sports (AFL Premiership, NRL Finals, etc.)"""
    __tablename__ = "competitions"

    id = Column(Integer, primary_key=True, index=True)
    sport_id = Column(Integer, ForeignKey("sports.id"), nullable=False)

    name = Column(String(200), nullable=False)  # "AFL Premiership Season 2025"
    short_name = Column(String(50), nullable=False)  # "AFL 2025"
    external_ids = Column(JSON, nullable=True)  # {"sportsbet": "comp_123", "tab": "afl2025"}

    # Competition metadata
    country = Column(String(10), default="AU", nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    sport = relationship("Sport", back_populates="competitions")
    events = relationship("Event", back_populates="competition", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_competition_sport_active", "sport_id", "is_active"),
    )


class Team(Base):
    """Normalized team/participant names for cross-bookmaker matching"""
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    sport_id = Column(Integer, ForeignKey("sports.id"), nullable=False)

    # Canonical team information
    canonical_name = Column(String(100), nullable=False)  # "Richmond Tigers"
    short_name = Column(String(20), nullable=False)  # "RICH"
    display_name = Column(String(50), nullable=False)  # "Richmond"

    # Bookmaker name variations for matching
    name_variations = Column(JSON, nullable=True)  # {"sportsbet": "Richmond", "tab": "Tigers", "bet365": "Richmond Tigers"}
    external_ids = Column(JSON, nullable=True)  # Bookmaker-specific IDs

    # Team metadata
    location = Column(String(100), nullable=True)  # "Melbourne, VIC"
    founded_year = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    sport = relationship("Sport")
    home_events = relationship("Event", foreign_keys="Event.home_team_id", back_populates="home_team")
    away_events = relationship("Event", foreign_keys="Event.away_team_id", back_populates="away_team")

    # Constraints
    __table_args__ = (
        Index("idx_team_sport_active", "sport_id", "is_active"),
        UniqueConstraint("sport_id", "canonical_name", name="uq_team_sport_canonical"),
    )


class Bookmaker(Base):
    """Australian bookmaker registry"""
    __tablename__ = "bookmakers"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(30), unique=True, nullable=False, index=True)  # "sportsbet"
    name = Column(String(100), nullable=False)  # "Sportsbet"
    display_name = Column(String(50), nullable=False)  # "Sportsbet"

    # Bookmaker configuration
    website_url = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    supports_each_way = Column(Boolean, default=False)
    country = Column(String(10), default="AU", nullable=False)

    # Data source configuration
    default_source_type = Column(String(20), default=SourceType.SCRAPE, nullable=False)
    base_url = Column(String(200), nullable=True)  # For scraping
    api_endpoint = Column(String(200), nullable=True)  # For API access
    rate_limit_seconds = Column(Integer, default=5, nullable=False)

    # Scraping metadata
    scraping_config = Column(JSON, nullable=True)  # Headers, selectors, etc.
    last_successful_scrape = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, default=0)

    # Lifecycle metadata
    lifecycle_state = Column(
        String(40),
        nullable=False,
        default=BookmakerLifecycleState.BACKLOG.value,
        server_default=BookmakerLifecycleState.BACKLOG.value,
        index=True,
    )
    lifecycle_state_updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    lifecycle_last_transition_at = Column(DateTime(timezone=True), nullable=True)
    lifecycle_last_transition_by = Column(String(120), nullable=True)
    lifecycle_last_transition_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    bookmaker_sources = relationship("BookmakerSource", back_populates="bookmaker", cascade="all, delete-orphan")
    odds_snapshots = relationship("OddsSnapshot", back_populates="bookmaker", cascade="all, delete-orphan")
    lifecycle_transitions = relationship(
        "BookmakerLifecycleTransition",
        back_populates="bookmaker",
        cascade="all, delete-orphan",
        order_by="BookmakerLifecycleTransition.created_at",
    )


class BookmakerLifecycleTransition(Base):
    """Audit trail for bookmaker lifecycle state transitions."""
    __tablename__ = "bookmaker_lifecycle_transitions"

    id = Column(Integer, primary_key=True, index=True)
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False, index=True)
    from_state = Column(String(40), nullable=False)
    to_state = Column(String(40), nullable=False)
    transition_reason = Column(Text, nullable=False)
    transition_metadata = Column(JSON, nullable=True)
    transitioned_by = Column(String(120), nullable=True)
    transitioned_by_email = Column(String(255), nullable=True)
    transition_source = Column(String(50), nullable=False, default="api")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    bookmaker = relationship("Bookmaker", back_populates="lifecycle_transitions")

    __table_args__ = (
        Index("idx_bookmaker_lifecycle_transition_lookup", "bookmaker_id", "created_at"),
        Index("idx_bookmaker_lifecycle_transition_to_state", "to_state", "created_at"),
    )


class BookmakerSource(Base):
    """Individual data sources for each bookmaker (hybrid API/scraping)"""
    __tablename__ = "bookmaker_sources"

    id = Column(Integer, primary_key=True, index=True)
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False)

    source_type = Column(String(20), nullable=False)  # SourceType enum
    endpoint_url = Column(String(500), nullable=False)  # Specific URL or API endpoint
    source_config = Column(JSON, nullable=True)  # Headers, auth, selectors

    # Rate limiting and reliability
    rate_limit_ms = Column(Integer, default=5000, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    timeout_seconds = Column(Integer, default=30, nullable=False)

    # Status tracking
    is_active = Column(Boolean, default=True)
    last_accessed = Column(DateTime(timezone=True), nullable=True)
    last_success = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, default=0)
    average_response_time_ms = Column(Integer, nullable=True)

    # Error tracking
    last_error = Column(Text, nullable=True)
    error_count_24h = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    bookmaker = relationship("Bookmaker", back_populates="bookmaker_sources")

    # Indexes
    __table_args__ = (
        Index("idx_source_bookmaker_active", "bookmaker_id", "is_active"),
        Index("idx_source_type_active", "source_type", "is_active"),
    )


class Event(Base):
    """Individual matches/events for betting"""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"), nullable=False)

    # Event details
    name = Column(String(200), nullable=False)  # "Richmond vs Collingwood"
    normalized_name = Column(String(200), nullable=True)  # Canonical form for cross-bookmaker matching: "collingwoodvrichmond"
    short_name = Column(String(100), nullable=True)  # "RICH v COLL"
    external_ids = Column(JSON, nullable=True)  # Bookmaker event IDs for matching

    # Participants (flexible for individual sports)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    participants = Column(JSON, nullable=True)  # For tennis, horse racing, etc.

    # Event timing
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default=EventStatus.SCHEDULED, nullable=False)

    # Event metadata
    venue = Column(String(200), nullable=True)
    round_number = Column(Integer, nullable=True)  # AFL Round 1, etc.
    event_metadata = Column(JSON, nullable=True)  # Weather, conditions, etc.

    # Result data (when finished)
    result = Column(JSON, nullable=True)  # {"home_score": 95, "away_score": 87}

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    competition = relationship("Competition", back_populates="events")
    home_team = relationship("Team", foreign_keys=[home_team_id], back_populates="home_events")
    away_team = relationship("Team", foreign_keys=[away_team_id], back_populates="away_events")
    markets = relationship("Market", back_populates="event", cascade="all, delete-orphan")

    # Computed properties
    @hybrid_property
    def sport_id(self):
        return self.competition.sport_id if self.competition else None

    # Indexes
    __table_args__ = (
        Index("idx_event_competition_start", "competition_id", "start_time"),
        Index("idx_event_status_start", "status", "start_time"),
        Index("idx_event_teams", "home_team_id", "away_team_id"),
        Index("idx_event_normalized", "competition_id", "normalized_name", "start_time"),  # Cross-bookmaker matching
    )


class Market(Base):
    """Betting markets within events (Head-to-Head, Handicap, etc.)"""
    __tablename__ = "markets"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)

    market_type = Column(String(50), nullable=False)  # MarketType enum
    name = Column(String(200), nullable=False)  # "Head To Head", "Line Betting (+7.5)"
    description = Column(Text, nullable=True)

    # Market parameters (for handicaps, totals, etc.)
    parameters = Column(JSON, nullable=True)  # {"handicap": 7.5, "total": 165.5}
    external_ids = Column(JSON, nullable=True)  # Bookmaker market IDs

    # Market metadata
    is_active = Column(Boolean, default=True)
    opens_at = Column(DateTime(timezone=True), nullable=True)
    closes_at = Column(DateTime(timezone=True), nullable=True)

    # Result data
    result = Column(JSON, nullable=True)  # {"winning_selection": "home"}
    settled_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    event = relationship("Event", back_populates="markets")
    selections = relationship("Selection", back_populates="market", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_market_event_type", "event_id", "market_type"),
        Index("idx_market_active_closes", "is_active", "closes_at"),
    )


class Selection(Base):
    """Individual betting options within markets (Home/Away/Draw, Over/Under, etc.)"""
    __tablename__ = "selections"

    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(Integer, ForeignKey("markets.id"), nullable=False)

    name = Column(String(200), nullable=False)  # "Richmond Tigers", "Over 165.5", "Draw"
    short_name = Column(String(50), nullable=True)  # "RICH", "Over", "Draw"
    selection_key = Column(String(50), nullable=False)  # "home", "away", "draw", "over", "under"

    # Selection metadata
    parameters = Column(JSON, nullable=True)  # For player-specific bets, etc.
    external_ids = Column(JSON, nullable=True)  # Bookmaker selection IDs
    sort_order = Column(Integer, default=0)

    # Result tracking
    is_winner = Column(Boolean, nullable=True)  # Set when market settles

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    market = relationship("Market", back_populates="selections")
    odds_snapshots = relationship("OddsSnapshot", back_populates="selection", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_selection_market_key", "market_id", "selection_key"),
        UniqueConstraint("market_id", "selection_key", name="uq_selection_market_key"),
    )


class OddsSnapshot(Base):
    """Real-time odds data from bookmakers"""
    __tablename__ = "odds_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    selection_id = Column(Integer, ForeignKey("selections.id"), nullable=False)
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False)

    # Odds data (stored as Decimal for precision)
    decimal_odds = Column(Numeric(10, 4), nullable=False)  # 1.9000, 2.5000, etc.

    # Data source tracking
    source_type = Column(String(20), nullable=False)  # SourceType enum
    source_url = Column(String(500), nullable=True)
    confidence_score = Column(Numeric(3, 2), default=1.0)  # 0.0-1.0, lower for scraped data

    # Temporal data
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    timestamp_bucket = Column(DateTime(timezone=True), nullable=True)  # Rounded timestamp for deduplication (e.g., floor to nearest 5min)
    is_current = Column(Boolean, default=True, index=True)  # Latest odds for this selection/bookmaker

    # Market context at time of snapshot
    market_status = Column(String(20), nullable=True)  # "open", "suspended", "closed"
    available_amount = Column(Numeric(12, 2), nullable=True)  # Max bet amount in AUD cents

    # Data quality tracking
    scrape_session_id = Column(String(100), nullable=True)  # For grouping simultaneous scrapes
    processing_time_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    selection = relationship("Selection", back_populates="odds_snapshots")
    bookmaker = relationship("Bookmaker", back_populates="odds_snapshots")

    # Computed properties for display
    @hybrid_property
    def decimal_odds_display(self):
        """Return odds formatted for Australian display (2 decimal places)"""
        return f"{float(self.decimal_odds):.2f}"

    @hybrid_property
    def implied_probability(self):
        """Calculate implied probability from decimal odds"""
        return 1.0 / float(self.decimal_odds) if self.decimal_odds > 0 else 0.0

    # Indexes for performance
    __table_args__ = (
        Index("idx_odds_selection_current", "selection_id", "is_current"),
        Index("idx_odds_bookmaker_current", "bookmaker_id", "is_current"),
        Index("idx_odds_timestamp", "timestamp"),
        Index("idx_odds_timestamp_bucket", "timestamp_bucket"),  # For cleanup queries
        Index("idx_odds_selection_bookmaker_current", "selection_id", "bookmaker_id", "is_current"),
        # Old constraint - will be dropped in migration
        # UniqueConstraint("selection_id", "bookmaker_id", "timestamp", name="uq_odds_selection_bookmaker_time"),
        # New idempotent constraint - prevents duplicates on retries
        UniqueConstraint("selection_id", "bookmaker_id", "timestamp_bucket", "scrape_session_id",
                        name="uq_odds_dedupe"),
    )


class OddsComparison(Base):
    """Pre-computed odds comparisons for matched betting opportunities"""
    __tablename__ = "odds_comparisons"

    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(Integer, ForeignKey("markets.id"), nullable=False)

    # Best odds for each selection
    best_back_selection_id = Column(Integer, ForeignKey("selections.id"), nullable=False)
    best_back_bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False)
    best_back_odds = Column(Numeric(10, 4), nullable=False)

    best_lay_selection_id = Column(Integer, ForeignKey("selections.id"), nullable=False)
    best_lay_bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False)
    best_lay_odds = Column(Numeric(10, 4), nullable=False)

    # Matched betting calculations
    arbitrage_percentage = Column(Numeric(5, 4), nullable=False)  # 0.95 = 95% (profit opportunity when < 1.0)
    profit_margin_percentage = Column(Numeric(5, 4), nullable=False)  # Expected profit %
    recommended_stake_aud = Column(Numeric(10, 2), nullable=False)  # In AUD cents

    # Snapshot metadata
    calculated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)  # When this comparison becomes stale
    is_active = Column(Boolean, default=True, index=True)

    # Quality indicators
    confidence_score = Column(Numeric(3, 2), default=1.0)  # Based on source data quality
    update_frequency_seconds = Column(Integer, nullable=True)  # How often odds change

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    market = relationship("Market")
    best_back_selection = relationship("Selection", foreign_keys=[best_back_selection_id])
    best_lay_selection = relationship("Selection", foreign_keys=[best_lay_selection_id])
    best_back_bookmaker = relationship("Bookmaker", foreign_keys=[best_back_bookmaker_id])
    best_lay_bookmaker = relationship("Bookmaker", foreign_keys=[best_lay_bookmaker_id])

    # Indexes for matched betting queries
    __table_args__ = (
        Index("idx_comparison_market_active", "market_id", "is_active"),
        Index("idx_comparison_arbitrage_active", "arbitrage_percentage", "is_active"),
        Index("idx_comparison_expires", "expires_at"),
        Index("idx_comparison_calculated", "calculated_at"),
    )


BOOKMAKER_LIVE_RUNTIME_STATES = {"canary_active", "active", "degraded"}
BOOKMAKER_VALID_LIFECYCLE_STATES = {
    "backlog",
    "discovery_complete",
    "adapter_ready",
    "config_ready",
    "validation_passed",
    "canary_active",
    "active",
    "degraded",
    "disabled",
}


def _normalize_lifecycle_state(value: Optional[str]) -> str:
    return (value or "").strip().lower()


@event.listens_for(Bookmaker, "before_insert")
@event.listens_for(Bookmaker, "before_update")
def _sync_bookmaker_lifecycle_fields(_mapper, _connection, target: Bookmaker) -> None:
    """
    Keep lifecycle state and runtime active flag aligned.

    This prevents unsafe runtime promotion via raw `is_active` flips without a
    valid lifecycle transition.
    """
    now = datetime.now(timezone.utc)
    state = _normalize_lifecycle_state(target.lifecycle_state)
    if state not in BOOKMAKER_VALID_LIFECYCLE_STATES:
        state = "active" if bool(target.is_active) else "backlog"
    target.lifecycle_state = state

    if target.lifecycle_state_updated_at is None:
        target.lifecycle_state_updated_at = now

    if state in BOOKMAKER_LIVE_RUNTIME_STATES and not is_bookmaker_frozen(target.code):
        target.is_active = True
    else:
        target.is_active = False
