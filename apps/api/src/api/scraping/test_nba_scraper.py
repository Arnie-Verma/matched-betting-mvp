# apps/api/src/api/scraping/test_nba_scraper.py
"""Test the NBA scraper"""
import asyncio
from sqlalchemy.orm import Session
from api.core.database import SessionLocal
from api.models import Bookmaker
from api.scraping.adapters.tab_nba_scraper import TABNBAScraper


async def test_nba_scraper():
    """Test the TAB NBA scraper with real data"""
    print("🏀 Testing TAB NBA Scraper...")

    db = SessionLocal()

    try:
        # Get TAB bookmaker
        tab_bookmaker = db.query(Bookmaker).filter(Bookmaker.code == "tab").first()
        if not tab_bookmaker:
            print("❌ TAB bookmaker not found in database")
            return

        print(f"📊 Found TAB bookmaker: {tab_bookmaker.name}")

        # Create NBA scraper instance
        async with TABNBAScraper(tab_bookmaker, db) as scraper:
            print("🔍 Running NBA Head-to-Head scrape...")

            # Run the scrape
            result = await scraper.scrape_nba_head_to_head()

            # Display results
            print(f"\n📋 NBA Scrape Results:")
            print(f"Status: {result.status}")
            print(f"Odds Count: {result.odds_count}")
            print(f"Message: {result.message}")
            print(f"Processing Time: {result.processing_time_ms}ms")
            print(f"Confidence Score: {result.confidence_score}")

            # Get scraper info
            info = scraper.get_scraper_info()
            print(f"\n📋 NBA Scraper Info:")
            for key, value in info.items():
                print(f"{key}: {value}")

            print(f"\n🎯 Sample NBA matchups that would be scraped:")
            print("- Los Angeles Lakers vs Golden State Warriors")
            print("- Boston Celtics vs Miami Heat")
            print("- Denver Nuggets vs Phoenix Suns")
            print("- Milwaukee Bucks vs Philadelphia 76ers")

    except Exception as e:
        print(f"❌ Error testing NBA scraper: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_nba_scraper())