# apps/api/src/api/routers/odds_matcher.py
"""
Odds matcher endpoints for finding matched betting opportunities.
Supports filtering by stake, bet type, bookmakers, leagues, and search.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from collections import defaultdict
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
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
    fuzzy_match_score,
    get_competition_display_name,
)


router = APIRouter(prefix="/odds", tags=["odds-matcher"])

def _market_preference_rank(sport_code: str, market_name: str) -> int:
    """
    Rank markets by preference for matched-betting parity.

    For Punterstech/MintBet, basketball + ice_hockey expose both "Match Winner" and "Money Line".
    Outmatched uses the "Money Line" market for these sports, so prefer it when present.
    """
    sport = (sport_code or "").strip().lower()
    name = (market_name or "").strip().lower()

    if sport in ("basketball", "ice_hockey"):
        if "moneyline" in name or "money line" in name:
            return 0
        if "head to head" in name or "head-to-head" in name or "h2h" in name:
            return 1
        if "match odds" in name:
            return 1
        if "match winner" in name:
            return 2
        return 3

    if sport == "boxing":
        if "fight betting" in name:
            return 0
        if "fight result" in name:
            return 1
        return 2

    # Soccer and other sports: treat all match-winner markets as equivalent for now.
    return 0


def _parse_csv_filter(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    parts = [part.strip() for part in value.split(",")]
    filtered = [part for part in parts if part]
    return filtered or None


def _matcher_market_filter_clause():
    """SQL clause for match-winner compatible markets."""
    return or_(
        # Match "Result" but exclude HTResult, H2Result, and combined markets
        and_(
            Market.name.ilike("%result"),
            Market.name.notilike("%htresult%"),  # Exclude half-time result
            Market.name.notilike("%h2result%"),  # Exclude 2nd half result
            Market.name.notilike("%both%"),      # Exclude Result-BothTmScr
            Market.name.notilike("%rou%"),       # Exclude Result-OU combined markets
        ),
        Market.name.ilike("%match winner%"),
        Market.name.ilike("%match odds%"),       # Betfair
        Market.name.ilike("%money%line%"),       # NBA/NHL
        Market.name.ilike("%head%to%head%"),     # Ladbrokes
        Market.name.ilike("%fight betting%"),    # Boxing
        Market.name.ilike("%fight%result%"),     # Punterstech boxing
        and_(Market.name.ilike("%h2h%"), Market.name.notilike("%hth2h%")),
    )


def _group_events(events: List[Event]) -> Dict[str, List[Event]]:
    """Group event rows by normalized event+competition key."""
    event_groups: Dict[str, List[Event]] = defaultdict(list)
    for event in events:
        norm_event_name = normalize_event_name(event.name)
        norm_comp = normalize_competition_name(event.competition.name if event.competition else "")
        group_key = f"{norm_event_name}_{norm_comp}"
        event_groups[group_key].append(event)
    return dict(event_groups)


def _load_precomputed_matcher_data(
    db: Session,
    *,
    event_ids: List[int],
    bookmaker_filter: List[str],
) -> Dict[str, Any]:
    """
    Bulk preload markets, selections, and odds for the candidate event set.

    This replaces per-event/per-market query loops to avoid N+1 behavior.
    """
    if not event_ids:
        return {
            "markets_by_event_id": {},
            "selections_by_market_id": {},
            "selection_by_id": {},
            "odds_by_selection_id": {},
        }

    markets = (
        db.query(Market)
        .filter(
            and_(
                Market.event_id.in_(event_ids),
                Market.is_active == True,
                _matcher_market_filter_clause(),
            )
        )
        .all()
    )
    market_ids = [market.id for market in markets]
    markets_by_event_id: Dict[int, List[Market]] = defaultdict(list)
    for market in markets:
        markets_by_event_id[market.event_id].append(market)

    if not market_ids:
        return {
            "markets_by_event_id": dict(markets_by_event_id),
            "selections_by_market_id": {},
            "selection_by_id": {},
            "odds_by_selection_id": {},
        }

    selections = (
        db.query(Selection)
        .options(joinedload(Selection.market))
        .filter(Selection.market_id.in_(market_ids))
        .all()
    )
    selection_ids = [selection.id for selection in selections]
    selections_by_market_id: Dict[int, List[Selection]] = defaultdict(list)
    selection_by_id: Dict[int, Selection] = {}
    for selection in selections:
        selections_by_market_id[selection.market_id].append(selection)
        selection_by_id[selection.id] = selection

    if not selection_ids:
        return {
            "markets_by_event_id": dict(markets_by_event_id),
            "selections_by_market_id": dict(selections_by_market_id),
            "selection_by_id": selection_by_id,
            "odds_by_selection_id": {},
        }

    bookmaker_codes = sorted(set((bookmaker_filter or []) + ["betfair"]))
    odds_rows = (
        db.query(OddsSnapshot)
        .join(Bookmaker)
        .options(joinedload(OddsSnapshot.bookmaker))
        .filter(
            and_(
                OddsSnapshot.selection_id.in_(selection_ids),
                OddsSnapshot.is_current == True,
                Bookmaker.code.in_(bookmaker_codes),
            )
        )
        .all()
    )
    odds_by_selection_id: Dict[int, List[OddsSnapshot]] = defaultdict(list)
    for odds_row in odds_rows:
        odds_by_selection_id[odds_row.selection_id].append(odds_row)

    return {
        "markets_by_event_id": dict(markets_by_event_id),
        "selections_by_market_id": dict(selections_by_market_id),
        "selection_by_id": selection_by_id,
        "odds_by_selection_id": dict(odds_by_selection_id),
    }


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
    in_progress_key = os.getenv("ODDS_REFRESH_IN_PROGRESS_KEY", "odds_refresh_in_progress_job_id")
    fast_ttl_seconds = int(os.getenv("ODDS_CACHE_TTL_FAST_SECONDS", "300"))
    slow_ttl_seconds = int(os.getenv("ODDS_CACHE_TTL_SLOW_SECONDS", "300"))
    job_ttl_seconds = int(os.getenv("ODDS_REFRESH_JOB_TTL_SECONDS", "900"))
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

    # Check plan entitlements
    subscription_service = SubscriptionService()
    can_access, message = subscription_service.can_user_access_feature(
        db, user.id, "odds_matcher"
    )

    if not can_access:
        raise HTTPException(status_code=403, detail=message)

    # If a refresh is already queued/running, return the existing job_id so the
    # frontend can show "Fetching latest odds..." instead of "No opportunities found".
    existing_job_id = redis_client.get(in_progress_key)
    if existing_job_id:
        job_id = existing_job_id.decode()
        # If the job pointer is stale, clear it and continue.
        if redis_client.get(f"{job_prefix}{job_id}"):
            opportunities_count = db.query(OddsSnapshot).filter(
                OddsSnapshot.is_current == True
            ).count()
            return RefreshOddsResponse(
                success=True,
                message="Refresh already in progress; returning current cached odds",
                opportunities_count=opportunities_count,
                last_refresh=datetime.now(timezone.utc),
                used_cache=False,
                job_id=job_id,
            )
        redis_client.delete(in_progress_key)

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

            # If the cache key exists but we have no current odds snapshots, treat
            # this as a cache miss (e.g. first run or after cleanup).
            if opportunities_count == 0:
                logger.info("Cache timestamp present but no current odds; treating as cache miss")
            else:
                return RefreshOddsResponse(
                    success=True,
                    message=f"Using cached odds (updated {int(age_seconds)}s ago)",
                    opportunities_count=opportunities_count,
                    last_refresh=last_refresh,
                    used_cache=True
                )

    # Per-user rate limit only when we're about to enqueue a new refresh job.
    user_rate_key = f"odds_refresh_rl:{user.id}"
    if redis_client.exists(user_rate_key):
        raise HTTPException(status_code=429, detail="Too many refreshes, try again soon")
    redis_client.setex(user_rate_key, per_user_refresh_seconds, "1")

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
        ttl_seconds=job_ttl_seconds,
        max_queue_length=max_queue_length,
        merge_if_pending=merge_if_pending,
    )
    job_id = enqueue_result["job_id"]

    # Store the "refresh in progress" job_id so other users can poll the same job
    # instead of triggering additional scrapes.
    redis_client.setex(in_progress_key, job_ttl_seconds, job_id)

    now = datetime.now(timezone.utc)

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

    # Get or create user (auto-create on first access)
    user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()
    if not user:
        user = User(
            clerk_user_id=user_claims.sub,
            email=user_claims.email or f"{user_claims.sub}@temp.com",
            email_verified=user_claims.email_verified or False,
            current_plan="free",
            plan_status="active",
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
    bookmaker_filter = _parse_csv_filter(bookmaker_codes)
    sport_filter = _parse_csv_filter(sport_codes)
    competition_code_filter = _parse_csv_filter(competition_codes)
    competition_filter = [int(x) for x in competition_ids.split(",") if x.strip()] if competition_ids else None

    # Apply plan restrictions: filter to only allowed bookmakers
    if bookmaker_filter:
        bookmaker_filter = [bm for bm in bookmaker_filter if bm in allowed_bookmakers]
    else:
        bookmaker_filter = allowed_bookmakers

    if not bookmaker_filter:
        raise HTTPException(
            status_code=403,
            detail="Your plan does not allow access to the requested bookmakers",
        )

    # Find events happening in next 14 days
    now = datetime.now(timezone.utc)
    date_from = now
    date_to = now + timedelta(days=14)

    # Query for events with filters and eager-load metadata used in response payload.
    events_query = (
        db.query(Event)
        .options(joinedload(Event.competition).joinedload(Competition.sport))
        .join(Competition)
        .join(Sport)
        .filter(
            and_(
                Event.start_time >= date_from,
                Event.start_time <= date_to,
                Event.status == "scheduled",
            )
        )
    )

    if sport_filter:
        events_query = events_query.filter(Sport.code.in_(sport_filter))

    if competition_filter:
        events_query = events_query.filter(Event.competition_id.in_(competition_filter))

    if search:
        events_query = events_query.filter(Event.name.ilike(f"%{search}%"))

    query_start = time.time()
    events = events_query.limit(500).all()
    query_time = time.time() - query_start
    logger.info(f"[MATCHER] Events query took {query_time:.2f}s, found {len(events)} events")

    # Apply competition code filter using normalization (handles season prefixes/suffixes)
    if competition_code_filter:
        normalized_codes = {
            normalize_competition_name(code)
            for code in competition_code_filter
            if code
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

    if not events:
        return PaginatedOddsResponse(
            items=[],
            total=0,
            offset=offset,
            limit=limit,
            has_more=False,
        )

    event_groups = _group_events(events)
    preloaded = _load_precomputed_matcher_data(
        db,
        event_ids=[event.id for event in events],
        bookmaker_filter=bookmaker_filter,
    )

    markets_by_event_id: Dict[int, List[Market]] = preloaded["markets_by_event_id"]
    selections_by_market_id: Dict[int, List[Selection]] = preloaded["selections_by_market_id"]
    odds_by_selection_id: Dict[int, List[OddsSnapshot]] = preloaded["odds_by_selection_id"]

    matching_engine = MatchingEngine()
    opportunities: List[OddsMatchResponse] = []
    back_bookmakers = [bm for bm in bookmaker_filter if bm != "betfair"]

    matching_start = time.time()

    for events_in_group in event_groups.values():
        representative_event = events_in_group[0]
        sport_code = (
            representative_event.competition.sport.code
            if representative_event.competition and representative_event.competition.sport
            else ""
        )

        group_markets: List[Market] = []
        for event in events_in_group:
            group_markets.extend(markets_by_event_id.get(event.id, []))

        if not group_markets:
            continue

        all_selections: List[Selection] = []
        for market in group_markets:
            all_selections.extend(selections_by_market_id.get(market.id, []))

        if not all_selections:
            continue

        selection_groups: Dict[str, Dict[str, Any]] = {}
        for selection in all_selections:
            # Prefer selection_key (home/away/draw) for match-winner markets.
            selection_group_key = (selection.selection_key or "").strip().lower()
            if not selection_group_key:
                selection_group_key = normalize_selection_name(selection.name)
            if not selection_group_key:
                selection_group_key = (selection.name or "").lower().strip()

            if selection_group_key not in selection_groups:
                selection_groups[selection_group_key] = {
                    "selections": [],
                    "selection_ids": [],
                }

            selection_groups[selection_group_key]["selections"].append(selection)
            selection_groups[selection_group_key]["selection_ids"].append(selection.id)

        for group in selection_groups.values():
            selection_ids = group["selection_ids"]
            selection_by_id = {s.id: s for s in group.get("selections", [])}

            group_odds: List[OddsSnapshot] = []
            for selection_id in selection_ids:
                group_odds.extend(odds_by_selection_id.get(selection_id, []))

            if back_bookmakers:
                back_odds_list = [
                    odds_row
                    for odds_row in group_odds
                    if odds_row.bookmaker and odds_row.bookmaker.code in back_bookmakers
                ]
            else:
                back_odds_list = []

            # Filter out invalid lay odds (odds >= 100 are placeholders meaning no liquidity)
            lay_odds = [
                odds_row
                for odds_row in group_odds
                if odds_row.bookmaker
                and odds_row.bookmaker.code == "betfair"
                and odds_row.decimal_odds < Decimal("100")
            ]

            if not back_odds_list or not lay_odds:
                continue

            selection = group["selections"][0]

            def market_rank_for_snapshot(snapshot: OddsSnapshot) -> int:
                sel = selection_by_id.get(snapshot.selection_id)
                market_name = sel.market.name if sel and sel.market else ""
                return _market_preference_rank(sport_code, market_name)

            # Find best lay odds per rank so back+lay markets stay aligned.
            lay_by_rank: Dict[int, List[OddsSnapshot]] = defaultdict(list)
            for lay_row in lay_odds:
                rank = market_rank_for_snapshot(lay_row)
                lay_by_rank[rank].append(lay_row)

            best_lay_by_rank: Dict[int, OddsSnapshot] = {}
            for rank, items in lay_by_rank.items():
                best_lay_by_rank[rank] = min(items, key=lambda x: x.decimal_odds)

            # Pick best back odds per bookmaker with market preference.
            bookmaker_best_odds: Dict[str, OddsSnapshot] = {}
            for back_odds in back_odds_list:
                bookmaker = back_odds.bookmaker
                if not bookmaker:
                    continue

                bm_code = bookmaker.code
                existing = bookmaker_best_odds.get(bm_code)
                if not existing:
                    bookmaker_best_odds[bm_code] = back_odds
                    continue

                existing_rank = market_rank_for_snapshot(existing)
                candidate_rank = market_rank_for_snapshot(back_odds)
                if candidate_rank < existing_rank:
                    bookmaker_best_odds[bm_code] = back_odds
                elif candidate_rank == existing_rank and back_odds.decimal_odds > existing.decimal_odds:
                    bookmaker_best_odds[bm_code] = back_odds

            for best_back in bookmaker_best_odds.values():
                back_rank = market_rank_for_snapshot(best_back)
                best_lay = best_lay_by_rank.get(back_rank)
                if not best_lay:
                    continue

                back_selection = selection_by_id.get(best_back.selection_id, selection)
                lay_selection = selection_by_id.get(best_lay.selection_id)

                # Safety: avoid mismatched back/lay selection pairs.
                if lay_selection and back_selection:
                    back_key = (back_selection.selection_key or "").strip().lower()
                    lay_key = (lay_selection.selection_key or "").strip().lower()
                    if not (back_key and lay_key and back_key == lay_key):
                        score = fuzzy_match_score(back_selection.name, lay_selection.name)
                        if score < 0.75:
                            continue

                back_bet = BackBet(
                    bookmaker_code=best_back.bookmaker.code,
                    bookmaker_name=best_back.bookmaker.display_name,
                    back_odds=best_back.decimal_odds,
                    stake=stake,
                )
                lay_bet = LayBet(
                    lay_odds=best_lay.decimal_odds,
                    commission=Decimal("0.06"),
                    liquidity=best_lay.available_amount,
                )

                calculation = matching_engine.calculate_matched_bet(back_bet, lay_bet, bet_type)
                if min_rating and calculation.rating < min_rating:
                    continue

                pnl_pct = matching_engine.calculate_pnl_percentage(calculation)
                market = back_selection.market if back_selection else selection.market
                response_selection = back_selection if back_selection else selection

                opportunities.append(
                    OddsMatchResponse(
                        event_id=representative_event.id,
                        event_name=representative_event.name,
                        event_start_time=representative_event.start_time,
                        sport_name=(
                            representative_event.competition.sport.display_name
                            if representative_event.competition and representative_event.competition.sport
                            else ""
                        ),
                        competition_name=get_competition_display_name(
                            representative_event.competition.name if representative_event.competition else ""
                        ),
                        market_id=market.id,
                        market_name=market.name,
                        market_type=market.market_type,
                        selection_id=response_selection.id,
                        selection_name=response_selection.name,
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
                        last_updated=best_back.timestamp,
                    )
                )

    matching_time = time.time() - matching_start
    logger.info(f"[MATCHER] Matching logic took {matching_time:.2f}s")

    sort_start = time.time()
    opportunities.sort(key=lambda x: x.pnl_percentage, reverse=True)
    sort_time = time.time() - sort_start
    logger.info(f"[MATCHER] Sorting took {sort_time:.2f}s")

    total_time = time.time() - total_start
    logger.info(f"[MATCHER] Total endpoint time: {total_time:.2f}s")

    total_count = len(opportunities)
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
                has_more=has_more,
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
                        has_more=has_more,
                    )
            except Exception:
                pass

    return PaginatedOddsResponse(
        items=paginated_opps,
        total=total_count,
        offset=offset,
        limit=limit,
        has_more=has_more,
    )
