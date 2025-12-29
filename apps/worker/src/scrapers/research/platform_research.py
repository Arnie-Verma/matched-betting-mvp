"""
Platform API Research Script

Use this script to capture API patterns from new bookmaker platforms.
Run with Playwright to intercept network requests and discover API endpoints.

Usage:
    cd apps/worker
    python -m src.scrapers.research.platform_research --site tradie.bet --sport soccer

This will:
1. Launch a browser and navigate to the site
2. Capture all API responses
3. Save them to a JSON file for analysis
4. Print summary of discovered endpoints

Platforms to Research:
- Punterstech: tradie.bet, mintbet.com.au
- Generation Web: elitebet.com.au, winnersbet.com.au
- BetCloud: wellbet.com.au, betgalaxy.com.au
- BetMakers: realbookie.com.au, crossbet.com.au
"""

import asyncio
import json
import argparse
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from playwright.async_api import async_playwright, Response

# Platform configurations - URLs to test
PLATFORM_SITES = {
    # Punterstech Platform
    "punterstech": {
        "tradie.bet": {
            "base_url": "https://www.tradie.bet",
            "sport_urls": {
                "soccer": "/sports/soccer",
                "afl": "/sports/afl",
                "nrl": "/sports/nrl",
            }
        },
        "mintbet.com.au": {
            "base_url": "https://www.mintbet.com.au",
            "sport_urls": {
                "soccer": "/sports/soccer",
                "afl": "/sports/afl",
            }
        },
    },

    # Generation Web Platform
    "generation_web": {
        "elitebet.com.au": {
            "base_url": "https://www.elitebet.com.au",
            "sport_urls": {
                "soccer": "/sports/soccer",
                "racing": "/racing",
            }
        },
        "winnersbet.com.au": {
            "base_url": "https://www.winnersbet.com.au",
            "sport_urls": {
                "soccer": "/sports/soccer",
            }
        },
    },

    # BetCloud Platform
    "betcloud": {
        "wellbet.com.au": {
            "base_url": "https://www.wellbet.com.au",
            "sport_urls": {
                "soccer": "/sports/soccer",
                "afl": "/sports/afl",
            }
        },
        "betgalaxy.com.au": {
            "base_url": "https://www.betgalaxy.com.au",
            "sport_urls": {
                "soccer": "/sports/soccer",
            }
        },
    },

    # BetMakers Platform
    "betmakers": {
        "realbookie.com.au": {
            "base_url": "https://www.realbookie.com.au",
            "sport_urls": {
                "soccer": "/sports/soccer",
                "racing": "/racing",
            }
        },
        "crossbet.com.au": {
            "base_url": "https://www.crossbet.com.au",
            "sport_urls": {
                "soccer": "/sports/soccer",
            }
        },
    },
}


class PlatformResearcher:
    """Research tool for discovering bookmaker API patterns"""

    def __init__(self, output_dir: str = "research_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.captured_responses: List[Dict[str, Any]] = []

    async def research_site(
        self,
        site_domain: str,
        base_url: str,
        sport_path: str,
        wait_time: int = 10
    ) -> Dict[str, Any]:
        """
        Research a single site by capturing all API responses.

        Args:
            site_domain: Domain name for output file naming
            base_url: Full base URL (e.g., https://www.tradie.bet)
            sport_path: Path to sport page (e.g., /sports/soccer)
            wait_time: Seconds to wait for API responses

        Returns:
            Dict with discovered endpoints and sample responses
        """
        self.captured_responses = []
        full_url = f"{base_url}{sport_path}"

        print(f"\n{'='*60}")
        print(f"RESEARCHING: {full_url}")
        print(f"{'='*60}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-AU',
                timezone_id='Australia/Sydney'
            )

            page = await context.new_page()

            # Capture all responses
            async def handle_response(response: Response):
                try:
                    url = response.url
                    status = response.status
                    content_type = response.headers.get('content-type', '')

                    # Skip static assets
                    skip_extensions = ['.js', '.css', '.png', '.jpg', '.gif', '.svg', '.woff', '.ico']
                    if any(ext in url.lower() for ext in skip_extensions):
                        return

                    # Focus on JSON/API responses
                    is_json = 'application/json' in content_type
                    is_api = any(pattern in url.lower() for pattern in [
                        '/api/', '/v1/', '/v2/', '/graphql',
                        'event', 'market', 'odds', 'sport', 'competition',
                        'fixture', 'price', 'betting'
                    ])

                    if status == 200 and (is_json or is_api):
                        try:
                            body = await response.json()
                            self.captured_responses.append({
                                'url': url,
                                'status': status,
                                'content_type': content_type,
                                'body_preview': self._truncate_body(body),
                                'body_keys': list(body.keys()) if isinstance(body, dict) else None,
                                'body_length': len(json.dumps(body)) if body else 0,
                            })
                            print(f"  ✓ Captured: {url[:80]}...")
                        except:
                            # Not JSON, skip
                            pass
                except Exception as e:
                    pass

            page.on('response', lambda res: asyncio.create_task(handle_response(res)))

            try:
                print(f"\nNavigating to {full_url}...")
                await page.goto(full_url, wait_until='domcontentloaded', timeout=30000)
                print(f"Page loaded. Waiting {wait_time}s for API responses...")

                # Wait for API responses to arrive
                await asyncio.sleep(wait_time)

                # Try scrolling to trigger lazy loading
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            except Exception as e:
                print(f"Error navigating: {e}")

            finally:
                await context.close()
                await browser.close()

        # Analyze captured responses
        result = self._analyze_responses(site_domain, sport_path)
        self._save_results(site_domain, sport_path, result)

        return result

    def _truncate_body(self, body: Any, max_items: int = 3) -> Any:
        """Truncate large response bodies for preview"""
        if isinstance(body, dict):
            return {k: self._truncate_body(v, max_items) for k, v in list(body.items())[:10]}
        elif isinstance(body, list):
            return body[:max_items] if len(body) > max_items else body
        return body

    def _analyze_responses(self, site_domain: str, sport_path: str) -> Dict[str, Any]:
        """Analyze captured responses to identify patterns"""
        print(f"\n{'='*60}")
        print(f"ANALYSIS: {site_domain}")
        print(f"{'='*60}")

        if not self.captured_responses:
            print("No API responses captured!")
            return {"error": "No responses captured", "responses": []}

        # Group by URL pattern
        endpoint_groups = {}
        for resp in self.captured_responses:
            # Extract endpoint pattern (remove IDs, query params)
            url = resp['url']
            # Simplify URL for pattern matching
            pattern = url.split('?')[0]
            if pattern not in endpoint_groups:
                endpoint_groups[pattern] = []
            endpoint_groups[pattern].append(resp)

        print(f"\nDiscovered {len(endpoint_groups)} unique endpoints:")
        for pattern, responses in endpoint_groups.items():
            print(f"\n  Endpoint: {pattern}")
            print(f"    Count: {len(responses)}")
            if responses[0]['body_keys']:
                print(f"    Keys: {responses[0]['body_keys']}")
            print(f"    Size: {responses[0]['body_length']} bytes")

        # Look for odds-related endpoints
        odds_endpoints = [
            p for p in endpoint_groups.keys()
            if any(kw in p.lower() for kw in ['odds', 'price', 'market', 'event', 'fixture'])
        ]

        print(f"\n🎯 Likely odds-related endpoints:")
        for ep in odds_endpoints:
            print(f"    {ep}")

        return {
            "site": site_domain,
            "sport_path": sport_path,
            "timestamp": datetime.now().isoformat(),
            "total_responses": len(self.captured_responses),
            "endpoints": list(endpoint_groups.keys()),
            "odds_endpoints": odds_endpoints,
            "responses": self.captured_responses,
        }

    def _save_results(self, site_domain: str, sport_path: str, result: Dict):
        """Save research results to JSON file"""
        safe_sport = sport_path.replace('/', '_').strip('_')
        filename = f"{site_domain}_{safe_sport}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2, default=str)

        print(f"\n📁 Results saved to: {filepath}")


async def research_platform(platform: str):
    """Research all sites for a given platform"""
    if platform not in PLATFORM_SITES:
        print(f"Unknown platform: {platform}")
        print(f"Available: {list(PLATFORM_SITES.keys())}")
        return

    researcher = PlatformResearcher()
    sites = PLATFORM_SITES[platform]

    print(f"\n{'#'*60}")
    print(f"# PLATFORM RESEARCH: {platform.upper()}")
    print(f"# Sites: {list(sites.keys())}")
    print(f"{'#'*60}")

    for site_domain, config in sites.items():
        base_url = config['base_url']
        for sport, path in config['sport_urls'].items():
            try:
                await researcher.research_site(site_domain, base_url, path)
            except Exception as e:
                print(f"Error researching {site_domain}{path}: {e}")


async def research_single_site(site_url: str, sport_path: str = "/sports/soccer"):
    """Research a single site"""
    researcher = PlatformResearcher()

    # Parse domain from URL
    domain = site_url.replace('https://', '').replace('http://', '').split('/')[0]

    # Ensure URL has protocol
    if not site_url.startswith('http'):
        site_url = f"https://{site_url}"

    await researcher.research_site(domain, site_url.rstrip('/'), sport_path)


def main():
    parser = argparse.ArgumentParser(description='Research bookmaker platform APIs')
    parser.add_argument('--platform', type=str, help='Platform to research (punterstech, generation_web, betcloud, betmakers)')
    parser.add_argument('--site', type=str, help='Single site URL to research')
    parser.add_argument('--sport', type=str, default='/sports/soccer', help='Sport path (default: /sports/soccer)')

    args = parser.parse_args()

    if args.platform:
        asyncio.run(research_platform(args.platform))
    elif args.site:
        asyncio.run(research_single_site(args.site, args.sport))
    else:
        print("Usage:")
        print("  Research a platform:  python platform_research.py --platform punterstech")
        print("  Research a single site: python platform_research.py --site tradie.bet --sport /sports/soccer")
        print("\nAvailable platforms: punterstech, generation_web, betcloud, betmakers")


if __name__ == "__main__":
    main()
