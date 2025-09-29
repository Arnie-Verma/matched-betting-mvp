# apps/api/src/api/scraping/inspect_tab_nba_live.py
"""Inspect TAB's live NBA odds structure to build real parser"""
import asyncio
import httpx
from bs4 import BeautifulSoup
import json
import re


async def inspect_tab_nba_live():
    """Inspect TAB's current NBA page for real odds"""

    nba_urls = [
        "https://www.tab.com.au/sports/basketball/competitions/usa-nba",
        "https://www.tab.com.au/sports/basketball",
        "https://www.tab.com.au/sports/basketball/usa-nba"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-AU,en;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

    async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
        for url in nba_urls:
            try:
                print(f"🔍 Checking: {url}")
                response = await client.get(url)

                print(f"Status: {response.status_code}")
                print(f"Content Length: {len(response.content)} bytes")

                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')

                    # Save full HTML for analysis
                    filename = f"/tmp/tab_nba_live_{url.split('/')[-1]}.html"
                    try:
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(response.text)
                        print(f"💾 Saved HTML to {filename}")
                    except:
                        pass

                    # Look for NBA team names in content
                    content_text = response.text.lower()
                    nba_teams = [
                        'lakers', 'warriors', 'celtics', 'heat', 'bulls', 'knicks',
                        'nets', 'clippers', 'suns', 'nuggets', 'bucks', 'mavs',
                        'pistons', 'hawks', 'magic', 'kings', 'spurs', 'jazz'
                    ]

                    found_teams = [team for team in nba_teams if team in content_text]
                    print(f"🏀 NBA teams found: {found_teams[:10]}")

                    # Look for odds patterns
                    odds_patterns = [
                        r'\b[12]\.\d{2,3}\b',  # Decimal odds like 1.85, 2.30
                        r'\$\d+\.\d{2}',       # Dollar amounts
                        r'data-price["\s]*=',  # Price attributes
                        r'odds["\s]*:',        # Odds in JSON
                    ]

                    total_odds_found = 0
                    for pattern in odds_patterns:
                        matches = re.findall(pattern, response.text)
                        total_odds_found += len(matches)
                        if matches:
                            print(f"📊 Found {len(matches)} matches for pattern {pattern}: {matches[:5]}")

                    # Look for specific betting elements
                    betting_classes = [
                        'price', 'odd', 'bet', 'market', 'selection', 'outcome',
                        'event', 'fixture', 'match', 'game'
                    ]

                    for class_name in betting_classes:
                        elements = soup.find_all(attrs={"class": lambda x: x and class_name in str(x).lower()})
                        if elements:
                            print(f"🎯 Found {len(elements)} elements with '{class_name}' in class")
                            # Print sample elements
                            for i, elem in enumerate(elements[:3]):
                                print(f"  - {elem.name} class='{elem.get('class')}' text='{elem.get_text().strip()[:50]}'")

                    # Look for JSON data in script tags
                    scripts = soup.find_all('script')
                    json_data_found = []

                    for script in scripts:
                        if script.string and ('nba' in script.string.lower() or 'lakers' in script.string.lower() or 'odds' in script.string.lower()):
                            # Try to extract JSON objects
                            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
                            matches = re.findall(json_pattern, script.string)

                            for match in matches[:3]:  # Only check first 3 matches
                                try:
                                    data = json.loads(match)
                                    json_str = json.dumps(data).lower()
                                    if any(team in json_str for team in nba_teams[:5]):
                                        json_data_found.append(match[:200])
                                except:
                                    continue

                    if json_data_found:
                        print(f"📦 Found {len(json_data_found)} JSON objects with NBA data:")
                        for i, data in enumerate(json_data_found):
                            print(f"  JSON {i+1}: {data[:100]}...")

                    # Check title and description for context
                    title = soup.find('title')
                    if title:
                        print(f"📰 Page title: {title.get_text()}")

                    print(f"📊 Summary for {url}:")
                    print(f"  - NBA teams mentioned: {len(found_teams)}")
                    print(f"  - Potential odds patterns: {total_odds_found}")
                    print(f"  - JSON data objects: {len(json_data_found)}")
                    print("-" * 60)

                else:
                    print(f"❌ Failed: {response.status_code}")
                    print(f"Headers: {dict(response.headers)}")

            except Exception as e:
                print(f"❌ Error with {url}: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_tab_nba_live())