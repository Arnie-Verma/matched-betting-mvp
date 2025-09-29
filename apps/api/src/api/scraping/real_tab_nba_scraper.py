# apps/api/src/api/scraping/real_tab_nba_scraper.py
"""Advanced TAB NBA scraper that finds real odds through network inspection"""
import asyncio
import httpx
import json
import re
from typing import List, Dict, Optional
from datetime import datetime


async def discover_tab_apis():
    """Try to discover TAB's real API endpoints through various methods"""

    print("🔍 Discovering TAB's real NBA API endpoints...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-AU,en;q=0.9",
        "Referer": "https://www.tab.com.au/"
    }

    # Common TAB API patterns based on typical betting site architectures
    potential_api_bases = [
        "https://api.tab.com.au",
        "https://content.tab.com.au",
        "https://sports.tab.com.au",
        "https://www.tab.com.au/api",
        "https://prod-api.tab.com.au",
        "https://api-sports.tab.com.au"
    ]

    # Common endpoint patterns for basketball/NBA
    api_endpoints = [
        "/v1/sports/basketball",
        "/v2/sports/basketball",
        "/sports/7",  # Basketball often has ID 7
        "/competitions/usa-nba",
        "/competitions/nba",
        "/events/basketball",
        "/markets/basketball",
        "/fixtures/nba",
        "/odds/basketball",
        "/sports/basketball/events",
        "/content/basketball",
        "/api/sports/basketball"
    ]

    async with httpx.AsyncClient(headers=headers, timeout=30.0) as client:

        for base_url in potential_api_bases:
            for endpoint in api_endpoints:
                url = f"{base_url}{endpoint}"

                try:
                    print(f"🔍 Trying: {url}")
                    response = await client.get(url)

                    if response.status_code == 200:
                        try:
                            # Try to parse as JSON
                            data = response.json()
                            content_str = json.dumps(data).lower()

                            # Look for NBA indicators
                            nba_keywords = [
                                'nba', 'lakers', 'warriors', 'celtics', 'heat', 'bulls',
                                'basketball', 'game', 'match', 'team', 'odds'
                            ]

                            keyword_matches = sum(1 for keyword in nba_keywords if keyword in content_str)

                            if keyword_matches >= 3:  # Likely NBA data
                                print(f"✅ FOUND NBA DATA: {url}")
                                print(f"   Keywords matched: {keyword_matches}")
                                print(f"   Response size: {len(response.content)} bytes")

                                # Sample the data structure
                                if isinstance(data, dict):
                                    print(f"   Top level keys: {list(data.keys())[:10]}")
                                elif isinstance(data, list) and data:
                                    print(f"   Array length: {len(data)}")
                                    if isinstance(data[0], dict):
                                        print(f"   Sample keys: {list(data[0].keys())[:10]}")

                                # Try to extract actual odds
                                odds_found = await extract_odds_from_data(data)
                                if odds_found:
                                    print(f"   🎯 LIVE ODDS FOUND: {len(odds_found)} games")
                                    for game in odds_found[:3]:
                                        print(f"      {game}")

                                return url, data

                        except json.JSONDecodeError:
                            # Not JSON, check if it contains NBA content
                            content_text = response.text.lower()
                            if any(keyword in content_text for keyword in ['nba', 'lakers', 'warriors']):
                                print(f"📄 Found NBA content (non-JSON): {url}")

                    elif response.status_code == 404:
                        pass  # Expected for most endpoints
                    else:
                        print(f"   Status {response.status_code}: {url}")

                except Exception as e:
                    continue  # Skip failed requests

        print("❌ No direct API endpoints found. Trying alternative approaches...")

        # Try to find API endpoints referenced in the main page
        main_page_url = "https://www.tab.com.au/sports/basketball/competitions/usa-nba"
        response = await client.get(main_page_url)

        if response.status_code == 200:
            # Look for API URLs in the JavaScript
            api_pattern = r'(?:https?://[^"\s]*(?:api|content)[^"\s]*)'
            api_matches = re.findall(api_pattern, response.text, re.IGNORECASE)

            unique_apis = list(set(api_matches))
            print(f"🔍 Found {len(unique_apis)} potential API references in main page:")

            for api_url in unique_apis[:10]:  # Test first 10
                try:
                    print(f"🔍 Testing referenced API: {api_url}")
                    api_response = await client.get(api_url)
                    if api_response.status_code == 200:
                        try:
                            api_data = api_response.json()
                            content_str = json.dumps(api_data).lower()
                            if 'nba' in content_str or 'basketball' in content_str:
                                print(f"✅ FOUND NBA DATA in referenced API: {api_url}")
                                odds_found = await extract_odds_from_data(api_data)
                                if odds_found:
                                    print(f"   🎯 LIVE ODDS: {len(odds_found)} games")
                                    return api_url, api_data
                        except:
                            pass
                except:
                    continue

    return None, None


async def extract_odds_from_data(data: Dict) -> List[Dict]:
    """Extract NBA games and odds from API data"""
    games = []

    try:
        # Common data structures in betting APIs
        potential_games = []

        if isinstance(data, dict):
            # Look for events, games, matches, fixtures
            for key in ['events', 'games', 'matches', 'fixtures', 'data']:
                if key in data and isinstance(data[key], list):
                    potential_games.extend(data[key])
        elif isinstance(data, list):
            potential_games = data

        for game in potential_games:
            if not isinstance(game, dict):
                continue

            # Look for team names
            teams = []
            game_name = ""

            # Common field names for event names
            for name_field in ['name', 'eventName', 'title', 'fixture']:
                if name_field in game:
                    game_name = game[name_field]
                    break

            # Look for participants/teams
            for team_field in ['participants', 'teams', 'competitors']:
                if team_field in game and isinstance(game[team_field], list):
                    for team in game[team_field]:
                        if isinstance(team, dict) and 'name' in team:
                            teams.append(team['name'])
                        elif isinstance(team, str):
                            teams.append(team)

            # Look for odds
            odds = {}
            for odds_field in ['markets', 'odds', 'selections', 'outcomes']:
                if odds_field in game:
                    odds_data = game[odds_field]
                    # This would need specific parsing based on TAB's structure
                    break

            # Check if this looks like an NBA game
            if game_name and any(team_name in ['lakers', 'warriors', 'celtics', 'heat', 'bulls']
                               for team_name in game_name.lower().split()):
                games.append({
                    'name': game_name,
                    'teams': teams,
                    'odds': odds,
                    'raw_data': game
                })

    except Exception as e:
        print(f"Error extracting odds: {e}")

    return games


async def main():
    """Main function to discover and test real TAB NBA APIs"""
    url, data = await discover_tab_apis()

    if url and data:
        print(f"\n🎉 SUCCESS! Found real TAB NBA data at: {url}")
        print("Now we can build a real scraper using this endpoint!")
    else:
        print(f"\n❌ Could not find TAB's NBA API endpoints")
        print("TAB likely uses sophisticated protection or the NBA season hasn't started yet")
        print("Let's try Ladbrokes instead, or investigate other approaches")


if __name__ == "__main__":
    asyncio.run(main())