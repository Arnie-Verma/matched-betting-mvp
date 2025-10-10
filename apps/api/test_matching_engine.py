"""
Test matching engine calculations against expected formulas.
"""
from decimal import Decimal
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from api.services.matching_engine import MatchingEngine, BackBet, LayBet, BetType


def test_normal_bet():
    """Test Normal Bet calculation"""
    print("\n=== NORMAL BET TEST ===")
    print("Inputs:")
    print("  Bet Stake: $100")
    print("  Back Odds: 3.25")
    print("  Lay Odds: 3.30")
    print("  Lay Commission: 6%")

    engine = MatchingEngine()

    back_bet = BackBet(
        bookmaker_code="tab",
        bookmaker_name="TAB",
        back_odds=Decimal("3.25"),
        stake=Decimal("100")
    )

    lay_bet = LayBet(
        lay_odds=Decimal("3.30"),
        commission=Decimal("0.06"),
        liquidity=Decimal("1000")
    )

    result = engine.calculate_matched_bet(back_bet, lay_bet, BetType.NORMAL)

    print("\nCalculated:")
    print(f"  Lay Stake: ${result.lay_stake}")
    print(f"  Expected: $100.31")

    print("\nOutcomes:")
    print(f"  If back bet wins: ${result.profit_if_back_wins:.2f}")
    print(f"  Expected: -$5.71")
    print(f"  If back bet loses: ${result.profit_if_lay_wins:.2f}")
    print(f"  Expected: -$5.71")

    print(f"\nBetfair Liability: ${result.lay_liability:.2f}")
    print(f"  Expected: $230.71")

    # Calculate return percentages
    return_back_wins = (result.profit_if_back_wins / back_bet.stake) * Decimal("100")
    return_back_loses = (result.profit_if_lay_wins / back_bet.stake) * Decimal("100")

    print(f"\nReturn %:")
    print(f"  If back wins: {return_back_wins:.0f}%")
    print(f"  If back loses: {return_back_loses:.0f}%")
    print(f"  Expected: -6%")

    # Verify
    print("\n✓ Verification:")
    assert abs(result.lay_stake - Decimal("100.31")) < Decimal("0.01"), f"Lay stake mismatch: {result.lay_stake}"
    assert abs(result.lay_liability - Decimal("230.71")) < Decimal("0.01"), f"Liability mismatch: {result.lay_liability}"
    assert abs(result.profit_if_back_wins - Decimal("-5.71")) < Decimal("0.02"), f"Profit if back wins mismatch: {result.profit_if_back_wins}"
    assert abs(result.profit_if_lay_wins - Decimal("-5.71")) < Decimal("0.02"), f"Profit if lay wins mismatch: {result.profit_if_lay_wins}"
    print("  All assertions passed!")


def test_bonus_bet():
    """Test Bonus Bet (SNR) calculation"""
    print("\n=== BONUS BET SNR TEST ===")
    print("Inputs:")
    print("  Bet Stake: $100")
    print("  Back Odds: 3.25")
    print("  Lay Odds: 3.30")
    print("  Lay Commission: 6%")

    engine = MatchingEngine()

    back_bet = BackBet(
        bookmaker_code="tab",
        bookmaker_name="TAB",
        back_odds=Decimal("3.25"),
        stake=Decimal("100")
    )

    lay_bet = LayBet(
        lay_odds=Decimal("3.30"),
        commission=Decimal("0.06"),
        liquidity=Decimal("1000")
    )

    result = engine.calculate_matched_bet(back_bet, lay_bet, BetType.BONUS)

    print("\nCalculated:")
    print(f"  Lay Stake: ${result.lay_stake}")
    print(f"  Expected: $69.44")

    print("\nOutcomes:")
    print(f"  If back bet wins: ${result.profit_if_back_wins:.2f}")
    print(f"  Expected: $65.28")
    print(f"  If back bet loses: ${result.profit_if_lay_wins:.2f}")
    print(f"  Expected: $65.28")

    print(f"\nBetfair Liability: ${result.lay_liability:.2f}")
    print(f"  Expected: $159.72")

    # Calculate return percentages
    return_back_wins = (result.profit_if_back_wins / back_bet.stake) * Decimal("100")
    return_back_loses = (result.profit_if_lay_wins / back_bet.stake) * Decimal("100")

    print(f"\nReturn %:")
    print(f"  If back wins: {return_back_wins:.0f}%")
    print(f"  If back loses: {return_back_loses:.0f}%")
    print(f"  Expected: 65%")

    # Verify
    print("\n✓ Verification:")
    assert abs(result.lay_stake - Decimal("69.44")) < Decimal("0.02"), f"Lay stake mismatch: {result.lay_stake}"
    assert abs(result.lay_liability - Decimal("159.72")) < Decimal("0.02"), f"Liability mismatch: {result.lay_liability}"
    assert abs(result.profit_if_back_wins - Decimal("65.28")) < Decimal("0.02"), f"Profit if back wins mismatch: {result.profit_if_back_wins}"
    assert abs(result.profit_if_lay_wins - Decimal("65.28")) < Decimal("0.02"), f"Profit if lay wins mismatch: {result.profit_if_lay_wins}"
    print("  All assertions passed!")


if __name__ == "__main__":
    try:
        test_normal_bet()
        test_bonus_bet()
        print("\n" + "="*50)
        print("✅ ALL TESTS PASSED!")
        print("="*50)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
