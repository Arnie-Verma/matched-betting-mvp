# apps/api/src/api/scraping/base/opportunity_calculator.py
"""Matched betting opportunity calculator - Outmatched style PnL calculations"""
from typing import List, Dict, Optional
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class BookmakerOdds:
    """Odds from a specific bookmaker"""
    bookmaker_name: str
    home_odds: Decimal
    away_odds: Decimal
    home_liquidity: Optional[Decimal] = None  # Available liquidity
    away_liquidity: Optional[Decimal] = None


@dataclass
class MatchedBettingOpportunity:
    """Outmatched-style matched betting opportunity"""
    event_name: str

    # Back bet (blue in Outmatched)
    back_bookmaker: str
    back_selection: str  # "Home" or "Away"
    back_odds: Decimal
    back_liquidity: Optional[Decimal]

    # Lay bet (pink in Outmatched)
    lay_bookmaker: str
    lay_selection: str  # "Home" or "Away"
    lay_odds: Decimal
    lay_liquidity: Optional[Decimal]

    # Calculations (on $100 stake)
    stake_amount: Decimal = Decimal("100.00")
    profit_loss: Decimal = Decimal("0.00")  # Can be negative for qualifying bets
    profit_percentage: Decimal = Decimal("0.00")

    # Metadata
    confidence_score: float = 1.0
    last_updated: Optional[str] = None


class OpportunityCalculator:
    """Calculate matched betting opportunities in Outmatched style"""

    def __init__(self, default_stake: Decimal = Decimal("100.00")):
        self.default_stake = default_stake

    def find_opportunities(self, event_name: str, bookmaker_odds: List[BookmakerOdds]) -> List[MatchedBettingOpportunity]:
        """Find all matched betting opportunities for an event"""
        opportunities = []

        # Compare every bookmaker pair
        for i, book1 in enumerate(bookmaker_odds):
            for j, book2 in enumerate(bookmaker_odds):
                if i >= j:  # Avoid duplicates
                    continue

                # Check all possible back/lay combinations
                opportunities.extend(self._calculate_opportunities(event_name, book1, book2))
                opportunities.extend(self._calculate_opportunities(event_name, book2, book1))

        # Sort by profit (best opportunities first)
        opportunities.sort(key=lambda x: x.profit_loss, reverse=True)

        return opportunities

    def _calculate_opportunities(self, event_name: str, back_book: BookmakerOdds, lay_book: BookmakerOdds) -> List[MatchedBettingOpportunity]:
        """Calculate opportunities between two bookmakers"""
        opportunities = []

        # Home team back/lay combinations
        home_opp = self._calculate_single_opportunity(
            event_name=event_name,
            back_bookmaker=back_book.bookmaker_name,
            back_selection="Home",
            back_odds=back_book.home_odds,
            back_liquidity=back_book.home_liquidity,
            lay_bookmaker=lay_book.bookmaker_name,
            lay_selection="Home",
            lay_odds=lay_book.home_odds,
            lay_liquidity=lay_book.home_liquidity
        )
        if home_opp:
            opportunities.append(home_opp)

        # Away team back/lay combinations
        away_opp = self._calculate_single_opportunity(
            event_name=event_name,
            back_bookmaker=back_book.bookmaker_name,
            back_selection="Away",
            back_odds=back_book.away_odds,
            back_liquidity=back_book.away_liquidity,
            lay_bookmaker=lay_book.bookmaker_name,
            lay_selection="Away",
            lay_odds=lay_book.away_odds,
            lay_liquidity=lay_book.away_liquidity
        )
        if away_opp:
            opportunities.append(away_opp)

        return opportunities

    def _calculate_single_opportunity(
        self,
        event_name: str,
        back_bookmaker: str,
        back_selection: str,
        back_odds: Decimal,
        back_liquidity: Optional[Decimal],
        lay_bookmaker: str,
        lay_selection: str,
        lay_odds: Decimal,
        lay_liquidity: Optional[Decimal]
    ) -> Optional[MatchedBettingOpportunity]:
        """Calculate a single matched betting opportunity"""

        # Skip if same bookmaker
        if back_bookmaker == lay_bookmaker:
            return None

        # Skip if not betting on same selection
        if back_selection != lay_selection:
            return None

        try:
            # Calculate PnL using Outmatched methodology
            # Back bet: Stake $100, Win = (odds - 1) * stake, Lose = -stake
            # Lay bet: Stake $100, Win = stake, Lose = -(odds - 1) * stake

            back_win = (back_odds - Decimal("1")) * self.default_stake  # Profit if back wins
            back_lose = -self.default_stake  # Loss if back loses

            lay_win = self.default_stake  # Profit if lay wins (opposite bet)
            lay_lose = -(lay_odds - Decimal("1")) * self.default_stake  # Loss if lay loses

            # For matched betting: if back wins, lay loses (and vice versa)
            # Total profit = back_win + lay_lose (when back selection wins)
            # Total profit = back_lose + lay_win (when back selection loses)

            profit_if_back_wins = back_win + lay_lose
            profit_if_back_loses = back_lose + lay_win

            # In perfect matched betting, both scenarios should be equal
            # In practice, we take the worst-case scenario
            profit_loss = min(profit_if_back_wins, profit_if_back_loses)

            # Calculate percentage
            profit_percentage = (profit_loss / self.default_stake) * Decimal("100")

            return MatchedBettingOpportunity(
                event_name=event_name,
                back_bookmaker=back_bookmaker,
                back_selection=back_selection,
                back_odds=back_odds,
                back_liquidity=back_liquidity,
                lay_bookmaker=lay_bookmaker,
                lay_selection=lay_selection,
                lay_odds=lay_odds,
                lay_liquidity=lay_liquidity,
                stake_amount=self.default_stake,
                profit_loss=profit_loss.quantize(Decimal("0.01")),
                profit_percentage=profit_percentage.quantize(Decimal("0.01"))
            )

        except Exception as e:
            # If calculation fails, skip this opportunity
            return None

    def format_opportunity_display(self, opportunity: MatchedBettingOpportunity) -> Dict[str, str]:
        """Format opportunity for Outmatched-style display"""
        profit_sign = "+" if opportunity.profit_loss >= 0 else ""

        return {
            "event": opportunity.event_name,
            "back_bet": f"{opportunity.back_bookmaker} {opportunity.back_selection} ${opportunity.back_odds}",
            "lay_bet": f"{opportunity.lay_bookmaker} {opportunity.lay_selection} ${opportunity.lay_odds}",
            "pnl": f"{profit_sign}${opportunity.profit_loss} AUD",
            "percentage": f"{profit_sign}{opportunity.profit_percentage}%",
            "display_text": f"Profit: {profit_sign}${opportunity.profit_loss} on ${opportunity.stake_amount} stake",
            "is_qualifying_bet": opportunity.profit_loss < 0,
            "back_color": "blue",  # Outmatched style
            "lay_color": "pink"    # Outmatched style
        }

    def filter_opportunities(
        self,
        opportunities: List[MatchedBettingOpportunity],
        min_profit: Optional[Decimal] = None,
        include_qualifying_bets: bool = True
    ) -> List[MatchedBettingOpportunity]:
        """Filter opportunities based on criteria"""
        filtered = opportunities

        if min_profit is not None:
            filtered = [opp for opp in filtered if opp.profit_loss >= min_profit]

        if not include_qualifying_bets:
            filtered = [opp for opp in filtered if opp.profit_loss >= 0]

        return filtered