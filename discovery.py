#!/usr/bin/env python3
"""
Comprehensive Bookmaker Platform Discovery Script

Discovers API patterns from major Australian bookmaker platforms
by intercepting network traffic with a headless browser.

Usage:
    python discovery.py --platform punterstech
    python discovery.py --site https://www.tradie.bet --sport /sports/soccer
"""

import asyncio
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

try:
    from playwright.async_api import async_playwright, Response
except ImportError:
    print("ERROR: playwright not installed. Install with: pip install playwright")
    print("Then run: playwright install chromium")
    exit(1)


class PlatformDiscovery:
    """Discovers API patterns from bookmaker platforms"""

    PLATFORMS = {
        "punterstech": {
            "sites": [
                ("TradieBET", "https://www.tradie.bet", "/sports/soccer"),
                ("MintBet", "https://www.mintbet.com.au", "/sports/soccer"),
            ]
        },
        "generation_web": {
            "sites": [
                ("EliteBet", "https://www.elitebet.com.au", ["/sports/soccer", "/sports/afl", "/sports/nrl"]),
                ("WinnersBet", "https://www.winnersbet.com.au", ["/sports/soccer", "/sports/afl", "/sports/nrl"]),
            ]
        },
        "betmakers": {
            "sites": [
                ("RealBookie", "https://www.realbookie.com.au", "/sports/soccer"),
                ("CrossBet", "https://www.crossbet.com.au", "/sports/soccer"),
            ]
        },
        "betcloud": {
            "sites": [
                ("WellBet", "https://www.wellbet.com.au", ["/sports/soccer", "/sports/afl", "/sports/nrl"]),
                ("BetGalaxy", "https://www.betgalaxy.com.au", ["/sports/soccer", "/sports/afl", "/sports/nrl"]),
            ]
        },
    }

    def __init__(self, output_dir: str = "discovery_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results = []

    async def research_site(self, name: str, base_url: str, sport_path) -> Dict[str, Any]:
        """
        Research a single site by capturing network requests.

        Args:
            name: Bookmaker name for logging
            base_url: Base URL of bookmaker (e.g., https://www.tradie.bet)
            sport_path: Path(s) to sports page (str or list of str)

        Returns:
            Dict with discovered endpoints and metadata
        """
        # Handle both single path (str) and multiple paths (list)
        if isinstance(sport_path, str):
            sport_paths = [sport_path]
        else:
            sport_paths = sport_path

        print(f"\n{'='*70}")
        print(f"🔍 RESEARCHING: {name}")
        print(f"{'='*70}")
        print(f"Sports paths: {', '.join(sport_paths)}")

        captured_responses = []
        api_endpoints = {}

        # Track endpoints per sport for better analysis
        endpoints_by_sport = {}

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

            # Create a shared async task queue for handling responses
            def create_response_handler(sport_name):
                """Factory function to create response handler with correct closure"""
                async def handler(response):
                    try:
                        url = response.url
                        status = response.status
                        content_type = response.headers.get('content-type', '')

                        # Skip static assets
                        skip_exts = ['.js', '.css', '.png', '.jpg', '.gif', '.svg', '.woff', '.ico']
                        if any(ext in url.lower() for ext in skip_exts):
                            return

                        # Focus on API/JSON - especially sports betting APIs
                        is_json = 'application/json' in content_type
                        is_api = any(p in url.lower() for p in [
                            '/api/', '/v1/', '/v2/', '/graphql',
                            'event', 'market', 'odds', 'sport', 'fixture', 'punter'
                        ])

                        # Special patterns for each platform
                        is_sports_betting_api = any(p in url.lower() for p in [
                            '/punter/sports',  # BetCloud pattern
                            '/sportutility',   # Generation Web pattern
                            '/api-events/public',  # Punterstech pattern
                        ])

                        if status == 200 and (is_json or is_api or is_sports_betting_api):
                            try:
                                body = await response.json()
                                endpoint = urlparse(url).path

                                # Track endpoint
                                if endpoint not in api_endpoints:
                                    api_endpoints[endpoint] = {
                                        'full_url': url,
                                        'method': response.request.method,
                                        'status': status,
                                        'content_type': content_type,
                                        'sample_keys': list(body.keys()) if isinstance(body, dict) else None,
                                        'response_size': len(json.dumps(body)),
                                        'sports_where_found': []
                                    }

                                # Track which sports this endpoint appears in
                                if sport_name not in api_endpoints[endpoint]['sports_where_found']:
                                    api_endpoints[endpoint]['sports_where_found'].append(sport_name)

                                captured_responses.append({
                                    'url': url,
                                    'endpoint': endpoint,
                                    'sport': sport_name,
                                    'status': status,
                                    'size': len(json.dumps(body)),
                                    'sample': self._truncate(body, max_depth=2),
                                })

                                print(f"    [{sport_name}] ✓ {endpoint[:50]:<50} ({len(json.dumps(body))} bytes)")
                            except:
                                pass
                    except Exception as e:
                        pass
                return handler

            # Research each sport path
            for sport_path in sport_paths:
                full_url = f"{base_url}{sport_path}"
                sport_name = sport_path.split('/')[-1] if '/' in sport_path else 'root'

                print(f"\n📱 Navigating to {sport_name.upper()}: {full_url}...")

                # Set response handler for this sport
                page.on('response', create_response_handler(sport_name))

                try:
                    await page.goto(full_url, wait_until='domcontentloaded', timeout=30000)
                    print(f"✓ Page loaded. Waiting 8s for API responses...")

                    await asyncio.sleep(8)

                    # Trigger lazy loading
                    print(f"📜 Scrolling to trigger lazy load...")
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(3)

                except Exception as e:
                    print(f"❌ Error navigating to {sport_name}: {e}")

            await context.close()
            await browser.close()

        # Analyze results
        print(f"\n{'='*70}")
        print(f"📊 ANALYSIS: {name}")
        print(f"{'='*70}")
        print(f"Total API responses captured: {len(captured_responses)}")
        print(f"Unique endpoints: {len(api_endpoints)}\n")

        print("🔗 Discovered Endpoints:")
        for endpoint, info in api_endpoints.items():
            print(f"\n  {endpoint}")
            print(f"    Full URL: {info['full_url']}")
            print(f"    Method: {info['method']}")
            print(f"    Response size: {info['response_size']} bytes")
            if info['sample_keys']:
                print(f"    Keys: {info['sample_keys']}")

        # Identify likely odds endpoints
        odds_endpoints = [
            e for e in api_endpoints.keys()
            if any(kw in e.lower() for kw in ['odds', 'price', 'market', 'event', 'fixture', 'sport'])
        ]

        print(f"\n🎯 Likely Odds-Related Endpoints:")
        for ep in odds_endpoints:
            print(f"    {ep}")

        result = {
            "bookmaker": name,
            "base_url": base_url,
            "sport_paths": sport_paths,
            "timestamp": datetime.now().isoformat(),
            "endpoints_captured": len(captured_responses),
            "unique_endpoints": len(api_endpoints),
            "endpoints": api_endpoints,
            "odds_endpoints": odds_endpoints,
            "endpoints_by_sport": {
                sport: [ep for ep, info in api_endpoints.items() if sport in info.get('sports_where_found', [])]
                for sport in set(r.get('sport', 'unknown') for r in captured_responses)
            },
            "sample_responses": captured_responses[:10],  # First 10 for analysis
        }

        self._save_results(name, result)
        return result

    def _truncate(self, obj: Any, max_depth: int = 2, depth: int = 0) -> Any:
        """Truncate nested objects for readability"""
        if depth >= max_depth:
            return "..."

        if isinstance(obj, dict):
            return {k: self._truncate(v, max_depth, depth+1) for k, v in list(obj.items())[:5]}
        elif isinstance(obj, list):
            return [self._truncate(item, max_depth, depth+1) for item in obj[:3]]
        return obj

    def _save_results(self, name: str, result: Dict):
        """Save research results to JSON"""
        filename = f"{name.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.output_dir / filename

        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2, default=str)

        print(f"\n💾 Results saved to: {filepath}")

    async def research_platform(self, platform: str):
        """Research all sites in a platform"""
        if platform not in self.PLATFORMS:
            print(f"❌ Unknown platform: {platform}")
            print(f"Available: {list(self.PLATFORMS.keys())}")
            return

        sites = self.PLATFORMS[platform]

        print(f"\n{'#'*70}")
        print(f"# 🏢 PLATFORM RESEARCH: {platform.upper()}")
        print(f"# Sites: {len(sites['sites'])}")
        print(f"{'#'*70}")

        for name, base_url, sport_paths in sites['sites']:
            try:
                result = await self.research_site(name, base_url, sport_paths)
                self.results.append(result)
            except Exception as e:
                print(f"❌ Error researching {name}: {e}")

    async def research_single_site(self, url: str, sport_path: str = "/sports/soccer"):
        """Research a single custom site"""
        # Extract domain for naming
        domain = urlparse(url).netloc.replace('www.', '')

        try:
            result = await self.research_site(domain, url.rstrip('/'), sport_path)
            self.results.append(result)
        except Exception as e:
            print(f"❌ Error researching {url}: {e}")

    def generate_summary(self):
        """Generate summary of all research"""
        print(f"\n\n{'='*70}")
        print(f"📈 DISCOVERY SUMMARY")
        print(f"{'='*70}\n")

        for result in self.results:
            print(f"✓ {result['bookmaker']}")
            print(f"  - Endpoints: {result['unique_endpoints']}")
            print(f"  - Responses: {result['endpoints_captured']}")
            print(f"  - Likely odds endpoints: {len(result['odds_endpoints'])}")

        print(f"\n{'='*70}")
        print(f"All discovery files saved to: {self.output_dir}")
        print(f"{'='*70}\n")


async def main():
    parser = argparse.ArgumentParser(description='Discover bookmaker platform APIs')
    parser.add_argument('--platform', type=str, help='Platform to research (punterstech, generation_web, betmakers, betcloud)')
    parser.add_argument('--site', type=str, help='Single site URL to research')
    parser.add_argument('--sport', type=str, default='/sports/soccer', help='Sport path (default: /sports/soccer)')

    args = parser.parse_args()

    discoverer = PlatformDiscovery()

    if args.platform:
        await discoverer.research_platform(args.platform)
    elif args.site:
        await discoverer.research_single_site(args.site, args.sport)
    else:
        print("Usage:")
        print("  Research a platform:   python discovery.py --platform punterstech")
        print("  Research a single site: python discovery.py --site https://www.tradie.bet --sport /sports/soccer")
        print(f"\nAvailable platforms: {list(discoverer.PLATFORMS.keys())}")

    discoverer.generate_summary()


if __name__ == "__main__":
    asyncio.run(main())
