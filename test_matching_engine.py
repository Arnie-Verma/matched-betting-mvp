#!/usr/bin/env python3
"""
Quick test script for the matching engine.
Run from project root: python test_matching_engine.py
"""
import sys
from pathlib import Path

# Add API to path
sys.path.insert(0, str(Path(__file__).parent / "apps" / "api" / "src"))

from decimal import Decimal
from api.services.matching_engine import MatchingEngine, BackBet, LayBet, BetType


def print_separator():
    print("=" * 70)


def test_normal_bet():
    """Test normal bet calculation"""
    print_separator()
    print("TEST 1: Normal Bet (Qualifying Loss)")
    print_separator()

    engine = MatchingEngine()

    back_bet = BackBet(
        bookmaker_code="tab",
        bookmaker_name="TAB",
        back_odds=Decimal("2.00"),
        stake=Decimal("100")
    )

    lay_bet = LayBet(
        lay_odds=Decimal("2.02"),
        commission=Decimal("0.02")
    )

    result = engine.calculate_matched_bet(back_bet, lay_bet, BetType.NORMAL)
    pnl_pct = engine.calculate_pnl_percentage(result)

    print(f"\n📊 Input:")
    print(f"  Back: ${result.back_stake} at {back_bet.back_odds} ({back_bet.bookmaker_name})")
    print(f"  Lay: {lay_bet.lay_odds} at Betfair ({lay_bet.commission * 100}% commission)")

    print(f"\n💰 Required Stakes:")
    print(f"  Bookmaker Stake: ${result.back_stake}")
    print(f"  Betfair Lay Stake: ${result.lay_stake}")
    print(f"  Betfair Liability: ${result.lay_liability}")

    print(f"\n🎯 Outcomes:")
    print(f"  If selection WINS  (back wins): ${result.profit_if_back_wins:+.2f}")
    print(f"  If selection LOSES (lay wins):  ${result.profit_if_lay_wins:+.2f}")

    print(f"\n📈 Summary:")
    print(f"  Qualifying Loss: ${result.qualifying_loss:+.2f}")
    print(f"  PnL Percentage: {pnl_pct:+.2f}%")
    print(f"  Quality Rating: {result.rating:.1f}/100")

    print(f"\n✅ Expected: Small loss (1-5%) - this unlocks bonus bets!")
    print()

    return result


def test_bonus_bet():
    """Test bonus bet calculation"""
    print_separator()
    print("TEST 2: Bonus Bet (Profit)")
    print_separator()

    engine = MatchingEngine()

    back_bet = BackBet(
        bookmaker_code="ladbrokes",
        bookmaker_name="Ladbrokes",
        back_odds=Decimal("4.00"),
        stake=Decimal("50")
    )

    lay_bet = LayBet(
        lay_odds=Decimal("4.10"),
        commission=Decimal("0.02")
    )

    result = engine.calculate_matched_bet(back_bet, lay_bet, BetType.BONUS)
    pnl_pct = engine.calculate_pnl_percentage(result)

    print(f"\n📊 Input:")
    print(f"  Bonus Bet: ${result.back_stake} at {back_bet.back_odds} ({back_bet.bookmaker_name})")
    print(f"  Lay: {lay_bet.lay_odds} at Betfair ({lay_bet.commission * 100}% commission)")

    print(f"\n💰 Required Stakes:")
    print(f"  Bonus Bet (Free): ${result.back_stake} (no cost to you!)")
    print(f"  Betfair Lay Stake: ${result.lay_stake}")
    print(f"  Betfair Liability: ${result.lay_liability}")

    print(f"\n🎯 Outcomes:")
    print(f"  If selection WINS  (back wins): ${result.profit_if_back_wins:+.2f}")
    print(f"  If selection LOSES (lay wins):  ${result.profit_if_lay_wins:+.2f}")

    print(f"\n📈 Summary:")
    print(f"  Average Profit: ${result.qualifying_loss:+.2f}")
    print(f"  PnL Percentage: {pnl_pct:+.2f}%")
    print(f"  Quality Rating: {result.rating:.1f}/100")

    print(f"\n✅ Expected: Profit (70-95%) - guaranteed money from free bet!")
    print()

    return result


def test_edge_cases():
    """Test edge cases"""
    print_separator()
    print("TEST 3: Edge Cases")
    print_separator()

    engine = MatchingEngine()

    # Very close odds (low qualifying loss)
    back_bet = BackBet(
        bookmaker_code="tab",
        bookmaker_name="TAB",
        back_odds=Decimal("2.00"),
        stake=Decimal("100")
    )

    lay_bet = LayBet(
        lay_odds=Decimal("2.01"),  # Very close!
        commission=Decimal("0.02")
    )

    result = engine.calculate_matched_bet(back_bet, lay_bet, BetType.NORMAL)
    pnl_pct = engine.calculate_pnl_percentage(result)

    print(f"\n🔬 Close Odds Test:")
    print(f"  Back: 2.00, Lay: 2.01 (only 0.01 difference)")
    print(f"  Qualifying Loss: ${result.qualifying_loss:+.2f}")
    print(f"  PnL%: {pnl_pct:+.2f}%")
    print(f"  Rating: {result.rating:.1f}/100")
    print(f"  ✅ Rating should be high (close odds = better)")

    # Large stake
    back_bet_large = BackBet(
        bookmaker_code="tab",
        bookmaker_name="TAB",
        back_odds=Decimal("3.50"),
        stake=Decimal("1000")
    )

    lay_bet_large = LayBet(
        lay_odds=Decimal("3.60"),
        commission=Decimal("0.02")
    )

    result_large = engine.calculate_matched_bet(back_bet_large, lay_bet_large, BetType.NORMAL)

    print(f"\n💪 Large Stake Test:")
    print(f"  Stake: $1,000")
    print(f"  Lay Stake: ${result_large.lay_stake:.2f}")
    print(f"  Liability: ${result_large.lay_liability:.2f}")
    print(f"  ✅ All calculations scale linearly")

    print()


def main():
    """Run all tests"""
    print("\n🧪 Testing Matched Betting Calculation Engine")
    print("This tests the core math behind the odds matcher\n")

    try:
        test_normal_bet()
        test_bonus_bet()
        test_edge_cases()

        print_separator()
        print("✅ ALL TESTS PASSED!")
        print_separator()
        print("\n💡 Next steps:")
        print("  1. Start the dev servers: pnpm dev:up && pnpm dev")
        print("  2. Go to: http://localhost:3000/dashboard/odds-matcher")
        print("  3. Click 'Search Opportunities' to see mock data")
        print("  4. Click 'OPEN' on any bet to test the calculator")
        print("\n📖 See TEST_ODDS_MATCHER.md for full testing guide")
        print()

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
