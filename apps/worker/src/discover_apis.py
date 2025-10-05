"""
API Discovery Script for TAB and Ladbrokes

This script helps identify the actual API endpoints used by bookmaker websites.

Usage:
    python discover_apis.py tab
    python discover_apis.py ladbrokes

Instructions:
1. Open browser devtools (F12) on the bookmaker website
2. Go to Network tab
3. Filter for XHR/Fetch requests
4. Navigate to a sport (e.g., AFL)
5. Look for JSON responses containing odds data
6. Copy the request URL and inspect the response structure
7. Update the scrapers with the actual endpoints

Common patterns to look for:
- /api/... endpoints
- GraphQL endpoints (/graphql)
- WebSocket connections for live odds
- JSON responses with odds arrays
"""
import asyncio
import httpx
import json
from datetime import datetime


class APIDiscovery:
    """Helper class to test and discover bookmaker APIs"""

    def __init__(self, bookmaker: str):
        self.bookmaker = bookmaker
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-AU,en;q=0.9",
        }

    async def test_endpoint(self, url: str, method: str = "GET", json_body: dict = None):
        """Test an API endpoint and print response"""
        print(f"\n{'='*80}")
        print(f"Testing: {method} {url}")
        print(f"{'='*80}")

        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    response = await client.get(url, headers=self.headers, timeout=10)
                else:
                    response = await client.post(url, headers=self.headers, json=json_body, timeout=10)

                print(f"Status: {response.status_code}")
                print(f"Headers: {dict(response.headers)}\n")

                if response.status_code == 200:
                    try:
                        data = response.json()
                        print("Response (formatted):")
                        print(json.dumps(data, indent=2)[:2000])  # First 2000 chars
                        print(f"\n... (truncated, total length: {len(json.dumps(data))})")

                        # Analyze structure
                        self.analyze_structure(data)
                    except:
                        print("Response (text):")
                        print(response.text[:1000])
                else:
                    print(f"Error: {response.text}")

            except Exception as e:
                print(f"Error: {e}")

    def analyze_structure(self, data: dict | list):
        """Analyze JSON structure to find odds data"""
        print(f"\n{'='*80}")
        print("Structure Analysis:")
        print(f"{'='*80}")

        if isinstance(data, dict):
            print(f"Top-level keys: {list(data.keys())}")

            # Look for common patterns
            for key in ["events", "meetings", "markets", "data", "result", "response"]:
                if key in data:
                    print(f"\nFound '{key}' with {len(data[key]) if isinstance(data[key], list) else 'object'}")

                    if isinstance(data[key], list) and len(data[key]) > 0:
                        print(f"First item structure: {list(data[key][0].keys()) if isinstance(data[key][0], dict) else 'not a dict'}")

        elif isinstance(data, list) and len(data) > 0:
            print(f"List with {len(data)} items")
            if isinstance(data[0], dict):
                print(f"First item keys: {list(data[0].keys())}")

    async def discover_tab(self):
        """Discover TAB API endpoints"""
        print("\n" + "="*80)
        print("TAB API Discovery")
        print("="*80)
        print("\nKnown TAB patterns:")
        print("- Base: https://api.beta.tab.com.au")
        print("- Sports: /v1/tab-info-service/sports/...")
        print("- Racing: /v1/tab-info-service/racing/...")
        print("\nTest some common endpoints:")

        test_endpoints = [
            "https://api.beta.tab.com.au/v1/tab-info-service/sports/Australian%20Rules/featured-competitions?jurisdiction=NSW",
            "https://api.beta.tab.com.au/v1/tab-info-service/sports/Rugby%20League/featured-competitions?jurisdiction=NSW",
        ]

        for endpoint in test_endpoints:
            await self.test_endpoint(endpoint)
            await asyncio.sleep(2)

    async def discover_ladbrokes(self):
        """Discover Ladbrokes API endpoints"""
        print("\n" + "="*80)
        print("Ladbrokes API Discovery")
        print("="*80)
        print("\nKnown Ladbrokes patterns:")
        print("- May use GraphQL")
        print("- May use REST API")
        print("- Check network tab on ladbrokes.com.au")
        print("\nManual steps required:")
        print("1. Open https://www.ladbrokes.com.au/sports/australian-rules")
        print("2. Open DevTools (F12) > Network tab")
        print("3. Filter for 'XHR' or 'Fetch'")
        print("4. Look for JSON responses with odds data")
        print("5. Copy the Request URL and update ladbrokes_scraper.py")

    async def run(self):
        """Run discovery based on bookmaker"""
        if self.bookmaker == "tab":
            await self.discover_tab()
        elif self.bookmaker == "ladbrokes":
            await self.discover_ladbrokes()
        else:
            print(f"Unknown bookmaker: {self.bookmaker}")
            print("Supported: tab, ladbrokes")


async def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python discover_apis.py <bookmaker>")
        print("Bookmakers: tab, ladbrokes")
        return

    bookmaker = sys.argv[1].lower()
    discovery = APIDiscovery(bookmaker)
    await discovery.run()


if __name__ == "__main__":
    asyncio.run(main())
