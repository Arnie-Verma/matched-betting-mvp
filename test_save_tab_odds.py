"""Test scraping TAB and saving to database"""
import asyncio
import sys
sys.path.insert(0, "apps/worker/src")
sys.path.insert(0, "apps/api/src")

from scrapers.tab_scraper import TABScraper
from jobs.save_odds import save_scrape_result_to_db


async def test_tab_scrape_and_save():
    """Scrape TAB odds and save to database"""
    print("🔍 Testing TAB Scraper + Database Save...")
    print("=" * 80)

    # Step 1: Scrape TAB odds
    print("\n📊 Step 1: Scraping TAB for EPL odds...")
    scraper = TABScraper()
    result = await scraper.scrape_sport('soccer', limit=2)  # Just 2 events for testing

    print(f"✅ Scrape completed:")
    print(f"   Status: {result.status}")
    print(f"   Events: {result.events_scraped}")
    print(f"   Odds: {result.odds_scraped}")
    print(f"   Errors: {len(result.errors)}")

    if result.events:
        print(f"\n📋 Scraped Events:")
        for event in result.events:
            print(f"   - {event.name} ({event.start_time})")
            print(f"     Odds: {len(event.odds)}")

    # Step 2: Save to database
    print(f"\n💾 Step 2: Saving to database...")
    try:
        stats = save_scrape_result_to_db(result)

        print(f"✅ Database save completed:")
        print(f"   Events saved: {stats['events_saved']}")
        print(f"   Odds saved: {stats['odds_saved']}")
        print(f"   Errors: {stats['errors']}")

    except Exception as e:
        print(f"❌ Database save failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("✅ Test completed successfully!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_tab_scrape_and_save())
    sys.exit(0 if success else 1)
