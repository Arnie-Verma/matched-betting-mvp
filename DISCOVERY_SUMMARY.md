# Platform Discovery Summary

## Premium Tier Targeted Discovery Update (2026-02-01)

Goal: finish **Premium** bookmaker list (excluding known proxy-required scrapers for MVP).

### Quick Recommendations (MVP, no rotating proxy)
Unibet is now implemented (KindredScraper); next easiest to add:
1. **PointsBet** – public JSON REST endpoints; looks straightforward to implement
2. **BetRight** – “next-api” JSON endpoints captured; likely implementable
3. **TABTouch** – appears to be **Kambi** (config reveals Kambi offering URLs); needs Kambi-specific implementation
4. **CrossBet + RealBookie** – appear to use **BetMakers Apollo GraphQL** (`bmapollo.com/query`); odds queries not captured yet (needs deeper interaction discovery)

### Premium Bookmakers: What We Found (2026-02-01)

| Bookmaker | Result | Likely Platform | Evidence / Notes |
|---|---|---|---|
| **Ladbrokes** | Already working | Entain | Existing `EntainScraper` |
| **Neds** | Already working | Entain | Existing `EntainScraper` |
| **Betfair** | Already working | Exchange | Existing `BetfairScraper` |
| **Unibet** | Implemented (frozen for activation) | Kindred/FDJ (+ Shape Games config present) | Implemented via `KindredScraper`; keep `BOOKMAKER_FREEZE_UNIBET=true` and `is_active=false` until explicit activation approval |
| **PointsBet** | ✅ Strong “no proxy” candidate | Standalone (PointsBet) | Captured `https://api.au.pointsbet.com/api/v2/...` incl. `/sports/soccer/competitions`, `/sports/soccer/events/all-featured`, `/events/nextup` |
| **BetRight** | ✅ Likely implementable | Standalone (BetRight) | Captured `https://next-api.betright.com.au/Sports/Next` + `PopularMarket/List` + SignalR negotiate |
| **TABTouch** | ⚠️ Candidate (needs Kambi approach) | Kambi (via Shape Games config) | Config reveals `apiBaseUrl=https://oc-offering-api.kambicdn.com/{api}/v2018/` and stats GraphQL URLs |
| **CrossBet** | ⚠️ Needs deeper discovery | BetMakers Apollo (GraphQL) | Captured `https://platform.crossbet.bmapollo.com/query` (GraphQL); only config query captured so far |
| **RealBookie** | ⚠️ Needs deeper discovery | BetMakers Apollo (GraphQL) | Captured `https://platform.realbookie.bmapollo.com/query` (GraphQL); only config query captured so far |
| **EliteBet** | ⚠️ Still blocked on odds endpoint | Generation Web | Same as before: `/sportutility/getSportAZ`, `/sportutility2/getSportHighlights` only |
| **BetDeluxe** | ⚠️ Partial | Unknown (“blackstream” API) | Captured `https://api.blackstream.com.au/api/sports/v1/...` but `multi-sports-competitions` returned empty; needs parameter discovery / deeper navigation |
| **Betr** | ❌ No odds captured | Likely BlueBet/“web20-api” | Captured `https://web20-api.bluebet.com.au/*` config/content only; no sports odds calls observed |
| **Dabble** | ❌ No odds captured | Unknown | Only analytics calls captured; likely requires login/app API |
| **Sportsbet** | ⚠️ Partial; treat as proxy-likely | Standalone | Captured limited `/apigw/...` calls (racing + commentary); no core sports odds endpoints in this run |
| **TAB** | ❌ No endpoints captured | Standalone (TAB) | No API calls observed in Playwright run; consistent with prior “proxy needed” notes |

## Executive Summary

Completed comprehensive automated research on major Australian bookmaker platforms (2025-12-28 → 2026-01-04) plus Premium-tier targeted discovery refresh (2026-02-01). Key findings:
- **Implemented scrapers**: Entain (Ladbrokes, Neds), Betfair, Punterstech (21-skin platform scraper), Kindred (Unibet)
- **Premium (no-proxy) next additions**: PointsBet, BetRight
- **Platform APIs discovered, not yet implemented**: BetCloud (26 bookmakers)
- **Needs deeper work**: Generation Web odds endpoint, BetMakers GraphQL odds queries, plus Betr/Dabble/BetDeluxe deeper interaction discovery

**Ownership Correction (2025-12-30)**:
- ✅ **Entain** owns Ladbrokes + Neds (confirmed same platform/API)
- ❌ **Unibet is NOT Entain** - owned by Kindred Group (now FDJ), completely different API

### Research Scope
- **Sites tested**: 11 bookmakers across 5 platforms
- **Platforms covered**: Punterstech, Generation Web, BetMakers, BetCloud, Kindred
- **Total bookmakers**: 103 across all platforms
- **Methodology**: Enhanced Playwright-based multi-sport network traffic interception
- **Sports tested**: Soccer, AFL, NRL, Football (to find all endpoints)
- **Data collected**: 17 JSON files (platform discovery) + 12 Premium-tier targeted discovery runs (2026-02-01)
- **Research dates**: 2025-12-28 to 2026-02-01

---

## Platform Analysis

### 1. Punterstech (21 bookmakers) - ✅ IMPLEMENTED

**Status**: Platform scraper implemented and validated (`PunterstechScraper`)

**API Discovery**:
- REST-based with 36-38 endpoints per site
- All endpoints consistent across both test sites (TradieBET, MintBet)
- Base URL pattern: `https://api.public.{domain}/`
- No authentication required for public endpoints

**Core Endpoints**:
```
POST /api-events/public/next-to-go/batch     ← Primary endpoint (116KB response)
GET  /api-events/public/open-event-types     ← Sports list
GET  /api-events/public/markets/{event-id}   ← Specific event odds
GET  /sportssilks/supportedsports            ← Team/sport metadata
```

**Anti-Bot Assessment**: ✅ NONE
- No rate limiting observed
- No IP blocking
- No Cloudflare/Akamai protection
- Safe for direct scraping at scale

**Implementation Approach (Completed)**:
- Implemented `PunterstechScraper` (direct HTTP, config-driven `base_url` per bookmaker)
- Enable additional skins by updating DB config (`is_active=true`, `scraper_class=punterstech`, correct `base_url`)
- Keep defunct/DNS-failing skins disabled

**Recommendation**: Use Punterstech as the reference “easy/no-proxy” platform; expand coverage via config + validation.

---

### 2. BetMakers (33 bookmakers) - ⚠️ GRAPHQL (Apollo) ENDPOINT CONFIRMED

**Status**: GraphQL endpoint confirmed; odds queries still need capture

**Discovery Results (Update 2026-02-01)**:
- Captured GraphQL endpoint on BetMakers skins:
  - CrossBet: `https://platform.crossbet.bmapollo.com/query`
  - RealBookie: `https://platform.realbookie.bmapollo.com/query`
- Requests are JSON GraphQL (`query`, `variables`, `operationName`)
- Only a configuration query was captured so far (still need event/market/odds operations)

**Anti-Bot Assessment**: ✅ NONE detected (so far)
- No Cloudflare/Akamai observed during discovery runs

**Implementation Approach**:
1. Use Playwright to navigate deeper (competition → event) to capture GraphQL operations for events/markets/odds
2. Replay those operations via direct HTTP POST (cheaper/faster than DOM scraping)
3. Generalize `{bookmaker}.bmapollo.com` base to cover all BetMakers skins

**Expected Implementation**: **1-2 days research + 2-4 days implementation**
**Value**: **33 bookmakers with 1 scraper**

**Recommendation**: High leverage, but only after capturing the odds GraphQL operations.

---

### 3. Generation Web (22 bookmakers) - ⚠️ CONFIGURATION + JS ENDPOINTS FOUND

**Status**: Partial API found, sports betting odds endpoint still hidden

**Discovery Results (Multi-Sport Research)**:
- ✅ Found 2 consistent endpoints across all 3 sports
- ✅ Captured: `/sportutility/getSportAZ` (865 bytes), `/sportutility2/getSportHighlights` (2.2KB)
- ✅ Endpoints identical between EliteBet and WinnersBet (consistent across platform)
- ⚠️ Sports betting odds API NOT captured
- Evidence: Sites use `betapi.{domain}` subdomain, responses are lightweight configs

**Key Findings**:
- EliteBet tested across 3 sports (soccer, AFL, NRL) → same endpoints
- WinnersBet tested → only live chat API captured
- Endpoint consistency confirms single API pattern across Generation Web bookmakers
- Response keys: `hotevents`, `sportAZ` suggest market/sport configuration, not odds

**Targeted Updates (2026-01-04)**:
- EliteBet JS bundle references additional betapi endpoints:
  - `POST /sportutility/getAllSports` payload: `{"sportcode":"all","isHome": true|false}`
  - `POST /sportutility/getUpcomingSport` (payload not yet captured)
  - `POST /sportutility/getSportAZ` payload: `{}`
  - `POST /sportutility2/getSportHighlights` payload: `{"sportcode":"all","trending":1,"featured":0,"futures":0}`
- JS also references `/api/racing/getRaceDayEvents` and `/api/racing/getRacePrices` (likely Next.js API routes on `https://www.{domain}`).
- Direct HTTP calls to betapi return HTML error/500; Playwright captures JSON responses, so browser context or extra headers are likely required.

**Implementation Approach**:
1. ✅ Configuration endpoints working and documented
2. ⚠️ Need to find sports betting odds endpoint
   - Likely client-side loaded via JavaScript
   - May require parsing HTML response for embedded JSON
   - Or find event IDs from config endpoint, then fetch odds separately

**Expected Implementation**: **2-3 days research + 3-5 days implementation**
**Value**: **22 bookmakers with 1 scraper**

---

### 4. BetCloud (26 bookmakers) - ✅ SPORTS ODDS API FOUND

**Status**: Sports odds endpoints confirmed (2026-01-04)

**Discovery Results (Targeted 2026-01-04)**:
- ✅ `GET /punter/general/offerings` → `offered_sports` with `sport_id`
- ✅ `GET /punter/sports/competitions-tournaments?sport_id={id}` → competition list
- ✅ `GET /punter/sports/upcoming-matches-group-by-sport` → per-sport upcoming matches with `main_markets` odds
- ✅ `GET /punter/sports/upcoming-matches-by-time?limit=50&sport_id={id}&top_markets=false` → detailed match list with `main_markets`
- ✅ `GET /punter/races/next-to-jump?race_type=...` → racing (already known)

**Header Requirement**:
- API calls must use `Origin`/`Referer` for the non-www base domain (e.g., `https://wellbet.com.au/`, `https://betgalaxy.com.au/`).
- Using `www` in Origin/Referer returns 403.

**Response Structure (sports odds)**:
- `upcoming-matches-by-time` returns `items[]` with:
  - `match_id`, `match_name`, `competition_name`, `match_start_time`
  - `main_markets[]` → `propositions[]` → `odds` (decimal)
- `upcoming-matches-group-by-sport` returns per-sport `upcoming_matches[]` with `main_markets`.

**Implementation Approach**:
1. Call `offerings` to map sport display names to `sport_id`.
2. Fetch matches via `upcoming-matches-by-time` (or grouped endpoint for fast snapshots).
3. Parse `main_markets` → `propositions` → `odds`.

**Expected Implementation**: **2-3 days**
**Value**: **26 bookmakers with 1 scraper**

---

### 5. Kindred/Unibet (1 bookmaker) - ✅ API DISCOVERED

**Status**: Complete API found, ready to implement
**Discovery Date**: 2025-12-30
**Owner**: Kindred Group (acquired by FDJ in Oct 2024) - **NOT Entain**

**API Pattern Discovered**:
```
GET https://www.unibet.com.au/sportsbook-feeds/views/filter/{sport}/all/matches
Response: 1.9MB for football - COMPLETE ODDS DATA
```

**Core Endpoints** (14 captured):
```
GET /sportsbook-feeds/views/filter/football/all/matches  → Full odds (1.9MB)
GET /sportsbook-feeds/views/sports/a-z                   → Sports list (10KB)
GET /sportsbook-feeds/settings                           → Config (50KB)
```

**Anti-Bot Protection**: ✅ NONE detected
**Proxy Needed**: No

**Key Finding**: Completely different API from Entain - needs separate scraper

**Implementation Notes**:
- Single large API call returns all match data per sport
- Response structure: `viewId`, `session`, `layout`, `_links`
- May need pagination for efficiency
- **Covers 1 bookmaker but high-value (Premium tier)**

**Expected Implementation**: **1-2 days**
**Value**: **1 Premium bookmaker**

---

## Implementation Roadmap (Updated 2026-02-01)

### Phase 0: Currently Working ✅
- Entain (Ladbrokes + Neds): 2 bookmakers
- Betfair: 1 exchange
- Punterstech: platform scraper implemented (21-skin platform; multiple skins enabled)
- **Total Working (implemented scrapers)**: 3 platform scrapers + exchange

### Phase 1: Premium Tier (No Proxy) - PARTIAL READY
- Kindred/Unibet: implemented but intentionally frozen (no activation work in current baseline)
- PointsBet: 1 bookmaker (public REST endpoints on `api.au.pointsbet.com`)
- BetRight: 1 bookmaker (`next-api.betright.com.au` endpoints captured)

### Phase 2: BetCloud (26 bookmakers) - ✅ READY
- Timeline: 2-3 days
- Status: Sports odds endpoints confirmed; requires non-www Origin/Referer

### Phase 3: BetMakers (33 bookmakers) - ⚠️ NEEDS GRAPHQL ODDS QUERY CAPTURE
- Timeline: 1-2 days research + 2-4 days implementation
- Status: GraphQL endpoint confirmed (`bmapollo.com/query`), but event/market/odds operations still need capture

### Phase 4: Generation Web (22 bookmakers) - ⚠️ RESEARCH NEEDED
- Timeline: 2-3 days research + 3-5 days implementation
- Status: Configuration endpoints found; sports odds endpoint still hidden

### Phase 5: Proxy/Production Later
- TAB + Sportsbet (likely proxy/anti-bot); skip for MVP if needed

**Critical Path**: finish Premium “no proxy” bookies (Unibet + PointsBet + BetRight), then BetCloud, then BetMakers GraphQL capture.

---

## Key Technical Findings

### Anti-Bot Protection
- **Punterstech**: ✅ None
- **Kindred/Unibet**: ✅ None
- **BetMakers**: ✅ None
- **Generation Web**: ⚠️ Unknown (limited data)
- **BetCloud**: ✅ None (requires non-www Origin/Referer)
**Conclusion**: No proxy required for any discovered platform

### Authentication Requirements
- **Punterstech**: ✅ Public (no auth)
- **BetMakers**: ✅ Public (HTML embedded)
- **Generation Web**: ⚠️ Unknown
- **BetCloud**: ✅ Public (Origin/Referer required)

---

## Discovery Output Files

Located in `discovery_output/`:

**Punterstech** (Initial discovery - working):
- `tradiebet_20251229_071822.json` - TradieBET (36 endpoints, consistent)
- `mintbet_20251229_071836.json` - MintBet (38 endpoints, consistent)

**Generation Web** (Initial + Enhanced multi-sport):
- `elitebet_20251229_071944.json` - EliteBet (3 endpoints, initial)
- `winnersbet_20251229_072000.json` - WinnersBet (1 endpoint, initial)
- `elitebet_20251229_122024.json` - EliteBet (3 endpoints, multi-sport) ✅ **ENHANCED**
- `winnersbet_20251229_122103.json` - WinnersBet (1 endpoint, multi-sport) ✅ **ENHANCED**
- `elitebet_20260104_053836.json` - EliteBet (targeted rerun)
- `winnersbet_20260104_053910.json` - WinnersBet (targeted rerun)

**BetMakers** (Initial discovery - SSR):
- `realbookie_20251229_073815.json` - RealBookie (0 APIs - SSR)
- `crossbet_20251229_073829.json` - CrossBet (0 APIs - SSR)

**Premium Tier Targeted Discovery (2026-02-01)**:
- `unibet.com.au_20260201_181859.json` - Unibet (reconfirmed large `/sportsbook-feeds/views/filter/.../matches` payload)
- `pointsbet.com.au_20260201_181137.json` - PointsBet (public `api.au.pointsbet.com` endpoints captured)
- `betright.com.au_20260201_181409.json` - BetRight (`next-api.betright.com.au` endpoints captured)
- `tabtouch.com.au_20260201_181504.json` - TABTouch (Shape Games config; reveals Kambi offering URLs)
- `sportsbet.com.au_20260201_181626.json` - Sportsbet (partial `apigw` endpoints captured; core odds not captured in this run)
- `tab.com.au_20260201_181701.json` - TAB (0 endpoints captured in this run)
- `elitebet.com.au_20260201_181916.json` - EliteBet (still only `betapi.* /sportutility*` endpoints)
- `betdeluxe.com.au_20260201_181251.json` - BetDeluxe (partial; `api.blackstream.com.au` endpoints, sports competitions empty)
- `betr.com.au_20260201_181214.json` - Betr (no odds endpoints captured; `web20-api.bluebet.com.au` config/content only)
- `dabble.com.au_20260201_181436.json` - Dabble (no odds endpoints captured)
- `crossbet.com.au_20260201_182047.json` - CrossBet (`platform.crossbet.bmapollo.com/query` GraphQL captured; only config query observed)
- `realbookie.com.au_20260201_182106.json` - RealBookie (`platform.realbookie.bmapollo.com/query` GraphQL captured; only config query observed)

**BetCloud** (Initial + Enhanced multi-sport):
- `wellbet_20251229_073936.json` - WellBet (4 endpoints, initial - racing only)
- `betgalaxy_20251229_073953.json` - BetGalaxy (4 endpoints, initial - racing only)
- `wellbet_20251229_122512.json` - WellBet (4 endpoints, multi-sport) ✅ **ENHANCED**
- `betgalaxy_20251229_122555.json` - BetGalaxy (4 endpoints, multi-sport) ✅ **ENHANCED**
- `wellbet_20260104_053950.json` - WellBet (targeted rerun)
- `betgalaxy_20260104_054029.json` - BetGalaxy (targeted rerun)

**Kindred** (New discovery 2025-12-30):
- `unibet_20251230_071610.json` - Unibet (14 endpoints, 1.9MB odds data) ✅ **COMPLETE**

**Total Data**: 17 platform discovery JSON files (Dec/Jan) + 12 Premium-tier targeted discovery JSON files (2026-02-01)

---

## Summary of Findings

### What's Working Now (implemented scrapers)
✅ **Entain (Ladbrokes + Neds)**: 2 bookmakers working (same platform/API)
✅ **Betfair (Exchange)**: 1 exchange working
✅ **Punterstech (21 bookmakers)**: scraper implemented; enable/disable skins via DB config
✅ **Kindred (Unibet)**: scraper implemented (direct HTTP); keep frozen in baseline (`is_active=false`, runtime freeze flag enabled)

### What's Ready to Implement Next (no proxy priority)
✅ **PointsBet (1 bookmaker)**: public REST endpoints captured on `api.au.pointsbet.com`
✅ **BetRight (1 bookmaker)**: `next-api.betright.com.au` endpoints captured
✅ **BetCloud (26 bookmakers)**: sports odds endpoints confirmed; parse `main_markets`/`propositions`

### What Needs Investigation
⚠️ **BetMakers (33 bookmakers)**: GraphQL endpoint confirmed (`bmapollo.com/query`), but odds operations still need capture
⚠️ **Generation Web (22 bookmakers)**: configuration endpoints found; odds endpoint still hidden; betapi JS endpoints identified
⚠️ **Premium standalone backlog (2026-02-01)**: Betr, Dabble, BetDeluxe need deeper interaction discovery to capture odds endpoints
⚠️ **Proxy/anti-bot**: TAB + Sportsbet likely; defer for MVP if needed

### Blockers Resolved (through 2026-02-01)
- ✅ Multi-sport automated research working
- ✅ Can now test platforms across soccer, AFL, NRL to find all endpoints
- ✅ Eliminated false hypothesis that hidden endpoints only in certain sports
- ✅ Confirmed BetCloud sports odds endpoints (`/punter/sports/*`) and header requirement (non-www Origin/Referer)
- ✅ **Corrected ownership**: Unibet is Kindred (NOT Entain), confirmed Neds works with Ladbrokes scraper
- ✅ **Discovered Unibet API**: Complete with 1.9MB football endpoint
- ✅ **Implemented Unibet scraper**: KindredScraper + market-rank aligned lay selection

---

**Last Updated**: 2026-02-01
**Tool**: `discovery.py` (Enhanced Playwright-based automated multi-sport research)
**Status**: Punterstech + Unibet implemented; Premium-tier discovery refreshed (PointsBet/BetRight reconfirmed; others need deeper discovery)
**Next Steps**:
1. Keep Unibet frozen (`BOOKMAKER_FREEZE_UNIBET=true`, `is_active=false`) and maintain readiness validation evidence
2. Build PointsBet scraper using `api.au.pointsbet.com/api/v2/...` endpoints (Premium) + add `pointsbet` to worker scraper registry
3. Build BetRight scraper using `next-api.betright.com.au` endpoints (Premium) + add `betright` to worker scraper registry
4. Build BetCloud platform scraper using `/punter/sports/*` endpoints (2-3 days, 26 bookmakers)
5. Improve BetMakers discovery (capture GraphQL odds queries on `bmapollo.com/query`) then implement platform scraper
6. Continue Generation Web discovery (find odds endpoint or DOM fallback)
7. Defer TAB/Sportsbet until proxy/production (if needed)
