# apps/api/src/api/services/matching_engine.py
"""
Matched betting engine for calculating back/lay opportunities and PnL.
Handles normal bets and bonus bets with Betfair commission.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any
from enum import Enum


class BetType(str, Enum):
    """Type of bet being placed"""
    NORMAL = "normal"
    BONUS = "bonus"  # Bonus bets don't return the stake


@dataclass
class BackBet:
    """Back bet at a bookmaker"""
    bookmaker_code: str
    bookmaker_name: str
    back_odds: Decimal  # Decimal odds (e.g., 2.50)
    stake: Decimal  # Amount to bet in AUD


@dataclass
class LayBet:
    """Lay bet at Betfair exchange"""
    lay_odds: Decimal  # Decimal odds
    commission: Decimal = Decimal("0.02")  # 2% default Betfair commission
    liquidity: Optional[Decimal] = None  # Available AUD at this price


@dataclass
class MatchedBetOutcome:
    """Outcome calculation for a matched bet"""
    outcome_name: str  # "Back wins", "Lay wins"
    profit_loss: Decimal  # Net profit/loss in AUD
    is_winning_outcome: bool


@dataclass
class MatchedBetCalculation:
    """Complete matched betting calculation"""
    back_bet: BackBet
    lay_bet: LayBet
    bet_type: BetType

    # Stakes
    back_stake: Decimal
    lay_stake: Decimal
    lay_liability: Decimal

    # Outcomes
    outcomes: List[MatchedBetOutcome]

    # Summary metrics
    qualifying_loss: Decimal  # Expected loss for qualifying bet
    profit_if_back_wins: Decimal
    profit_if_lay_wins: Decimal
    rating: Decimal  # Quality rating (0-100)

    @property
    def is_profitable(self) -> bool:
        """Returns True if this is an arbitrage opportunity"""
        return self.qualifying_loss > Decimal("0")


class MatchingEngine:
    """Engine for calculating matched betting opportunities"""

    def __init__(self):
        pass

    def calculate_lay_stake(
        self,
        back_stake: Decimal,
        back_odds: Decimal,
        lay_odds: Decimal,
        bet_type: BetType = BetType.NORMAL
    ) -> Decimal:
        """
        Calculate the required lay stake to cover the back bet.

        For normal bets:
            lay_stake = (back_stake * back_odds) / lay_odds

        For bonus bets (stake not returned):
            lay_stake = (back_stake * (back_odds - 1)) / lay_odds
        """
        if bet_type == BetType.BONUS:
            # Bonus bets don't return the stake
            numerator = back_stake * (back_odds - Decimal("1"))
        else:
            # Normal bets return stake + winnings
            numerator = back_stake * back_odds

        lay_stake = numerator / lay_odds
        return lay_stake.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_lay_liability(
        self,
        lay_stake: Decimal,
        lay_odds: Decimal
    ) -> Decimal:
        """
        Calculate the liability (risk) for a lay bet.
        Liability = lay_stake * (lay_odds - 1)
        """
        liability = lay_stake * (lay_odds - Decimal("1"))
        return liability.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_commission(
        self,
        winnings: Decimal,
        commission_rate: Decimal = Decimal("0.02")
    ) -> Decimal:
        """Calculate Betfair commission on winnings"""
        commission = winnings * commission_rate
        return commission.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_matched_bet(
        self,
        back_bet: BackBet,
        lay_bet: LayBet,
        bet_type: BetType = BetType.NORMAL
    ) -> MatchedBetCalculation:
        """
        Calculate complete matched bet with all outcomes.

        Returns a MatchedBetCalculation with:
        - Required lay stake and liability
        - Profit/loss for each outcome
        - Overall qualifying loss/profit
        - Quality rating
        """
        back_stake = back_bet.stake
        back_odds = back_bet.back_odds
        lay_odds = lay_bet.lay_odds
        commission = lay_bet.commission

        # Calculate lay stake required
        lay_stake = self.calculate_lay_stake(
            back_stake, back_odds, lay_odds, bet_type
        )

        # Calculate lay liability
        lay_liability = self.calculate_lay_liability(lay_stake, lay_odds)

        # Scenario 1: Back bet wins (selection wins)
        if bet_type == BetType.BONUS:
            # Bonus bet: only winnings returned (no stake back)
            back_winnings = back_stake * (back_odds - Decimal("1"))
        else:
            # Normal bet: stake + winnings
            back_winnings = (back_stake * back_odds) - back_stake

        # Lay bet loses: we pay out the liability
        lay_loss = lay_liability

        # Net profit if back wins
        profit_if_back_wins = back_winnings - lay_loss
        if bet_type == BetType.NORMAL:
            # We lose the back stake at the bookmaker (it's tied up)
            # But we get it back, so net effect is zero for stake
            pass
        else:
            # Bonus bet: we lose nothing at bookmaker (free bet)
            pass

        # Scenario 2: Lay bet wins (selection loses)
        # Lay bet wins: we keep the lay stake minus commission
        lay_winnings = lay_stake
        betfair_commission = self.calculate_commission(lay_winnings, commission)
        lay_profit = lay_winnings - betfair_commission

        # Back bet loses
        if bet_type == BetType.BONUS:
            # Bonus bet: we lose nothing (it was free)
            back_loss = Decimal("0")
        else:
            # Normal bet: we lose our stake
            back_loss = back_stake

        # Net profit if lay wins
        profit_if_lay_wins = lay_profit - back_loss

        # Overall qualifying loss (average of both outcomes)
        qualifying_loss = (profit_if_back_wins + profit_if_lay_wins) / Decimal("2")

        # Calculate quality rating (0-100)
        # Better rating for smaller qualifying loss on normal bets
        # Higher rating for higher profit on bonus bets
        if bet_type == BetType.BONUS:
            # Bonus bets: rating based on profit potential
            # Typically ranges from 70-95% returns
            return_percentage = (qualifying_loss / back_stake) * Decimal("100")
            rating = min(Decimal("100"), max(Decimal("0"), return_percentage))
        else:
            # Normal bets: rating based on closeness of odds (lower loss = better)
            # Calculate loss percentage
            loss_percentage = abs(qualifying_loss / back_stake) * Decimal("100")
            # Invert: lower loss = higher rating
            # Typical qualifying loss is 2-5%, so rate 5% loss as 0, 0% as 100
            rating = max(Decimal("0"), Decimal("100") - (loss_percentage * Decimal("20")))

        rating = rating.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

        # Create outcomes
        outcomes = [
            MatchedBetOutcome(
                outcome_name="Back wins (selection wins)",
                profit_loss=profit_if_back_wins,
                is_winning_outcome=profit_if_back_wins > profit_if_lay_wins
            ),
            MatchedBetOutcome(
                outcome_name="Lay wins (selection loses)",
                profit_loss=profit_if_lay_wins,
                is_winning_outcome=profit_if_lay_wins > profit_if_back_wins
            )
        ]

        return MatchedBetCalculation(
            back_bet=back_bet,
            lay_bet=lay_bet,
            bet_type=bet_type,
            back_stake=back_stake,
            lay_stake=lay_stake,
            lay_liability=lay_liability,
            outcomes=outcomes,
            qualifying_loss=qualifying_loss,
            profit_if_back_wins=profit_if_back_wins,
            profit_if_lay_wins=profit_if_lay_wins,
            rating=rating
        )

    def find_best_matches(
        self,
        back_opportunities: List[Dict[str, Any]],
        lay_opportunities: List[Dict[str, Any]],
        stake: Decimal = Decimal("100"),
        bet_type: BetType = BetType.NORMAL,
        min_liquidity: Optional[Decimal] = None
    ) -> List[MatchedBetCalculation]:
        """
        Find best matched betting opportunities from available back and lay odds.

        Args:
            back_opportunities: List of dicts with 'bookmaker_code', 'bookmaker_name', 'odds'
            lay_opportunities: List of dicts with 'odds', 'commission', 'liquidity'
            stake: Amount to bet (AUD)
            bet_type: NORMAL or BONUS
            min_liquidity: Minimum liquidity required at Betfair

        Returns:
            List of MatchedBetCalculation, sorted by rating (best first)
        """
        matches = []

        for back_opp in back_opportunities:
            for lay_opp in lay_opportunities:
                # Check liquidity if required
                if min_liquidity and lay_opp.get('liquidity'):
                    if Decimal(str(lay_opp['liquidity'])) < min_liquidity:
                        continue

                back_bet = BackBet(
                    bookmaker_code=back_opp['bookmaker_code'],
                    bookmaker_name=back_opp['bookmaker_name'],
                    back_odds=Decimal(str(back_opp['odds'])),
                    stake=stake
                )

                lay_bet = LayBet(
                    lay_odds=Decimal(str(lay_opp['odds'])),
                    commission=Decimal(str(lay_opp.get('commission', '0.02'))),
                    liquidity=Decimal(str(lay_opp['liquidity'])) if lay_opp.get('liquidity') else None
                )

                calculation = self.calculate_matched_bet(back_bet, lay_bet, bet_type)
                matches.append(calculation)

        # Sort by rating (best first)
        matches.sort(key=lambda x: x.rating, reverse=True)

        return matches

    def calculate_pnl_percentage(
        self,
        calculation: MatchedBetCalculation
    ) -> Decimal:
        """
        Calculate PnL as a percentage of stake.

        For normal bets: typically negative (qualifying loss)
        For bonus bets: typically positive (profit)
        """
        pnl_pct = (calculation.qualifying_loss / calculation.back_stake) * Decimal("100")
        return pnl_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
