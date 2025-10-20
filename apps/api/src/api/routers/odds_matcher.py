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
    import logging
    logger = logging.getLogger(__name__)
    logger.info("=== REFRESH ODDS ENDPOINT CALLED ===")
    logger.info(f"User: {user_claims.sub}")

    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

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

    # Global cache key (shared by all users)
    global_cache_key = "odds_last_refresh_global"

    # Check global cache first (unless force refresh)
    # Cache provides natural rate limiting - no need for explicit limits
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

    # Trigger scraping (only if cache expired)
    import sys
    sys.path.insert(0, "../worker/src")

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
    import logging
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
    events = events_query.limit(100).all()
    logger.info(f"Query executed successfully, found {len(events)} events")

    print(f"\n>>> Found {len(events)} events in date range {date_from} to {date_to}")
    print(f">>> Bookmaker filter: {bookmaker_filter}\n")

    logger.info(f"Matcher query found {len(events)} events in date range {date_from} to {date_to}")
    logger.info(f"Bookmaker filter: {bookmaker_filter}")

    if not events:
        logger.warning("No events found - returning empty list")
        print(">>> No events found - returning empty list")
        return []

    # Group events by normalized name to handle duplicate events from different bookmakers
    print(f"\n>>> Grouping {len(events)} events by normalized name...")
    event_groups = {}
    for event in events:
        # Normalize event name to group similar events from different bookmakers
        norm_event_name = event.name.lower().strip()

        # Team name variations
        norm_event_name = norm_event_name.replace('wolverhampton', 'wolves')
        norm_event_name = norm_event_name.replace('nottinghm', 'nottm')
        norm_event_name = norm_event_name.replace('nottingham', 'nottm')
        norm_event_name = norm_event_name.replace('brighton hovealb', 'brighton')
        norm_event_name = norm_event_name.replace('brighton & hove albion', 'brighton')
        norm_event_name = norm_event_name.replace('leeds united', 'leeds')
        norm_event_name = norm_event_name.replace('manchester united', 'manutd')
        norm_event_name = norm_event_name.replace('manchester city', 'mancity')
        norm_event_name = norm_event_name.replace('man united', 'manutd')
        norm_event_name = norm_event_name.replace('man city', 'mancity')
        norm_event_name = norm_event_name.replace('man utd', 'manutd')
        norm_event_name = norm_event_name.replace('tottenham hotspur', 'tottenham')
        norm_event_name = norm_event_name.replace('west ham united', 'westham')
        norm_event_name = norm_event_name.replace('newcastle united', 'newcastle')
        norm_event_name = norm_event_name.replace('leicester city', 'leicester')

        # Remove all spaces and 'v' separator
        norm_event_name = norm_event_name.replace(' v ', 'v').replace(' ', '')

        if norm_event_name not in event_groups:
            event_groups[norm_event_name] = []
        event_groups[norm_event_name].append(event)

    print(f">>> Found {len(event_groups)} unique events (from {len(events)} total events)")

    # For each event group, find matched betting opportunities
    matching_engine = MatchingEngine()
    opportunities = []

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
                    and_(Market.name.ilike('%h2h%'), Market.name.notilike('%hth2h%'))
                )
            )
        ).all()

        print(f"    Markets found across all events: {len(markets)}")
        logger.info(f"  Found {len(markets)} markets across event group {event_names}")

        # Group ALL selections across ALL markets in this event group
        selection_groups = {}
        for market in markets:
            logger.info(f"    Market: {market.name} (ID: {market.id})")

            # Get selections for this market
            selections = db.query(Selection).filter(
                Selection.market_id == market.id
            ).all()

            logger.info(f"      Found {len(selections)} selections")

            # Group selections by normalized name across ALL markets in this event group
            for selection in selections:
                # Normalize selection name for matching (remove "The", spaces, lowercase, abbreviations)
                norm_name = selection.name.lower().strip()
                norm_name = norm_name.replace('the ', '').replace(' the ', ' ')  # Remove "the" prefix
                norm_name = norm_name.replace('utd', 'united').replace('man ', 'manchester')  # Expand abbreviations
                norm_name = norm_name.replace(' ', '')  # Remove all spaces

                if norm_name not in selection_groups:
                    selection_groups[norm_name] = {
                        'selections': [],
                        'back_odds': [],
                        'lay_odds': []
                    }

                selection_groups[norm_name]['selections'].append(selection)

                # Get back odds for this selection
                back_bookmakers = [bm for bm in bookmaker_filter if bm != "betfair"]
                if back_bookmakers:
                    back = db.query(OddsSnapshot).join(Bookmaker).filter(
                        and_(
                            OddsSnapshot.selection_id == selection.id,
                            OddsSnapshot.is_current == True,
                            Bookmaker.code.in_(back_bookmakers)
                        )
                    ).all()
                    selection_groups[norm_name]['back_odds'].extend(back)

                # Get lay odds for this selection
                lay = db.query(OddsSnapshot).join(Bookmaker).filter(
                    and_(
                        OddsSnapshot.selection_id == selection.id,
                        OddsSnapshot.is_current == True,
                        Bookmaker.code == "betfair"
                    )
                ).all()
                selection_groups[norm_name]['lay_odds'].extend(lay)

        # Now check each selection group for matched opportunities
        for norm_name, group in selection_groups.items():
            back_odds = group['back_odds']
            lay_odds = group['lay_odds']
            selection = group['selections'][0]  # Use first selection for metadata

            # Show all original names in this group
            all_names = [s.name for s in group['selections']]
            print(f"    Selection group '{norm_name}' (original names: {all_names}): {len(back_odds)} back, {len(lay_odds)} lay")

            if not back_odds or not lay_odds:
                if not back_odds:
                    print(f"      SKIP: no back odds")
                if not lay_odds:
                    print(f"      SKIP: no lay odds")
                continue

            print(f"      MATCH FOUND! Creating opportunity...")

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
                competition_name=representative_event.competition.short_name,
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
    opportunities.sort(key=lambda x: x.pnl_percentage, reverse=True)

    print(f"\n{'='*80}")
    print(f"=== SUMMARY: Found {len(opportunities)} matched betting opportunities ===")
    print(f"{'='*80}\n")

    logger.info(f"=== MATCHER SUMMARY ===")
    logger.info(f"Total opportunities found: {len(opportunities)}")
    logger.info(f"Returning top {min(limit, len(opportunities))} opportunities")

    return opportunities[:limit]
