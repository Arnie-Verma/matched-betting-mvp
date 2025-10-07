# apps/api/src/api/routers/odds_matcher.py
"""
Odds matcher endpoints for finding matched betting opportunities.
Supports filtering by stake, bet type, bookmakers, leagues, and search.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from api.core.database import get_db
from api.core.auth import get_current_user, UserClaims
from api.models import User, Event, Market, Selection, OddsSnapshot, Bookmaker, Competition, Sport
from api.services.matching_engine import MatchingEngine, BetType, BackBet, LayBet
from api.services.subscription_service import SubscriptionService


router = APIRouter(prefix="/odds", tags=["odds-matcher"])


class OddsMatcherFilters(BaseModel):
    """Filters for odds matcher"""
    stake: Decimal = Field(default=Decimal("100"), ge=Decimal("1"), le=Decimal("10000"))
    bet_type: BetType = Field(default=BetType.NORMAL)
    bookmaker_codes: Optional[List[str]] = None  # Filter by specific bookmakers
    sport_codes: Optional[List[str]] = None  # Filter by sports
    competition_ids: Optional[List[int]] = None  # Filter by competitions
    search: Optional[str] = None  # Search event names
    min_rating: Optional[Decimal] = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=200)


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


class RefreshOddsRequest(BaseModel):
    """Request to manually refresh odds"""
    force: bool = Field(default=False, description="Force refresh even if recently updated")


class RefreshOddsResponse(BaseModel):
    """Response from odds refresh"""
    success: bool
    message: str
    opportunities_count: int
    last_refresh: datetime


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

    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    # Check user exists and has access
    user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check plan entitlements
    subscription_service = SubscriptionService()
    can_access, message = subscription_service.can_user_access_feature(
        db, user.id, "odds_matcher"
    )

    if not can_access:
        raise HTTPException(status_code=403, detail=message)

    # Global cache key (shared by all users)
    global_cache_key = "odds_last_refresh_global"

    # Per-user rate limit key
    user_rate_limit_key = f"odds_refresh_ratelimit:{user.id}"

    # Check per-user rate limit (30 seconds between refreshes)
    if redis_client.exists(user_rate_limit_key):
        raise HTTPException(
            status_code=429,
            detail="Please wait 30 seconds between refresh requests"
        )

    # Check global cache first (unless force refresh)
    if not request.force:
        cached_time = redis_client.get(global_cache_key)
        if cached_time:
            last_refresh = datetime.fromisoformat(cached_time.decode())
            age_seconds = (datetime.now(timezone.utc) - last_refresh).total_seconds()

            if age_seconds < 300:  # 5 minutes global cache
                # Use cached data - count current odds
                opportunities_count = db.query(OddsSnapshot).filter(
                    OddsSnapshot.is_current == True
                ).count()

                return RefreshOddsResponse(
                    success=True,
                    message=f"Using cached odds (updated {int(age_seconds)}s ago)",
                    opportunities_count=opportunities_count,
                    last_refresh=last_refresh
                )

    # Set user rate limit (30 seconds)
    redis_client.setex(user_rate_limit_key, 30, "1")

    # Trigger scraping (only if cache expired)
    import sys
    sys.path.insert(0, "apps/worker/src")

    from jobs.scrape_service import trigger_scrape

    try:
        # Scrape TAB for EPL (limit to 10 events for faster response)
        import logging
        logging.info(f"User {user.id} triggered odds refresh")

        scrape_result = await trigger_scrape(sport="soccer", limit=10)

        # Update global cache
        now = datetime.now(timezone.utc)
        redis_client.setex(global_cache_key, 300, now.isoformat())  # 5 min TTL

        # Count opportunities
        opportunities_count = scrape_result.get("odds_saved", 0)

        return RefreshOddsResponse(
            success=scrape_result.get("success", False),
            message=f"Refreshed {scrape_result.get('bookmakers_scraped', 0)} bookmakers - {scrape_result.get('odds_saved', 0)} odds updated",
            opportunities_count=opportunities_count,
            last_refresh=now
        )

    except Exception as e:
        import logging
        logging.error(f"Scrape failed: {e}")

        # Still respect rate limit even on failure to prevent abuse
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")


@router.get("/matcher")
async def get_matcher_opportunities(
    stake: Decimal = Query(default=Decimal("100"), ge=Decimal("1"), le=Decimal("10000")),
    bet_type: BetType = Query(default=BetType.NORMAL),
    bookmaker_codes: Optional[str] = Query(default=None, description="Comma-separated bookmaker codes"),
    sport_codes: Optional[str] = Query(default=None, description="Comma-separated sport codes"),
    competition_ids: Optional[str] = Query(default=None, description="Comma-separated competition IDs"),
    search: Optional[str] = Query(default=None, description="Search event names"),
    min_rating: Optional[Decimal] = Query(default=None, ge=Decimal("0"), le=Decimal("100")),
    limit: int = Query(default=50, ge=1, le=200),
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[OddsMatchResponse]:
    """
    Get matched betting opportunities with filtering.

    Filters available odds to show only best opportunities based on:
    - User's plan (free tier = TAB + Ladbrokes only)
    - Stake amount
    - Bet type (normal vs bonus)
    - Sport, competition, search terms
    - Minimum rating threshold
    """
    # Get user and check entitlements
    user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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
    competition_filter = [int(x) for x in competition_ids.split(",")] if competition_ids else None

    # Apply plan restrictions: filter to only allowed bookmakers
    if bookmaker_filter:
        # User requested specific bookmakers - ensure they're allowed
        bookmaker_filter = [bm for bm in bookmaker_filter if bm in allowed_bookmakers]
    else:
        # No filter specified - use all allowed bookmakers
        bookmaker_filter = allowed_bookmakers

    if not bookmaker_filter:
        raise HTTPException(
            status_code=403,
            detail="Your plan does not allow access to the requested bookmakers"
        )

    # Build query for current odds
    # We need: Event -> Market -> Selection -> OddsSnapshot
    # Find events happening in next 7 days
    now = datetime.now(timezone.utc)
    date_from = now
    date_to = now + timedelta(days=7)

    # Query for events with filters
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

    events = events_query.limit(100).all()

    if not events:
        return []

    # For each event, find matched betting opportunities
    matching_engine = MatchingEngine()
    opportunities = []

    for event in events:
        # Get markets for this event (focus on match_winner markets)
        markets = db.query(Market).filter(
            and_(
                Market.event_id == event.id,
                Market.is_active == True,
                Market.market_type == "match_winner"  # Start with H2H markets
            )
        ).all()

        for market in markets:
            # Get selections for this market
            selections = db.query(Selection).filter(
                Selection.market_id == market.id
            ).all()

            for selection in selections:
                # Get current back odds from allowed bookmakers
                back_odds = db.query(OddsSnapshot).join(Bookmaker).filter(
                    and_(
                        OddsSnapshot.selection_id == selection.id,
                        OddsSnapshot.is_current == True,
                        Bookmaker.code.in_(bookmaker_filter)
                    )
                ).all()

                # Get current lay odds from Betfair
                lay_odds = db.query(OddsSnapshot).join(Bookmaker).filter(
                    and_(
                        OddsSnapshot.selection_id == selection.id,
                        OddsSnapshot.is_current == True,
                        Bookmaker.code == "betfair"
                    )
                ).all()

                if not back_odds or not lay_odds:
                    continue

                # Find best back odds (highest)
                best_back = max(back_odds, key=lambda x: x.decimal_odds)

                # Use first lay odds (in production, handle multiple lay prices)
                best_lay = lay_odds[0]

                # Calculate matched bet
                back_bet = BackBet(
                    bookmaker_code=best_back.bookmaker.code,
                    bookmaker_name=best_back.bookmaker.display_name,
                    back_odds=best_back.decimal_odds,
                    stake=stake
                )

                lay_bet = LayBet(
                    lay_odds=best_lay.decimal_odds,
                    commission=Decimal("0.02"),  # 2% Betfair commission
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

                opportunities.append(OddsMatchResponse(
                    event_id=event.id,
                    event_name=event.name,
                    event_start_time=event.start_time,
                    sport_name=event.competition.sport.display_name,
                    competition_name=event.competition.short_name,
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

    # Sort by rating (best first)
    opportunities.sort(key=lambda x: x.rating, reverse=True)

    return opportunities[:limit]
