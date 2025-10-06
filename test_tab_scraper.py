"""Test TAB scraper with real EPL data"""
import asyncio
import sys
sys.path.insert(0, "apps/worker/src")
sys.path.insert(0, "apps/api/src")

from scrapers.tab_scraper import TABScraper


async def test_tab_scraper():
    """Test TAB scraper for EPL"""
    print("🔍 Testing TAB Scraper for EPL...")
    print("-" * 60)

    scraper = TABScraper()
    result = await scraper.scrape_sport('soccer', limit=5)  # Test with 5 matches

    print(f"\n📊 Scrape Results:")
    print(f"Status: {result.status}")
    print(f"Events Scraped: {result.events_scraped}")
    print(f"Odds Scraped: {result.odds_scraped}")
    print(f"Errors: {result.errors}")

    if result.events:
        print(f"\n⚽ ALL EVENTS SCRAPED:")
        print("=" * 80)
        for i, event in enumerate(result.events, 1):
            print(f"\n{i}. {event.name}")
            print(f"   Start: {event.start_time}")
            print(f"   Teams: {event.home_team} vs {event.away_team}")
            print(f"   Odds Count: {len(event.odds)}")

            # Show match winner odds if available
            match_winner_odds = [o for o in event.odds if 'result' in o.market_name.lower()][:3]
            if match_winner_odds:
                print(f"   Match Winner Odds:")
                for odd in match_winner_odds:
                    print(f"      {odd.selection_name}: {odd.decimal_odds}")

        print(f"\n" + "=" * 80)
        print(f"\n💰 DETAILED SAMPLE - First Event Markets:")
        event = result.events[0]

        # Group odds by market type
        markets_summary = {}
        for odd in event.odds:
            market = odd.market_name
            if market not in markets_summary:
                markets_summary[market] = []
            markets_summary[market].append(f"{odd.selection_name}: {odd.decimal_odds}")

        print(f"\nTotal Markets: {len(markets_summary)}")
        print(f"\nMarket Types Found:")
        for i, (market_name, selections) in enumerate(list(markets_summary.items())[:5], 1):
            print(f"\n{i}. {market_name}")
            for sel in selections[:3]:  # Show first 3 selections per market
                print(f"   - {sel}")

    print("\n" + "=" * 60)
    return result


if __name__ == "__main__":
    result = asyncio.run(test_tab_scraper())

    if result.status == "success":
        print("✅ TAB scraper test PASSED!")
        sys.exit(0)
    else:
        print("❌ TAB scraper test FAILED!")
        sys.exit(1)
