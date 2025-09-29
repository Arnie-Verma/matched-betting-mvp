# apps/api/src/api/scraping/inspect_tab.py
"""Inspect TAB's NBL page structure to build real scraper"""
import asyncio
import httpx
from bs4 import BeautifulSoup


async def inspect_tab_nbl():
    """Inspect TAB's NBL page structure"""

    # TAB's NBL URL
    url = "https://www.tab.com.au/sports/basketball/competitions/australia-nbl"

    # Realistic headers to avoid immediate blocking
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-AU,en;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none"
    }

    async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
        try:
            print(f"🔍 Inspecting TAB NBL page: {url}")

            response = await client.get(url)
            print(f"📊 Status Code: {response.status_code}")
            print(f"📊 Content Length: {len(response.content)} bytes")

            if response.status_code == 200:
                # Parse HTML
                soup = BeautifulSoup(response.content, 'html.parser')

                # Look for common betting elements
                print("\n🔍 Searching for betting elements...")

                # Look for odds containers
                odds_elements = soup.find_all(['div', 'span'], class_=lambda x: x and any(
                    keyword in x.lower() for keyword in ['odd', 'price', 'bet', 'market', 'event']
                ))
                print(f"📊 Found {len(odds_elements)} potential odds elements")

                # Look for team/event names
                event_elements = soup.find_all(['div', 'span', 'h1', 'h2', 'h3'], string=lambda text:
                    text and any(team in text for team in ['United', 'Kings', 'Wildcats', 'vs', 'v '])
                )
                print(f"📊 Found {len(event_elements)} potential event elements")

                # Look for JSON data (many sites embed odds in JSON)
                scripts = soup.find_all('script')
                json_scripts = [script for script in scripts if script.string and
                               any(keyword in script.string for keyword in ['odds', 'markets', 'events', 'basketball'])]
                print(f"📊 Found {len(json_scripts)} scripts with potential JSON data")

                # Print some sample content for analysis
                print("\n📋 Sample HTML structure:")
                print("=" * 50)

                # Print first few odds-related elements
                for i, element in enumerate(odds_elements[:3]):
                    print(f"Odds Element {i+1}: {element.name} class='{element.get('class')}' text='{element.get_text().strip()[:100]}'")

                # Print first few event-related elements
                for i, element in enumerate(event_elements[:3]):
                    print(f"Event Element {i+1}: {element.name} text='{element.get_text().strip()[:100]}'")

                # Save full HTML for detailed analysis
                try:
                    with open('/tmp/tab_nbl_page.html', 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    print(f"\n💾 Full HTML saved to /tmp/tab_nbl_page.html")
                except Exception as e:
                    print(f"⚠️  Could not save HTML file: {e}")

                # Also print some raw HTML structure
                print(f"\n📄 First 500 chars of HTML:")
                print(response.text[:500])
                print("...")

                # Look for data attributes and modern web app patterns
                print(f"\n🔍 Looking for modern web app patterns...")

                # Check if it's a React/Vue/Angular app
                content_lower = response.text.lower()
                if 'react' in content_lower or 'vue' in content_lower or 'angular' in content_lower or 'ng-app' in content_lower:
                    print("📱 Detected modern JS framework - may need browser automation")

                # Look for API endpoints in scripts
                api_patterns = ['api/', '/api', 'endpoint', 'fetch(', 'axios']
                api_mentions = sum(1 for pattern in api_patterns if pattern in content_lower)
                print(f"🔗 Found {api_mentions} potential API references")

                # Check for data-* attributes
                data_attributes = soup.find_all(attrs=lambda x: x and any(key.startswith('data-') for key in x.keys()))
                print(f"📊 Found {len(data_attributes)} elements with data attributes")

                # Print title and meta description to understand page content
                title = soup.find('title')
                if title:
                    print(f"📰 Page title: {title.get_text().strip()}")

                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    print(f"📝 Meta description: {meta_desc.get('content', '')[:100]}")

                # Check if we're being redirected or see a landing page
                if 'coming soon' in content_lower or 'maintenance' in content_lower:
                    print("⚠️  Site may be in maintenance mode")

                if 'login' in content_lower or 'sign in' in content_lower:
                    print("🔐 May require authentication")

                # Look for specific NBL teams in content
                content_lower = response.text.lower()
                nbl_teams = ['melbourne united', 'sydney kings', 'perth wildcats', 'adelaide 36ers',
                            'brisbane bullets', 'cairns taipans', 'illawarra hawks', 'new zealand breakers',
                            'tasmania jackjumpers', 'south east melbourne phoenix']

                found_teams = [team for team in nbl_teams if team in content_lower]
                print(f"\n🏀 NBL teams found in content: {found_teams}")

                if found_teams:
                    print("✅ TAB page contains NBL data - we can build a parser!")
                else:
                    print("⚠️  No NBL teams found - may need to check URL or NBL season status")

            else:
                print(f"❌ Failed to access TAB page: {response.status_code}")
                print(f"Response headers: {dict(response.headers)}")

        except Exception as e:
            print(f"❌ Error inspecting TAB: {e}")


if __name__ == "__main__":
    asyncio.run(inspect_tab_nbl())