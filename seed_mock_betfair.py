"""
Seed mock Betfair lay odds for existing TAB events.

This allows us to test the complete matched betting flow
before implementing the real Betfair scraper.

Formula: lay_odds = back_odds + 0.05 (slightly higher for realistic spread)
"""
import sys
sys.path.insert(0, "apps/api/src")

from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select
from api.core.database import SessionLocal
from api.models.odds import Bookmaker, Event, Market, Selection, OddsSnapshot


def seed_mock_betfair_odds():
    """Create mock Betfair lay odds for all existing TAB back odds"""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("🎰 SEEDING MOCK BETFAIR LAY ODDS")
        print("=" * 80)

        # Get or create Betfair bookmaker
        betfair = db.scalar(select(Bookmaker).where(Bookmaker.code == "betfair"))
        if not betfair:
            print("❌ Betfair bookmaker not found in database")
            print("   Run seed_all_bookmakers.py first")
            return

        print(f"\n✅ Found Betfair bookmaker (id: {betfair.id})")

        # Get all TAB odds
        tab = db.scalar(select(Bookmaker).where(Bookmaker.code == "tab"))
        if not tab:
            print("❌ TAB bookmaker not found")
            return

        tab_odds = db.execute(
            select(OddsSnapshot).where(
                OddsSnapshot.bookmaker_id == tab.id,
                OddsSnapshot.is_current == True
            )
        ).scalars().all()

        print(f"📊 Found {len(tab_odds)} TAB odds to create Betfair matches for")

        if not tab_odds:
            print("\n⚠️  No TAB odds found. Run the scraper first:")
            print("   docker exec mb_api python test_save_tab_odds.py")
            return

        # Create Betfair lay odds
        created_count = 0
        skipped_count = 0

        for tab_odd in tab_odds:
            # Check if Betfair odds already exist for this selection
            existing = db.scalar(
                select(OddsSnapshot).where(
                    OddsSnapshot.selection_id == tab_odd.selection_id,
                    OddsSnapshot.bookmaker_id == betfair.id,
                    OddsSnapshot.is_current == True
                )
            )

            if existing:
                skipped_count += 1
                continue

            # Create lay odds (slightly higher than back odds for realistic spread)
            lay_odds = tab_odd.decimal_odds + Decimal("0.05")

            # Create Betfair odds snapshot
            betfair_odds = OddsSnapshot(
                selection_id=tab_odd.selection_id,
                bookmaker_id=betfair.id,
                decimal_odds=lay_odds,
                source_type="manual",  # Mark as mock data
                source_url="mock://betfair",
                timestamp=datetime.now(timezone.utc),
                is_current=True,
                market_status="open",
                available_amount=Decimal("5000.00"),  # Mock liquidity: $5000
                scrape_session_id="mock_betfair_seed"
            )

            db.add(betfair_odds)
            created_count += 1

        # Commit all changes
        db.commit()

        print(f"\n✅ Mock Betfair Odds Created:")
        print(f"   Created: {created_count}")
        print(f"   Skipped (already exist): {skipped_count}")

        # Verify results
        total_betfair = db.execute(
            select(OddsSnapshot).where(
                OddsSnapshot.bookmaker_id == betfair.id,
                OddsSnapshot.is_current == True
            )
        ).scalars().all()

        print(f"\n📊 Total Betfair odds in database: {len(total_betfair)}")

        # Show sample matched odds
        print(f"\n💰 Sample Matched Odds:")
        sample_selection = db.get(Selection, tab_odds[0].selection_id)
        sample_tab = tab_odds[0]
        sample_betfair = db.scalar(
            select(OddsSnapshot).where(
                OddsSnapshot.selection_id == sample_selection.id,
                OddsSnapshot.bookmaker_id == betfair.id,
                OddsSnapshot.is_current == True
            )
        )

        if sample_betfair:
            print(f"   Selection: {sample_selection.name}")
            print(f"   TAB Back: {sample_tab.decimal_odds}")
            print(f"   Betfair Lay: {sample_betfair.decimal_odds}")
            print(f"   Spread: {sample_betfair.decimal_odds - sample_tab.decimal_odds}")

        print("\n" + "=" * 80)
        print("✅ MOCK BETFAIR SEEDING COMPLETE")
        print("=" * 80)
        print("\n🎯 You can now test the odds matcher with real TAB + mock Betfair!")
        print("   Next: Wire up frontend to /matcher endpoint")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    seed_mock_betfair_odds()
