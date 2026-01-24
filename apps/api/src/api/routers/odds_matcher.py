# apps/api/src/api/routers/odds_matcher.py
"""
Odds matcher endpoints for finding matched betting opportunities.
Supports filtering by stake, bet type, bookmakers, leagues, and search.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from email.utils import format_datetime, parsedate_to_datetime

from api.core.database import get_db
from api.core.auth import get_current_user, UserClaims
from api.models import User, Event, Market, Selection, OddsSnapshot, Bookmaker, Competition, Sport
from api.services.matching_engine import MatchingEngine, BetType, BackBet, LayBet
from api.services.subscription_service import SubscriptionService
from api.services.normalization_service import (
    normalize_event_name,
    normalize_competition_name,
    normalize_selection_name,
    get_competition_display_name,
)


router = APIRouter(prefix="/odds", tags=["odds-matcher"])


class OddsMatcherFilters(BaseModel):
    """Filters for odds matcher"""
    stake: Decimal = Field(default=Decimal("100"), ge=Decimal("1"), le=Decimal("10000"))
    bet_type: BetType = Field(default=BetType.NORMAL)
    bookmaker_codes: Optional[List[str]] = None  # Filter by specific bookmakers
    sport_codes: Optional[List[str]] = None  # Filter by sports
    competition_codes: Optional[List[str]] = None  # Filter by normalized competition codes
    competition_ids: Optional[List[int]] = None  # Filter by competitions
    search: Optional[str] = None  # Search event names
    min_rating: Optional[Decimal] = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(default=200, ge=1, le=500)


class OddsMatchResponse(BaseModel):
    """Single matched betting opportunity"""
    event_id: int
    event_name: str
    event_start_time: datetime
    sport_name: str
    competition_name: str

    market_id: int
    market_name: str
    market_type: str

    selection_id: int
    selection_name: str

    # Back bet details
    back_bookmaker_code: str
    back_bookmaker_name: str
    back_odds: float
    back_stake: float

    # Lay bet details (Betfair)
    lay_odds: float
    lay_stake: float
    lay_liability: float
    lay_commission: float
    lay_liquidity: Optional[float]

    # Outcomes
    profit_if_back_wins: float
    profit_if_lay_wins: float
    qualifying_loss: float
    pnl_percentage: float

    # Metadata
    bet_type: BetType
    rating: float
    last_updated: datetime


class PaginatedOddsResponse(BaseModel):
    """Paginated response for odds matcher with infinite scroll support"""
    items: List[OddsMatchResponse]
    total: int
    offset: int
    limit: int
    has_more: bool


class RefreshOddsRequest(BaseModel):
    """Request to manually refresh odds"""
    force: bool = Field(default=False, description="Force refresh even if recently updated")


class RefreshOddsResponse(BaseModel):
    """Response from odds refresh"""
    success: bool
    message: str
    opportunities_count: int
    last_refresh: datetime
    job_id: Optional[str] = Field(default=None, description="Queued job id if a refresh was enqueued")
    used_cache: bool = Field(default=False, description="Whether cached data was used")


class RefreshJobStatusResponse(BaseModel):
    """Status payload for a queued refresh job"""
    job_id: str
    status: str
    enqueued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    message: Optional[str] = None
    errors: Optional[List[str]] = None
    result: Optional[dict] = None


@router.post("/refresh")
async def refresh_odds(
    request: RefreshOddsRequest,
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> RefreshOddsResponse:
    """
    Manually trigger odds refresh.

    Implements:
    - Global cache (5 min TTL) - all users share same scraped data
    - Per-user rate limiting (max 1 refresh per 30 seconds)
    - Scrapes TAB for latest EPL odds on cache miss
    """
    import redis
    import os
    import logging
    logger = logging.getLogger(__name__)
    logger.info("=== REFRESH ODDS ENDPOINT CALLED ===")
    logger.info(f"User: {user_claims.sub}")

    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    job_queue_key = os.getenv("ODDS_REFRESH_QUEUE_KEY", "odds_refresh_jobs")
    job_prefix = os.getenv("ODDS_REFRESH_JOB_PREFIX", "odds_refresh_job:")
    fast_ttl_seconds = int(os.getenv("ODDS_CACHE_TTL_FAST_SECONDS", "300"))
    slow_ttl_seconds = int(os.getenv("ODDS_CACHE_TTL_SLOW_SECONDS", "300"))
    max_queue_length = int(os.getenv("ODDS_REFRESH_MAX_QUEUE_LENGTH", "50"))
    merge_if_pending = os.getenv("ODDS_REFRESH_MERGE_IF_PENDING", "1") == "1"
    per_user_refresh_seconds = int(os.getenv("ODDS_REFRESH_PER_USER_SECONDS", "30"))

    # Get or create user (auto-create on first access)
    logger.info(f"Looking up user with clerk_user_id: {user_claims.sub}")
    user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()

    if not user:
        logger.info(f"User not found, creating new user: {user_claims.sub}")
        user = User(
            clerk_user_id=user_claims.sub,
            email=user_claims.email or f"{user_claims.sub}@temp.com",
            email_verified=user_claims.email_verified or False,
            current_plan="free",
            plan_status="active"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created new user with id: {user.id}")
    else:
        logger.info(f"User found: {user.id}")

    # Per-user rate limit independent of cache (now that user is defined)
    user_rate_key = f"odds_refresh_rl:{user.id}"
    if redis_client.exists(user_rate_key):
        raise HTTPException(status_code=429, detail="Too many refreshes, try again soon")
    redis_client.setex(user_rate_key, per_user_refresh_seconds, "1")

    # Check plan entitlements
    subscription_service = SubscriptionService()
    can_access, message = subscription_service.can_user_access_feature(
        db, user.id, "odds_matcher"
    )

    if not can_access:
        raise HTTPException(status_code=403, detail=message)

    # Global cache key (shared by all users)
    global_cache_key = "odds_last_refresh_global"

    # Check global cache first (unless force refresh)
    # Cache provides natural rate limiting - no need for explicit limits
    cached_time = redis_client.get(global_cache_key)
    if cached_time and not request.force:
        last_refresh = datetime.fromisoformat(cached_time.decode())
        age_seconds = (datetime.now(timezone.utc) - last_refresh).total_seconds()

        if age_seconds < fast_ttl_seconds:
            # Use cached data - count current odds
            opportunities_count = db.query(OddsSnapshot).filter(
                OddsSnapshot.is_current == True
            ).count()

            return RefreshOddsResponse(
                success=True,
                message=f"Using cached odds (updated {int(age_seconds)}s ago)",
                opportunities_count=opportunities_count,
                last_refresh=last_refresh,
                used_cache=True
            )

    # Enqueue refresh job instead of blocking the request
    from api.services.refresh_queue import enqueue_refresh_job

    payload = {
        "requested_by": user.id,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "sports": "all",
        "bookmakers": None,
        "force": request.force,
    }

    enqueue_result = enqueue_refresh_job(
        redis_client,
        payload,
        queue_key=job_queue_key,
        job_prefix=job_prefix,
        ttl_seconds=900,
        max_queue_length=max_queue_length,
        merge_if_pending=merge_if_pending,
    )
    job_id = enqueue_result["job_id"]

    # Mark cache intent to prevent stampede; worker will set actual refresh time
    # CRITICAL FIX: TTL must cover the entire scrape duration (~79s)
    # If we only set fast_ttl_seconds (60s), the cache expires while worker is still running,
    # causing stale data window: cache expires at T=60s but worker finishes at T=79s
    now = datetime.now(timezone.utc)
    # Use slow_ttl (300s) to ensure cache doesn't expire while worker is scraping
    redis_client.setex(global_cache_key, slow_ttl_seconds, now.isoformat())

    opportunities_count = db.query(OddsSnapshot).filter(
        OddsSnapshot.is_current == True
    ).count()

    if enqueue_result.get("merged"):
        return RefreshOddsResponse(
            success=True,
            message="Refresh already queued; merged request",
            opportunities_count=opportunities_count,
            last_refresh=now,
            # CRITICAL: used_cache=False so frontend polls for job completion
            # Even though request was merged, a scrape is still running!
            used_cache=False,
            job_id=job_id,
        )

    return RefreshOddsResponse(
        success=True,
        message=f"Refresh job queued (job_id={job_id}); returning current cached odds",
        opportunities_count=opportunities_count,
        last_refresh=now,
        # CRITICAL: used_cache=False when job is enqueued
        # Frontend must poll job status until scrape completes
        # Previously used bool(cached_time) which was True if expired cache existed
        used_cache=False,
        job_id=job_id,
    )


@router.get("/refresh/status")
async def refresh_status(
    job_id: str,
    user_claims: UserClaims = Depends(get_current_user),
):
    """
    Get status for a queued refresh job.
    """
    import redis
    import os

    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    job_prefix = os.getenv("ODDS_REFRESH_JOB_PREFIX", "odds_refresh_job:")

    from api.services.refresh_queue import get_job_status

    status = get_job_status(redis_client, job_id, job_prefix=job_prefix)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    def parse_dt(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None

    return RefreshJobStatusResponse(
        job_id=job_id,
        status=status.get("status", "unknown"),
        enqueued_at=parse_dt(status.get("enqueued_at")),
        started_at=parse_dt(status.get("started_at")),
        completed_at=parse_dt(status.get("completed_at")),
        message=status.get("message"),
        errors=status.get("errors"),
        result=status.get("result"),
    )


@router.get("/matcher", response_model=PaginatedOddsResponse)
async def get_matcher_opportunities(
    request: Request,
    response: Response,
    stake: Decimal = Query(default=Decimal("100"), ge=Decimal("1"), le=Decimal("10000")),
    bet_type: BetType = Query(default=BetType.NORMAL),
    bookmaker_codes: Optional[str] = Query(default=None, description="Comma-separated bookmaker codes"),
    sport_codes: Optional[str] = Query(default=None, description="Comma-separated sport codes"),
    competition_codes: Optional[str] = Query(default=None, description="Comma-separated competition codes"),
    competition_ids: Optional[str] = Query(default=None, description="Comma-separated competition IDs"),
    search: Optional[str] = Query(default=None, description="Search event names"),
    min_rating: Optional[Decimal] = Query(default=None, ge=Decimal("0"), le=Decimal("100")),
    limit: int = Query(default=30, ge=1, le=100, description="Number of items per page"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> PaginatedOddsResponse:
    """
    Get matched betting opportunities with filtering and pagination.

    Supports infinite scroll with offset-based pagination:
    - First request: offset=0, limit=30
    - Next page: offset=30, limit=30
    - And so on...

    Filters available odds to show only best opportunities based on:
    - User's plan (free tier = 2 bookmakers: Ladbrokes + Neds, plus Betfair exchange)
    - Stake amount
    - Bet type (normal vs bonus)
    - Sport, competition, search terms
    - Minimum rating threshold
    """
    import logging
    import time
    total_start = time.time()
    logger = logging.getLogger(__name__)

    print("\n" + "="*80)
    print("=== MATCHER ENDPOINT CALLED ===")
    print(f"Parameters: stake={stake}, bet_type={bet_type}, bookmaker_codes={bookmaker_codes}")
    print("="*80 + "\n")

    logger.info("=== MATCHER ENDPOINT CALLED ===")
    logger.info(f"Parameters: stake={stake}, bet_type={bet_type}, bookmaker_codes={bookmaker_codes}")

    # Get or create user (auto-create on first access)
    user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()
    if not user:
        user = User(
            clerk_user_id=user_claims.sub,
            email=user_claims.email or f"{user_claims.sub}@temp.com",
            email_verified=user_claims.email_verified or False,
            current_plan="free",
            plan_status="active"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    subscription_service = SubscriptionService()
    can_access, message = subscription_service.can_user_access_feature(
        db, user.id, "odds_matcher"
    )

    if not can_access:
        raise HTTPException(status_code=403, detail=message)

    # Get user's allowed bookmakers based on plan
    allowed_bookmakers = subscription_service.get_allowed_bookmakers(db, user)

    # Parse comma-separated filters
    bookmaker_filter = bookmaker_codes.split(",") if bookmaker_codes else None
    sport_filter = sport_codes.split(",") if sport_codes else None
    competition_code_filter = competition_codes.split(",") if competition_codes else None
    competition_filter = [int(x) for x in competition_ids.split(",")] if competition_ids else None

    # Apply plan restrictions: filter to only allowed bookmakers
    print(f"allowed_bookmakers: {allowed_bookmakers}")
    print(f"bookmaker_filter (before): {bookmaker_filter}")

    if bookmaker_filter:
        # User requested specific bookmakers - ensure they're allowed
        bookmaker_filter = [bm for bm in bookmaker_filter if bm in allowed_bookmakers]
    else:
        # No filter specified - use all allowed bookmakers
        bookmaker_filter = allowed_bookmakers

    print(f"bookmaker_filter (after): {bookmaker_filter}")

    if not bookmaker_filter:
        raise HTTPException(
            status_code=403,
            detail="Your plan does not allow access to the requested bookmakers"
        )

    # Build query for current odds
    # We need: Event -> Market -> Selection -> OddsSnapshot
    # Find events happening in next 14 days
    now = datetime.now(timezone.utc)
    date_from = now
    date_to = now + timedelta(days=14)

    # Query for events with filters
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"=== MATCHER QUERY DEBUG ===")
    logger.info(f"Date range: {date_from} to {date_to}")
    logger.info(f"Sport filter: {sport_filter}")
    logger.info(f"Competition filter: {competition_filter}")
    logger.info(f"Competition codes: {competition_code_filter}")
    logger.info(f"Search filter: {search}")

    events_query = db.query(Event).join(Competition).join(Sport)

    # Apply date filter
    events_query = events_query.filter(
        and_(
            Event.start_time >= date_from,
            Event.start_time <= date_to,
            Event.status == "scheduled"
        )
    )

    # Apply sport filter
    if sport_filter:
        events_query = events_query.filter(Sport.code.in_(sport_filter))

    # Apply competition filter
    if competition_filter:
        events_query = events_query.filter(Event.competition_id.in_(competition_filter))

    # Apply search filter
    if search:
        events_query = events_query.filter(Event.name.ilike(f"%{search}%"))

    logger.info("About to execute query...")
    query_start = time.time()
    # Fetch all events - we need to group duplicates across bookmakers
    # 500 limit should cover all sports for next 14 days
    events = events_query.limit(500).all()
    query_time = time.time() - query_start
    logger.info(f"⏱️  [MATCHER] Events query took {query_time:.2f}s, found {len(events)} events")

    # Apply competition code filter using normalization (handles season prefixes/suffixes)
    if competition_code_filter:
        normalized_codes = {
            normalize_competition_name(code.strip())
            for code in competition_code_filter
            if code.strip()
        }
        if normalized_codes:
            filtered_events = []
            for event in events:
                comp_name = ""
                if event.competition:
                    comp_name = event.competition.name or event.competition.short_name or ""
                if normalize_competition_name(comp_name) in normalized_codes:
                    filtered_events.append(event)
            events = filtered_events
            logger.info(f"[MATCHER] Competition code filter applied: {len(events)} events match {normalized_codes}")

    print(f"\n>>> Found {len(events)} events in date range {date_from} to {date_to}")
    print(f">>> Bookmaker filter: {bookmaker_filter}\n")

    logger.info(f"Matcher query found {len(events)} events in date range {date_from} to {date_to}")
    logger.info(f"Bookmaker filter: {bookmaker_filter}")

    if not events:
        logger.warning("No events found - returning empty list")
        print(">>> No events found - returning empty list")
        return PaginatedOddsResponse(
            items=[],
            total=0,
            offset=offset,
            limit=limit,
            has_more=False
        )

    # Group events by normalized name to handle duplicate events from different bookmakers
    # Uses NormalizationService (Phase 4) for centralized team/event mappings
    print(f"\n>>> Grouping {len(events)} events by normalized name...")

    event_groups = {}
    for event in events:
        norm_event_name = normalize_event_name(event.name)
        # Also normalize competition to handle "Premier League" vs "English Premier League"
        norm_comp = normalize_competition_name(event.competition.name if event.competition else "")
        # Create composite key: normalized_event_name + normalized_competition
        # This ensures events from same match but different bookmaker competition names are grouped
        group_key = f"{norm_event_name}_{norm_comp}"

        if group_key not in event_groups:
            event_groups[group_key] = []
        event_groups[group_key].append(event)

    print(f">>> Found {len(event_groups)} unique events (from {len(events)} total events)")

    # For each event group, find matched betting opportunities
    matching_engine = MatchingEngine()
    opportunities = []

    matching_start = time.time()
    print(f"\n>>> Processing {len(event_groups)} unique events to find opportunities...")
    for norm_event_name, events_in_group in event_groups.items():
        # Use the first event for metadata
        representative_event = events_in_group[0]
        event_ids = [e.id for e in events_in_group]
        event_names = [e.name for e in events_in_group]

        print(f">>> Event group '{norm_event_name}' (original names: {event_names})")
        logger.info(f"Processing event group: {event_names} (IDs: {event_ids})")

        # Get markets for ALL events in this group (only H2H/Match Result markets - exclude combined markets)
        markets = db.query(Market).filter(
            and_(
                Market.event_id.in_(event_ids),
                Market.is_active == True,
                or_(
                    # Match "Result" but exclude HTResult, H2Result, and combined markets
                    and_(
                        Market.name.ilike('%result'),
                        Market.name.notilike('%htresult%'),  # Exclude half-time result
                        Market.name.notilike('%h2result%'),  # Exclude 2nd half result
                        Market.name.notilike('%both%'),      # Exclude Result-BothTmScr
                        Market.name.notilike('%rou%')        # Exclude Result-OU combined markets
                    ),
                    Market.name.ilike('%match winner%'),
                    Market.name.ilike('%match odds%'),  # Betfair calls it "Match Odds"
                    Market.name.ilike('%money%line%'),  # NBA/NHL use "Money Line" or "Moneyline"
                    Market.name.ilike('%head%to%head%'),  # Ladbrokes uses "Head To Head"
                    Market.name.ilike('%fight betting%'),  # Boxing uses "Fight Betting"
                    and_(Market.name.ilike('%h2h%'), Market.name.notilike('%hth2h%'))
                )
            )
        ).all()

        print(f"    Markets found across all events: {len(markets)}")
        logger.info(f"  Found {len(markets)} markets across event group {event_names}")

        # PHASE 1: Collect ALL selections across ALL markets in this event group
        # Then group them by normalized team name
        all_selections = []
        for market in markets:
            selections = db.query(Selection).filter(Selection.market_id == market.id).all()
            all_selections.extend(selections)

        # Group selections by normalized name (using NormalizationService)
        selection_groups = {}

        # PHASE 2: Group selections by normalized name
        for selection in all_selections:
            norm_name = normalize_selection_name(selection.name)

            if norm_name not in selection_groups:
                selection_groups[norm_name] = {
                    'selections': [],
                    'selection_ids': [],
                    'back_odds': [],
                    'lay_odds': []
                }

            selection_groups[norm_name]['selections'].append(selection)
            selection_groups[norm_name]['selection_ids'].append(selection.id)

        logger.info(f"  Grouped {len(all_selections)} selections into {len(selection_groups)} normalized groups")

        # PHASE 3: For each selection group, query odds for ALL selection IDs in the group
        # This is the key fix - we query across all selections with the same normalized name
        back_bookmakers = [bm for bm in bookmaker_filter if bm != "betfair"]

        for norm_name, group in selection_groups.items():
            selection_ids = group['selection_ids']

            # Get back odds for ALL selections in this group
            if back_bookmakers:
                back = db.query(OddsSnapshot).join(Bookmaker).filter(
                    and_(
                        OddsSnapshot.selection_id.in_(selection_ids),
                        OddsSnapshot.is_current == True,
                        Bookmaker.code.in_(back_bookmakers)
                    )
                ).all()
                group['back_odds'] = back

            # Get lay odds for ALL selections in this group
            lay = db.query(OddsSnapshot).join(Bookmaker).filter(
                and_(
                    OddsSnapshot.selection_id.in_(selection_ids),
                    OddsSnapshot.is_current == True,
                    Bookmaker.code == "betfair"
                )
            ).all()
            group['lay_odds'] = lay

        # Now check each selection group for matched opportunities
        # KEY CHANGE: Create one opportunity PER BOOKMAKER (like Outmatched)
        # This allows users to see and bet on the same event across multiple bookmakers
        for norm_name, group in selection_groups.items():
            back_odds_list = group['back_odds']
            # Filter out invalid lay odds (odds >= 100 are Betfair placeholders meaning no liquidity)
            lay_odds = [lo for lo in group['lay_odds'] if lo.decimal_odds < Decimal("100")]
            selection = group['selections'][0]  # Use first selection for metadata

            # Show all original names in this group
            all_names = [s.name for s in group['selections']]
            print(f"    Selection group '{norm_name}' (names: {all_names}): {len(back_odds_list)} back, {len(lay_odds)} lay (valid)")

            if not back_odds_list or not lay_odds:
                if not back_odds_list:
                    print(f"      SKIP: no back odds")
                if not lay_odds:
                    print(f"      SKIP: no valid lay odds (filtered out odds >= 100)")
                continue

            # Find best lay odds (lowest is best for laying) - same for all bookmakers
            best_lay = min(lay_odds, key=lambda x: x.decimal_odds)

            # Group back odds by bookmaker and find best odds per bookmaker
            # (in case same bookmaker has multiple odds entries for same selection)
            bookmaker_best_odds: dict[str, OddsSnapshot] = {}
            for back_odds in back_odds_list:
                bm_code = back_odds.bookmaker.code
                if bm_code not in bookmaker_best_odds:
                    bookmaker_best_odds[bm_code] = back_odds
                elif back_odds.decimal_odds > bookmaker_best_odds[bm_code].decimal_odds:
                    bookmaker_best_odds[bm_code] = back_odds

            print(f"      MATCHES FOUND! Creating {len(bookmaker_best_odds)} opportunities (one per bookmaker)")

            # Create one opportunity per bookmaker
            for bm_code, best_back in bookmaker_best_odds.items():
                # Calculate matched bet for this bookmaker
                back_bet = BackBet(
                    bookmaker_code=best_back.bookmaker.code,
                    bookmaker_name=best_back.bookmaker.display_name,
                    back_odds=best_back.decimal_odds,
                    stake=stake
                )

                lay_bet = LayBet(
                    lay_odds=best_lay.decimal_odds,
                    commission=Decimal("0.06"),  # 6% Betfair commission (Australian users)
                    liquidity=best_lay.available_amount
                )

                calculation = matching_engine.calculate_matched_bet(
                    back_bet, lay_bet, bet_type
                )

                # Apply rating filter
                if min_rating and calculation.rating < min_rating:
                    continue

                # Calculate PnL percentage
                pnl_pct = matching_engine.calculate_pnl_percentage(calculation)

                # Get market from first selection for metadata
                market = selection.market

                opportunities.append(OddsMatchResponse(
                    event_id=representative_event.id,
                    event_name=representative_event.name,
                    event_start_time=representative_event.start_time,
                    sport_name=representative_event.competition.sport.display_name,
                    competition_name=get_competition_display_name(representative_event.competition.name if representative_event.competition else ""),
                    market_id=market.id,
                    market_name=market.name,
                    market_type=market.market_type,
                    selection_id=selection.id,
                    selection_name=selection.name,
                    back_bookmaker_code=calculation.back_bet.bookmaker_code,
                    back_bookmaker_name=calculation.back_bet.bookmaker_name,
                    back_odds=float(calculation.back_bet.back_odds),
                    back_stake=float(calculation.back_stake),
                    lay_odds=float(calculation.lay_bet.lay_odds),
                    lay_stake=float(calculation.lay_stake),
                    lay_liability=float(calculation.lay_liability),
                    lay_commission=float(calculation.lay_bet.commission),
                    lay_liquidity=float(calculation.lay_bet.liquidity) if calculation.lay_bet.liquidity else None,
                    profit_if_back_wins=float(calculation.profit_if_back_wins),
                    profit_if_lay_wins=float(calculation.profit_if_lay_wins),
                    qualifying_loss=float(calculation.qualifying_loss),
                    pnl_percentage=float(pnl_pct),
                    bet_type=calculation.bet_type,
                    rating=float(calculation.rating),
                    last_updated=best_back.timestamp
                ))

    # Sort by PnL percentage (most profitable first: -1% is better than -5%)
    # For normal bets: higher PnL% = less loss = better (e.g., -1% > -5%)
    # For bonus bets: higher PnL% = more profit = better (e.g., 80% > 70%)
    matching_time = time.time() - matching_start
    logger.info(f"⏱️  [MATCHER] Matching logic took {matching_time:.2f}s")

    sort_start = time.time()
    opportunities.sort(key=lambda x: x.pnl_percentage, reverse=True)
    sort_time = time.time() - sort_start
    logger.info(f"⏱️  [MATCHER] Sorting took {sort_time:.2f}s")

    total_time = time.time() - total_start
    logger.info(f"⏱️  [MATCHER] TOTAL endpoint time: {total_time:.2f}s")

    print(f"\n{'='*80}")
    print(f"=== SUMMARY: Found {len(opportunities)} matched betting opportunities ===")
    print(f"=== TOTAL TIME: {total_time:.2f}s ===")
    print(f"{'='*80}\n")

    logger.info(f"=== MATCHER SUMMARY ===")
    total_count = len(opportunities)
    logger.info(f"Total opportunities found: {total_count}")
    logger.info(f"Returning items {offset} to {offset + limit} (offset={offset}, limit={limit})")

    # Apply pagination: slice from offset to offset+limit
    paginated_opps = opportunities[offset:offset + limit]
    has_more = (offset + limit) < total_count

    # Compute caching headers
    last_modified_dt = None
    if paginated_opps:
        last_modified_dt = max((opp.last_updated for opp in paginated_opps if opp.last_updated), default=None)

    if last_modified_dt:
        etag = f'W/"{int(last_modified_dt.timestamp())}-{total_count}-{offset}-{limit}"'
        response.headers["ETag"] = etag
        response.headers["Last-Modified"] = format_datetime(last_modified_dt)

        incoming_etag = request.headers.get("if-none-match")
        incoming_last_mod = request.headers.get("if-modified-since")

        if incoming_etag and incoming_etag == etag:
            response.status_code = 304
            return PaginatedOddsResponse(
                items=[],
                total=total_count,
                offset=offset,
                limit=limit,
                has_more=has_more
            )
        if incoming_last_mod:
            try:
                if_last_mod_dt = parsedate_to_datetime(incoming_last_mod)
                if last_modified_dt <= if_last_mod_dt:
                    response.status_code = 304
                    return PaginatedOddsResponse(
                        items=[],
                        total=total_count,
                        offset=offset,
                        limit=limit,
                        has_more=has_more
                    )
            except Exception:
                pass

    return PaginatedOddsResponse(
        items=paginated_opps,
        total=total_count,
        offset=offset,
        limit=limit,
        has_more=has_more
    )
