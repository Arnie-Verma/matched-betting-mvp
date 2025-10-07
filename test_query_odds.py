"""Test querying odds from database"""
import sys
sys.path.insert(0, "apps/api/src")

from api.core.database import SessionLocal
from api.models.odds import Event, Market, Selection, OddsSnapshot, Bookmaker, Competition, Sport
from sqlalchemy import select

def test_query_odds():
    """Query and display odds from database"""
    db = SessionLocal()
    try:
        print("=" * 80)
        print("📊 REAL TAB ODDS IN DATABASE")
        print("=" * 80)

        # Get all events
        events = db.execute(select(Event)).scalars().all()

        print(f"\n✅ Found {len(events)} events in database\n")

        for event in events:
            competition = db.get(Competition, event.competition_id)
            sport = db.get(Sport, competition.sport_id) if competition else None

            print(f"⚽ Event: {event.name}")
            print(f"   Competition: {competition.name if competition else 'Unknown'}")
            print(f"   Sport: {sport.display_name if sport else 'Unknown'}")
            print(f"   Start Time: {event.start_time}")

            # Get markets
            markets = db.execute(
                select(Market).where(Market.event_id == event.id)
            ).scalars().all()

            print(f"   Markets: {len(markets)}")

            # Show match winner market odds
            match_winner_markets = [m for m in markets if 'result' in m.name.lower()]
            if match_winner_markets:
                market = match_winner_markets[0]
                print(f"\n   📈 {market.name}:")

                selections = db.execute(
                    select(Selection).where(Selection.market_id == market.id)
                ).scalars().all()

                for selection in selections:
                    odds = db.execute(
                        select(OddsSnapshot).where(
                            OddsSnapshot.selection_id == selection.id,
                            OddsSnapshot.is_current == True
                        )
                    ).scalars().first()

                    if odds:
                        bookmaker = db.get(Bookmaker, odds.bookmaker_id)
                        print(f"      {selection.name}: {odds.decimal_odds} ({bookmaker.code if bookmaker else 'Unknown'})")

            print()

        # Summary
        odds_count = db.execute(select(OddsSnapshot)).scalars().all()
        print(f"\n📊 Database Summary:")
        print(f"   Events: {len(events)}")
        print(f"   Total Odds: {len(odds_count)}")
        print(f"   Markets: {db.execute(select(Market)).scalars().all().__len__()}")

        print("\n" + "=" * 80)

    finally:
        db.close()


if __name__ == "__main__":
    test_query_odds()
