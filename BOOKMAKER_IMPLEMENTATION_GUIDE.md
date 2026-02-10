# Bookmaker Implementation Guide

**Created**: 2026-01-19
**Last Updated**: 2026-02-08
**Purpose**: Quick reference for implementing new bookmaker scrapers

---

## Quick Start: Adding a New Bookmaker

### If Platform Scraper Already Exists

**Platforms with working scrapers**: Entain, Betfair, Punterstech, Kindred (Unibet)

1. Add entry to `apps/api/src/api/scripts/seed_all_bookmakers.py`
2. Run: `docker exec mb_api python -m api.scripts.seed_all_bookmakers`
3. Done - scraper will automatically pick up the new bookmaker

**Example** (adding new Punterstech bookmaker):
```python
{
    "code": "newbookie",
    "name": "NewBookie",
    "display_name": "NewBookie",
    "website_url": "https://www.newbookie.com.au",
    "base_url": "https://api.public.newbookie.com.au",  # API URL
    "is_active": True,
    "scraping_config": {
        "tier": "diamond",
        "platform": "punterstech",
        "scraper_class": "punterstech",  # Maps to SCRAPER_CLASSES
        "difficulty": "easy",
        "requires_proxy": False,
    },
},
```

### If Platform Scraper Doesn't Exist

1. Run discovery: `python discovery.py --site https://www.newbookie.com.au --sport /sports/soccer`
2. Create scraper in `apps/worker/src/scrapers/{platform}_scraper.py`
3. Register in `apps/worker/src/jobs/scrape_service.py` SCRAPER_CLASSES
4. Add bookmaker entries to seed script
5. Run seed script

---

## Unibet End-to-End Acceptance Checklist (Local-First)

Use this checklist to prove Unibet is production-like ready in local pre-production mode.

1. **Config + wiring**
- [ ] `unibet` exists in `seed_all_bookmakers.py` with `platform=kindred`, `scraper_class=kindred`, `is_active=true`.
- [ ] `kindred` is registered in `apps/worker/src/jobs/scrape_service.py` `SCRAPER_CLASSES`.

2. **Scraper health**
- [ ] Run a full scrape and confirm Unibet events/odds are saved:
  - `docker exec mb_api python ../worker/src/manual_scrape.py`
- [ ] Confirm current odds exist for Unibet in DB (non-zero).

3. **Competition/market correctness**
- [ ] Validate target competitions one-by-one (EPL, NBA, NHL, boxing, NBL):
  - `docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition epl --bookmaker unibet`
  - repeat for other target competitions.
- [ ] Confirm expected market shapes (2-way or 3-way as intended) and stable `selection_key`.

4. **Local canary (required)**
- [ ] Run repeated refresh/validation cycles for 30-60 minutes.
- [ ] Target at least 10-20 cycles across target competitions.
- [ ] Monitor: success rate, breaker opens, validation trend, event/odds count drift.

5. **UI visibility**
- [ ] Confirm your account plan allows Unibet.
- [ ] Open odds matcher and verify Unibet appears as a back bookmaker.
- [ ] Verify expected opportunities appear for target competitions.

6. **Go/No-Go**
- [ ] Promote only if checklist passes and no unresolved critical issues.
- [ ] If failed, set degraded/disabled, capture failure signature, fix, and rerun checklist.

---

## Platform Status Summary

| Platform | Bookmakers | Scraper | Status | Priority |
|----------|------------|---------|--------|----------|
| **Entain** | 3 | ✅ `entain` | Working | - |
| **Betfair** | 1 | ✅ `betfair` | Working | - |
| **Punterstech** | 21 | ✅ `punterstech` | Working | - |
| **Kindred/Unibet** | 1 | ✅ `kindred` | Implemented | - |
| **BetCloud** | 26 | ❌ Needs impl | API discovered | High |
| **Generation Web** | 22 | ❌ Needs impl | Partial discovery | Medium |
| **BetMakers** | 33 | ❌ Needs impl | SSR approach | Medium |
| **TAB** | 2 | ⚠️ `tab` | Needs proxy | Low |

---

## Platform Implementation Details

### 1. Kindred/Unibet (1 bookmaker) - IMPLEMENTED

**Discovery Date**: 2025-12-30
**Owner**: Kindred Group (FDJ acquired 2024)

**Main Endpoint**:
```
GET https://www.unibet.com.au/sportsbook-feeds/views/filter/{sport}/all/matches
    ?includeParticipants=true&useCombined=true

Response: 1.9MB for football - COMPLETE ODDS DATA
```

**Supporting Endpoints**:
```
GET /sportsbook-feeds/views/sports/a-z              → Sports list (10KB)
GET /sportsbook-feeds/settings?clientId=polopoly_desktop  → Config (50KB)
```

**Response Structure** (from discovery):
```json
{
  "viewId": "...",
  "session": "...",
  "layout": { /* event data with odds */ },
  "_links": { /* pagination */ }
}
```

**Implementation Notes**:
- Single large API call returns ALL match data per sport
- No authentication required
- No proxy needed
- Sport codes: `football`, `basketball`, `ice-hockey`, `american-football`, etc.

**Estimated Effort**: Completed (historical estimate was 1-2 days)

---

### 2. BetCloud (26 bookmakers) - READY TO IMPLEMENT

**Discovery Date**: 2026-01-04
**Bookmakers**: WellBet, BetGalaxy, VolcanoBet, TitanBet, ChromaBet, Bet777, TempleBet, GigaBet, SlamBet, SugarCastle, OldGill, FiestaBet, VikingBet, JungleBet, BetRoyale, SterlingParker, JuicyBet, BetProfessor, PuntGenie, QuestBet, PuntCity, Bet575, GoldenBet888

**API Base**: `https://api.{bookmaker}.com.au`

**CRITICAL**: Origin/Referer headers must use non-www domain
```
Origin: https://wellbet.com.au/
Referer: https://wellbet.com.au/
```
Using `www.` returns 403!

**Endpoints**:
```
GET /punter/general/offerings
    → Returns offered_sports with sport_id UUIDs

GET /punter/sports/competitions-tournaments?sport_id={id}
    → Competition list with match counts

GET /punter/sports/upcoming-matches-group-by-sport
    → Per-sport upcoming matches with main_markets odds (fast snapshot)

GET /punter/sports/upcoming-matches-by-time?limit=50&sport_id={id}&top_markets=false
    → Detailed match list with main_markets
```

**Response Structure** (upcoming-matches-by-time):
```json
{
  "items": [
    {
      "match_id": "uuid",
      "match_name": "Team A vs Team B",
      "competition_name": "Premier League",
      "match_start_time": "2026-01-20T15:00:00Z",
      "main_markets": [
        {
          "market_type": "match_winner",
          "propositions": [
            { "name": "Team A", "odds": 1.85 },
            { "name": "Draw", "odds": 3.50 },
            { "name": "Team B", "odds": 4.20 }
          ]
        }
      ]
    }
  ]
}
```

**Known Sport IDs** (WellBet/BetGalaxy):
- Soccer: `cb67b2f4-1eac-48d8-83b7-8dc6eca5b263`
- Need to discover: AFL, NRL, NBA, NHL, Boxing

**Implementation Notes**:
- Call `/punter/general/offerings` first to map sport names → UUIDs
- No authentication required
- No proxy needed (with correct headers)

**Estimated Effort**: 2-3 days

---

### 3. Generation Web (22 bookmakers) - PARTIAL DISCOVERY

**Bookmakers**: EliteBet, WinnersBet, GoldBet, MyBet, MidasBet, JustBet, PuntNow, JimmyBet, LetsBet, BetBetBet, UltraBet, PuntZone, BoostBet, HotBet, BoomBet, and more

**API Base**: `https://betapi.{bookmaker}.com.au`

**Discovered Endpoints** (config/metadata only):
```
POST /sportutility/getSportAZ
    Payload: {}
    → Returns sports index (926 bytes)

POST /sportutility2/getSportHighlights
    Payload: {"sportcode":"all","trending":1,"featured":0,"futures":0}
    → Returns featured events (3.2KB)

POST /sportutility/getAllSports (found in JS, not captured)
    Payload: {"sportcode":"all","isHome": true|false}

POST /sportutility/getUpcomingSport (found in JS, payload unknown)
```

**Blocking Issue**: Sports betting ODDS endpoint NOT captured
- Config endpoints return market structure, not actual odds
- Direct HTTP calls to betapi return HTML error/500
- Need browser context or additional headers

**Implementation Approach Options**:
1. **Deeper API discovery**: Find the actual odds endpoint in JS bundle
2. **DOM parsing fallback**: Use Playwright to render page, extract from HTML
3. **Hybrid**: Use API for events list, DOM for odds

**Estimated Effort**: 3-5 days (includes research)

---

### 4. BetMakers (33 bookmakers) - SSR APPROACH

**Bookmakers**: RealBookie, CrossBet, TerryBet, BetYouCan, DowBet, BetLocal, BetEstate, ReadyBet, PremiumBet, Bet66, MarantelliBet, BaggyBet, Punt123, SwiftBet, UpCoz, PicnicBet, OkeBet, BossBet, DiamondBet, WishBet, PlayWest, PonyBet, BetAus, BetZooka, BetSupreme, BetDash, BetLegends, Betit

**Discovery Finding**: 0 JSON APIs captured

**Reason**: Server-side rendering
- Odds data embedded directly in HTML response
- No separate JSON API calls to intercept
- Uses Next.js or similar SSR framework

**Implementation Approach**:
```python
# Option 1: Look for embedded JSON in HTML
async def scrape_sport(self, sport):
    page = await context.new_page()
    await page.goto(f"{base_url}/sports/{sport}")

    # Try to find embedded data
    odds_json = await page.evaluate("""
        () => {
            // Look for Next.js data
            if (window.__NEXT_DATA__) return window.__NEXT_DATA__;
            // Look for custom data
            if (window.__ODDS_DATA__) return window.__ODDS_DATA__;
            return null;
        }
    """)

# Option 2: Parse DOM
async def scrape_sport(self, sport):
    page = await context.new_page()
    await page.goto(f"{base_url}/sports/{sport}")

    events = await page.query_selector_all('.event-card')
    for event in events:
        name = await event.query_selector('.event-name').text_content()
        odds = await event.query_selector_all('.odds-value')
        # Parse odds...
```

**Estimated Effort**: 4-6 days

---

## Architecture Quick Reference

### Base Scraper Contract

```python
# apps/worker/src/scrapers/base.py

class BaseScraper(ABC):
    def __init__(self, bookmaker_code: str, base_url: str, config: dict = None):
        self.bookmaker_code = bookmaker_code
        self.base_url = base_url
        self.config = config or {}

    @abstractmethod
    async def scrape_sport(self, sport: str, limit: int = None) -> ScrapeResult:
        """Main entry point - must implement"""
        pass

    def parse_event(self, event_data) -> ScrapedEvent:
        """Optional - can implement inline"""
        pass

    def parse_odds(self, odds_data, event) -> List[ScrapedOdds]:
        """Optional - can implement inline"""
        pass
```

### Data Models

```python
@dataclass
class ScrapedOdds:
    event_external_id: str
    event_name: str
    sport: str
    competition: str
    start_time: datetime
    market_type: str
    market_name: str
    selection_name: str
    selection_key: str  # home/away/draw/other
    decimal_odds: Decimal
    bookmaker_code: str
    source_url: str
    scraped_at: datetime
    liquidity: Optional[Decimal] = None  # For exchanges

@dataclass
class ScrapedEvent:
    external_id: str
    name: str
    sport: str
    competition: str
    start_time: datetime
    home_team: str
    away_team: str
    odds: List[ScrapedOdds]
    venue: Optional[str] = None

@dataclass
class ScrapeResult:
    bookmaker_code: str
    status: ScraperStatus  # SUCCESS/PARTIAL/FAILED
    events_scraped: int
    odds_scraped: int
    events: List[ScrapedEvent]
    errors: List[str]
    started_at: datetime
    completed_at: datetime
```

### Scraper Registry

```python
# apps/worker/src/jobs/scrape_service.py

SCRAPER_CLASSES: Dict[str, Type[BaseScraper]] = {
    "entain": EntainScraper,
    "betfair": BetfairScraper,
    "tab": TABScraper,
    "punterstech": PunterstechScraper,
    # Add new scrapers here:
    # "kindred": KindredScraper,
    # "betcloud": BetCloudScraper,
    # "generation_web": GenerationWebScraper,
    # "betmakers": BetMakersScraper,
}
```

### Sport Codes

Internal sport codes used across all scrapers:
- `soccer`
- `afl`
- `nrl`
- `basketball`
- `ice_hockey`
- `boxing`

### Competition Codes

Internal competition codes:
- `epl` - English Premier League
- `laliga` - Spanish La Liga
- `bundesliga` - German Bundesliga
- `seriea` - Italian Serie A
- `ligue1` - French Ligue 1
- `ucl` - UEFA Champions League
- `aleague` - A-League
- `mls` - Major League Soccer
- `afl` - AFL
- `nrl` - NRL
- `nba` - NBA
- `nbl` - NBL
- `nhl` - NHL
- `boxing` - Boxing

---

## Implementation Patterns

### Pattern 1: Direct HTTP API (Fastest)

Used by: Punterstech, TAB, BetCloud (planned), Kindred (planned)

```python
class PlatformScraper(BaseScraper):
    async def scrape_sport(self, sport: str, limit: int = None) -> ScrapeResult:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/events",
                params={"sport": sport},
                headers=self._get_headers()
            )
            data = response.json()

            events = []
            for event_data in data["events"]:
                event = self._parse_event(event_data)
                events.append(event)

            return ScrapeResult(
                bookmaker_code=self.bookmaker_code,
                status=ScraperStatus.SUCCESS,
                events_scraped=len(events),
                odds_scraped=sum(len(e.odds) for e in events),
                events=events,
                errors=[],
                started_at=start_time,
                completed_at=datetime.now()
            )
```

### Pattern 2: Browser + Network Interception

Used by: Entain, Betfair, Ladbrokes

```python
class PlatformScraper(BaseScraper):
    _browser = None  # Class-level browser reuse

    async def scrape_sport(self, sport: str, limit: int = None) -> ScrapeResult:
        browser = await self._get_or_create_browser()
        context = await browser.new_context()
        page = await context.new_page()

        # Local captured_data for closure safety
        captured_data: List[Dict] = []

        async def handle_response(response):
            if "api/events" in response.url:
                try:
                    data = await response.json()
                    captured_data.append(data)
                except:
                    pass

        page.on('response', handle_response)

        await page.goto(f"{self.base_url}/sports/{sport}")

        # Dynamic wait for data
        wait_start = time.time()
        while time.time() - wait_start < 10:
            if captured_data:
                await asyncio.sleep(0.5)
                break
            await asyncio.sleep(0.3)

        await context.close()

        # Parse captured_data into events
        ...
```

### Pattern 3: DOM Parsing (SSR Sites)

Used by: BetMakers (planned)

```python
class PlatformScraper(BaseScraper):
    async def scrape_sport(self, sport: str, limit: int = None) -> ScrapeResult:
        browser = await self._get_or_create_browser()
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(f"{self.base_url}/sports/{sport}")
        await page.wait_for_selector('.event-card')

        events = []
        event_elements = await page.query_selector_all('.event-card')

        for el in event_elements:
            name = await (await el.query_selector('.event-name')).text_content()
            time_str = await (await el.query_selector('.event-time')).text_content()

            odds_elements = await el.query_selector_all('.odds-button')
            odds = []
            for odds_el in odds_elements:
                selection = await odds_el.get_attribute('data-selection')
                price = await odds_el.text_content()
                odds.append(ScrapedOdds(...))

            events.append(ScrapedEvent(...))

        await context.close()
        return ScrapeResult(...)
```

---

## Testing New Scrapers

### 1. Unit Test the Scraper

```python
# apps/worker/tests/test_new_scraper.py

@pytest.mark.asyncio
async def test_scrape_single_sport():
    scraper = NewPlatformScraper(
        bookmaker_code="newbookie",
        base_url="https://api.newbookie.com.au",
        config={}
    )

    result = await scraper.scrape_sport("soccer")

    assert result.status in [ScraperStatus.SUCCESS, ScraperStatus.PARTIAL]
    assert result.events_scraped > 0
    assert result.odds_scraped > 0
```

### 2. Manual Scrape Test

```bash
# Single bookmaker
docker exec mb_api python -c "
import asyncio
from worker.src.scrapers.new_scraper import NewPlatformScraper

async def test():
    scraper = NewPlatformScraper('newbookie', 'https://api.newbookie.com.au', {})
    result = await scraper.scrape_sport('soccer')
    print(f'Events: {result.events_scraped}, Odds: {result.odds_scraped}')
    for e in result.events[:3]:
        print(f'  {e.name}: {len(e.odds)} odds')

asyncio.run(test())
"
```

### 3. Full Integration Test

```bash
# Run full scrape
docker exec mb_api python ../worker/src/manual_scrape.py

# Validate output
docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition epl
```

---

## Discovery Tool Usage

### Research a New Platform

```bash
# Basic discovery
python discovery.py --site https://www.newbookie.com.au --sport /sports/soccer

# Multi-sport discovery
python discovery.py --platform betcloud
```

### Analyze JS Bundle for Hidden APIs

```bash
# After loading page in browser:
# 1. Open DevTools > Sources
# 2. Search for patterns: "/api/", "fetch(", "axios"
# 3. Look for endpoint construction

# Common patterns:
# - `/punter/sports/...` (BetCloud)
# - `/sportutility/...` (Generation Web)
# - `/sportsbook-feeds/...` (Kindred)
# - `/api/v1/events/...` (Generic)
```

### Check API Manually

```bash
# Test endpoint with curl
curl -s "https://api.wellbet.com.au/punter/general/offerings" \
  -H "Origin: https://wellbet.com.au/" \
  -H "Referer: https://wellbet.com.au/" | jq .

# Test Unibet
curl -s "https://www.unibet.com.au/sportsbook-feeds/views/sports/a-z" | jq .
```

---

## Normalization Checklist

When adding new bookmaker, check these normalizations work:

### Team Names
- [ ] Check team names in new API match existing mappings
- [ ] Add new mappings to `apps/api/src/api/services/normalization_service.py` if needed

### Competition Names
- [ ] New bookmaker's competition names map to internal codes
- [ ] Examples: "English Premier League" → "epl", "La Liga" → "laliga"

### Selection Keys
- [ ] Home/Away/Draw correctly identified from API response
- [ ] Map API-specific keys (e.g., "1" → "home", "X" → "draw", "2" → "away")

---

## Troubleshooting

### Scraper Returns 0 Events

1. Check API endpoint is correct
2. Verify headers (especially Origin/Referer for BetCloud)
3. Increase wait time for JS-heavy sites
4. Check if sport is in season

### Events Not Matching Across Bookmakers

1. Check team name normalization
2. Look for different naming conventions (e.g., "Man Utd" vs "Manchester United")
3. Add mappings to normalization service

### 403 Errors

1. Check if proxy needed (TAB, Sportsbet)
2. Verify headers match browser
3. Check rate limiting
4. Try with browser context instead of direct HTTP

### Scraper Timeout

1. Increase timeout in scrape_service.py
2. Check if site is slow or blocking
3. Consider reducing concurrent requests

---

## Files Reference

| File | Purpose |
|------|---------|
| `apps/worker/src/scrapers/base.py` | Base class, data models |
| `apps/worker/src/scrapers/*_scraper.py` | Platform implementations |
| `apps/worker/src/jobs/scrape_service.py` | Orchestration, SCRAPER_CLASSES |
| `apps/worker/src/jobs/save_odds.py` | Database persistence |
| `apps/api/src/api/services/normalization_service.py` | Name normalization |
| `apps/api/src/api/scripts/seed_all_bookmakers.py` | Bookmaker config |
| `discovery.py` | API discovery tool |
| `discovery_output/*.json` | Captured API patterns |

---

## Implementation Priority

1. **BetCloud** (3 days) - 26 bookmakers, API confirmed
2. **Generation Web** (4 days) - 22 bookmakers, needs odds endpoint discovery
3. **BetMakers** (5 days) - 33 bookmakers, DOM/API query capture still required
4. **Standalone premium books** - PointsBet and BetRight next

Total remaining effort depends on discovery closure for Generation Web and BetMakers.

---

*Document version: 1.2*
*Created: 2026-01-19*
*Updated: 2026-02-08*
