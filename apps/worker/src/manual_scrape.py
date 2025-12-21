#!/usr/bin/env python3
"""
Manual script to trigger TAB and Betfair scraping.
Run this inside the mb_api container.
"""
import asyncio
import sys
sys.path.insert(0, "/workspace/apps/worker/src")

from jobs.scrape_service import trigger_scrape

async def main():
    print("=== Starting manual scrape ===")
    print("Scraping all bookmakers for all sports...")

    result = await trigger_scrape(sport="all", limit=None)  # Scrape all sports

    print("\n=== Scrape Complete ===")
    print(f"Success: {result['success']}")
    print(f"Bookmakers scraped: {result['bookmakers_scraped']}/{result['total_bookmakers']}")
    print(f"Events scraped: {result['events_scraped']}")
    print(f"Odds scraped: {result['odds_scraped']}")
    print(f"Odds saved to DB: {result['odds_saved']}")

    if result['errors']:
        print(f"\nErrors ({len(result['errors'])}):")
        for error in result['errors'][:5]:  # Show first 5
            print(f"  - {error}")

    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(main())
