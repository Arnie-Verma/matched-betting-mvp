# apps/api/src/api/scraping/test_tab_scraper.py
"""Test the real TAB scraper"""
import asyncio
from sqlalchemy.orm import Session
from api.core.database import SessionLocal
from api.models import Bookmaker
from api.scraping.adapters.tab_api_scraper import TABAPIScraper


async def test_tab_scraper():
    """Test the TAB scraper with real data"""
    print("🚀 Testing TAB Scraper...")

    # Get database session
    db = SessionLocal()

    try:
        # Get TAB bookmaker from database
        tab_bookmaker = db.query(Bookmaker).filter(Bookmaker.code == "tab").first()
        if not tab_bookmaker:
            print("❌ TAB bookmaker not found in database")
            return

        print(f"📊 Found TAB bookmaker: {tab_bookmaker.name}")

        # Create scraper instance
        async with TABAPIScraper(tab_bookmaker, db) as scraper:
            print("🔍 Running NBL Head-to-Head scrape...")

            # Run the scrape
            result = await scraper.scrape_nbl_head_to_head()

            # Display results
            print(f"\n📋 Scrape Results:")
            print(f"Status: {result.status}")
            print(f"Odds Count: {result.odds_count}")
            print(f"Message: {result.message}")
            print(f"Processing Time: {result.processing_time_ms}ms")
            print(f"Confidence Score: {result.confidence_score}")

            if result.raw_data:
                print(f"Raw Data Sample: {str(result.raw_data)[:200]}...")

            # Get scraper info
            info = scraper.get_scraper_info()
            print(f"\n📋 Scraper Info:")
            for key, value in info.items():
                print(f"{key}: {value}")

    except Exception as e:
        print(f"❌ Error testing TAB scraper: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_tab_scraper())