# apps/api/src/api/scraping/inspect_ladbrokes_nba.py
"""Inspect Ladbrokes NBA odds structure"""
import asyncio
import httpx
from bs4 import BeautifulSoup
import re
import json


async def inspect_ladbrokes_nba():
    """Inspect Ladbrokes NBA page for real odds"""

    ladbrokes_urls = [
        "https://www.ladbrokes.com.au/sports/basketball/usa/nba",
        "https://www.ladbrokes.com.au/sports/basketball",
        "https://www.ladbrokes.com.au/sports/basketball/nba",
        "https://www.ladbrokes.com.au/basketball"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-AU,en;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive"
    }

    async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
        for url in ladbrokes_urls:
            try:
                print(f"🔍 Checking Ladbrokes: {url}")
                response = await client.get(url)

                print(f"Status: {response.status_code}")
                print(f"Content Length: {len(response.content)} bytes")

                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')

                    # Check title
                    title = soup.find('title')
                    if title:
                        print(f"📰 Title: {title.get_text()}")

                    # Look for NBA teams
                    content_text = response.text.lower()
                    nba_teams = [
                        'lakers', 'warriors', 'celtics', 'heat', 'bulls', 'knicks',
                        'nets', 'clippers', 'suns', 'nuggets', 'bucks', 'mavs'
                    ]

                    found_teams = [team for team in nba_teams if team in content_text]
                    print(f"🏀 NBA teams found: {found_teams}")

                    # Look for odds patterns
                    odds_patterns = [
                        r'\b[12]\.\d{2}\b',  # 1.85, 2.30 etc
                        r'\b\d+/\d+\b',     # Fractional odds like 5/4
                        r'data-price',       # Price attributes
                        r'price.*\d\.\d{2}', # Price with decimal
                    ]

                    total_odds = 0
                    for pattern in odds_patterns:
                        matches = re.findall(pattern, response.text)
                        if matches:
                            total_odds += len(matches)
                            print(f"📊 Found {len(matches)} '{pattern}' matches: {matches[:5]}")

                    # Look for betting-specific elements
                    betting_selectors = [
                        '[class*="odds"]',
                        '[class*="price"]',
                        '[class*="market"]',
                        '[class*="selection"]',
                        '[data-price]',
                        '.bet-button',
                        '.outcome'
                    ]

                    for selector in betting_selectors:
                        elements = soup.select(selector)
                        if elements:
                            print(f"🎯 Found {len(elements)} elements with selector '{selector}'")
                            for elem in elements[:3]:
                                text = elem.get_text().strip()[:50]
                                classes = elem.get('class', [])
                                print(f"   - {elem.name} class={classes} text='{text}'")

                    # Check for JSON data
                    scripts = soup.find_all('script')
                    json_found = 0

                    for script in scripts:
                        if script.string:
                            try:
                                # Look for JSON objects
                                json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                                matches = re.findall(json_pattern, script.string)

                                for match in matches:
                                    try:
                                        data = json.loads(match)
                                        json_str = json.dumps(data).lower()
                                        if any(team in json_str for team in nba_teams[:5]):
                                            json_found += 1
                                            if json_found <= 3:  # Show first 3
                                                print(f"📦 NBA JSON data found: {str(data)[:200]}...")
                                    except:
                                        continue
                            except:
                                continue

                    print(f"📊 Summary for {url}:")
                    print(f"  - NBA teams: {len(found_teams)}")
                    print(f"  - Odds patterns: {total_odds}")
                    print(f"  - JSON objects with NBA data: {json_found}")
                    print("-" * 80)

                else:
                    print(f"❌ Failed: {response.status_code}")

            except Exception as e:
                print(f"❌ Error with {url}: {e}")
                continue

    # Also try direct API discovery for Ladbrokes
    print("\n🔍 Trying Ladbrokes API endpoints...")
    ladbrokes_api_bases = [
        "https://api.ladbrokes.com.au",
        "https://www.ladbrokes.com.au/api",
        "https://sports.ladbrokes.com.au"
    ]

    api_endpoints = [
        "/sports/basketball",
        "/basketball/nba",
        "/api/sports/basketball",
        "/odds/basketball",
        "/fixtures/basketball"
    ]

    for base_url in ladbrokes_api_bases:
        for endpoint in api_endpoints:
            try:
                url = f"{base_url}{endpoint}"
                print(f"🔍 Trying: {url}")

                response = await client.get(url)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        json_str = json.dumps(data).lower()
                        if any(team in json_str for team in nba_teams[:5]):
                            print(f"✅ FOUND LADBROKES NBA API: {url}")
                            print(f"   Sample data: {str(data)[:300]}...")
                            return url, data
                    except:
                        content_lower = response.text.lower()
                        if any(team in content_lower for team in nba_teams[:5]):
                            print(f"📄 Found NBA content: {url}")

            except Exception as e:
                continue

    print("🏁 Ladbrokes inspection complete")


if __name__ == "__main__":
    asyncio.run(inspect_ladbrokes_nba())