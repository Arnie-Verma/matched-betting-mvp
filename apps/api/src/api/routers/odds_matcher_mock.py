# apps/api/src/api/routers/odds_matcher_mock.py
"""
Mock odds matcher endpoint for testing UI without real data.
Returns fake but realistic matched betting opportunities.

DELETE THIS FILE once real scraping is working!
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List
from fastapi import APIRouter, Query
from random import uniform, choice, randint

from api.routers.odds_matcher import OddsMatchResponse, BetType
from api.services.matching_engine import MatchingEngine, BackBet, LayBet


router = APIRouter(prefix="/odds", tags=["odds-matcher-mock"])


def generate_mock_opportunities(
    count: int = 20,
    stake: Decimal = Decimal("100"),
    bet_type: BetType = BetType.NORMAL
) -> List[OddsMatchResponse]:
    """Generate fake but realistic odds opportunities"""

    opportunities = []
    engine = MatchingEngine()

    # Mock events
    afl_teams = [
        ("Richmond Tigers", "Collingwood Magpies"),
        ("Melbourne Demons", "Sydney Swans"),
        ("Geelong Cats", "Brisbane Lions"),
        ("Carlton Blues", "Essendon Bombers"),
        ("Port Adelaide Power", "Adelaide Crows"),
        ("West Coast Eagles", "Fremantle Dockers"),
        ("St Kilda Saints", "Hawthorn Hawks"),
        ("Western Bulldogs", "North Melbourne Kangaroos"),
    ]

    nrl_teams = [
        ("Melbourne Storm", "Penrith Panthers"),
        ("Brisbane Broncos", "North Queensland Cowboys"),
        ("Sydney Roosters", "South Sydney Rabbitohs"),
        ("Parramatta Eels", "Canterbury Bulldogs"),
        ("Cronulla Sharks", "St George Illawarra Dragons"),
    ]

    sports = [
        ("afl", "AFL", "AFL Premiership 2025", afl_teams),
        ("nrl", "NRL", "NRL Premiership 2025", nrl_teams),
    ]

    bookmakers = ["tab", "ladbrokes"]

    for i in range(count):
        # Pick random sport and teams
        sport_code, sport_name, competition, teams = choice(sports)
        home_team, away_team = choice(teams)
        event_name = f"{home_team} vs {away_team}"

        # Random time in next 7 days
        hours_ahead = randint(1, 168)
        start_time = datetime.now(timezone.utc) + timedelta(hours=hours_ahead)

        # Random bookmaker
        bookmaker_code = choice(bookmakers)
        bookmaker_name = "TAB" if bookmaker_code == "tab" else "Ladbrokes"

        # Generate realistic odds
        # Back odds between 1.50 and 5.00
        back_odds = Decimal(str(round(uniform(1.50, 5.00), 2)))

        # Lay odds slightly higher (typical Betfair spread)
        # Normal bets: 1-3% higher
        # Bonus bets: 2-5% higher
        if bet_type == BetType.NORMAL:
            spread_pct = uniform(0.01, 0.03)
        else:
            spread_pct = uniform(0.02, 0.05)

        lay_odds = back_odds * Decimal(str(1 + spread_pct))
        lay_odds = lay_odds.quantize(Decimal("0.01"))

        # Random liquidity
        liquidity = Decimal(str(randint(500, 50000)))

        # Calculate using matching engine
        back_bet = BackBet(
            bookmaker_code=bookmaker_code,
            bookmaker_name=bookmaker_name,
            back_odds=back_odds,
            stake=stake
        )

        lay_bet = LayBet(
            lay_odds=lay_odds,
            commission=Decimal("0.02"),
            liquidity=liquidity
        )

        calc = engine.calculate_matched_bet(back_bet, lay_bet, bet_type)
        pnl_pct = engine.calculate_pnl_percentage(calc)

        # Create response
        opp = OddsMatchResponse(
            event_id=i + 1000,
            event_name=event_name,
            event_start_time=start_time,
            sport_name=sport_name,
            competition_name=competition,
            market_id=i + 2000,
            market_name="Head To Head",
            market_type="match_winner",
            selection_id=i + 3000,
            selection_name=home_team,
            back_bookmaker_code=bookmaker_code,
            back_bookmaker_name=bookmaker_name,
            back_odds=float(back_odds),
            back_stake=float(stake),
            lay_odds=float(lay_odds),
            lay_stake=float(calc.lay_stake),
            lay_liability=float(calc.lay_liability),
            lay_commission=0.02,
            lay_liquidity=float(liquidity),
            profit_if_back_wins=float(calc.profit_if_back_wins),
            profit_if_lay_wins=float(calc.profit_if_lay_wins),
            qualifying_loss=float(calc.qualifying_loss),
            pnl_percentage=float(pnl_pct),
            bet_type=bet_type,
            rating=float(calc.rating),
            last_updated=datetime.now(timezone.utc)
        )

        opportunities.append(opp)

    # Sort by rating (best first)
    opportunities.sort(key=lambda x: x.rating, reverse=True)

    return opportunities


@router.get("/matcher-mock", response_model=List[OddsMatchResponse])
async def get_mock_matcher_opportunities(
    stake: Decimal = Query(default=Decimal("100"), ge=Decimal("1"), le=Decimal("10000")),
    bet_type: BetType = Query(default=BetType.NORMAL),
    limit: int = Query(default=20, ge=1, le=100),
) -> List[OddsMatchResponse]:
    """
    🧪 MOCK ENDPOINT - Returns fake odds for testing UI

    This endpoint generates realistic but fake matched betting opportunities
    so you can test the UI without needing real scraped data.

    DELETE THIS ENDPOINT once real scraping is working!

    Query params work the same as /odds/matcher:
    - stake: Amount to bet (1-10000 AUD)
    - bet_type: "normal" or "bonus"
    - limit: Max results (1-100)
    """
    opportunities = generate_mock_opportunities(
        count=limit,
        stake=stake,
        bet_type=bet_type
    )

    return opportunities
