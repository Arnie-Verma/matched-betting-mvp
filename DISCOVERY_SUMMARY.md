# Platform Discovery Summary (2026-01-04)

## Executive Summary

Completed comprehensive automated research on **5 major Australian bookmaker platforms** plus targeted discovery updates (2026-01-04). Key findings:
- **3 bookmakers working NOW**: Ladbrokes, Neds (Entain), Betfair
- **3 platforms ready to implement**: Punterstech (21 bookmakers), Kindred/Unibet (1 bookmaker), BetCloud (26 bookmakers)
- **2 platforms still need deeper work**: BetMakers (SSR extraction), Generation Web (odds endpoint still hidden; betapi endpoints found)

**Ownership Correction (2025-12-30)**:
- ✅ **Entain** owns Ladbrokes + Neds (confirmed same platform/API)
- ❌ **Unibet is NOT Entain** - owned by Kindred Group (now FDJ), completely different API

### Research Scope
- **Sites tested**: 11 bookmakers across 5 platforms
- **Platforms covered**: Punterstech, Generation Web, BetMakers, BetCloud, Kindred
- **Total bookmakers**: 103 across all platforms
- **Methodology**: Enhanced Playwright-based multi-sport network traffic interception
- **Sports tested**: Soccer, AFL, NRL, Football (to find all endpoints)
- **Data collected**: 17 JSON files with API patterns documented
- **Research dates**: 2025-12-28 to 2026-01-04

---

## Platform Analysis

### 1. Punterstech (21 bookmakers) - ✅ READY TO IMPLEMENT

**Status**: Complete API documentation ready

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

**Implementation Approach**:
- Reuse Ladbrokes scraper architecture (similar API pattern)
- Minor changes: Update base URL + endpoint paths
- Expected timeline: **2-3 days**
- Value: **21 bookmakers with 1 scraper**

**Recommendation**: Start here - lowest barrier to entry, immediate impact

---

### 2. BetMakers (33 bookmakers) - ⚠️ SSR APPROACH REQUIRED

**Status**: Partial implementation path clear

**Discovery Results**:
- 0 public JSON APIs captured (server-side rendering)
- Odds data embedded directly in HTML response
- Uses modern JS framework (Next.js-style) but renders server-side
- Both test sites (RealBookie, CrossBet) follow identical pattern

**Anti-Bot Assessment**: ✅ NONE detected
- No rate limiting observed
- No IP blocking
- Safe for Playwright scraping

**Implementation Approach**:
- Use Playwright to load page + wait for DOM render
- Extract odds from HTML DOM using selectors/regex
- Expected timeline: **3-5 days**
- Value: **33 bookmakers with 1 scraper**

**Recommendation**: Second priority - higher effort but covers 33 bookmakers

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

## Implementation Roadmap (Updated 2026-01-04)

### Phase 0: Currently Working ✅
- Entain (Ladbrokes + Neds): 2 bookmakers
- Betfair: 1 exchange
- **Total Working**: 3 bookmakers

### Phase 1: Punterstech (21 bookmakers) - ✅ READY TO START
- Timeline: 2-3 days
- Value: 21 bookmakers (20% of target)
- Difficulty: Easy
- Status: Full API documented, ready to implement

### Phase 1b: Kindred/Unibet (1 bookmaker) - ✅ READY TO START
- Timeline: 1-2 days
- Value: 1 Premium bookmaker
- Difficulty: Easy
- Status: Full API discovered (1.9MB single endpoint)

### Phase 2: BetMakers (33 bookmakers) - ⚠️ CLEAR APPROACH
- Timeline: 3-5 days
- Value: 33 bookmakers (32% of target)
- Difficulty: Medium (SSR parsing with Playwright + DOM extraction)
- Status: Approach clear, no API to find

### Phase 3: Generation Web (22 bookmakers) - RESEARCH NEEDED
- Timeline: 2-3 days research + 3-5 days implementation
- Value: 22 bookmakers (21% of target)
- Difficulty: Medium (find hidden sports betting endpoint)
- Status: Configuration endpoints found, odds endpoint needs investigation

### Phase 4: BetCloud (26 bookmakers) - READY
- Timeline: 2-3 days
- Value: 26 bookmakers (26% of target)
- Difficulty: Medium (parse main_markets/propositions)
- Status: Sports odds endpoints confirmed; requires non-www Origin/Referer

**Total Timeline**: 2-3 weeks for 103-bookmaker coverage with 5 platform scrapers
**Critical Path**: Complete Phase 1 + 1b immediately, build BetCloud + BetMakers in parallel while Generation Web discovery continues

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

**BetCloud** (Initial + Enhanced multi-sport):
- `wellbet_20251229_073936.json` - WellBet (4 endpoints, initial - racing only)
- `betgalaxy_20251229_073953.json` - BetGalaxy (4 endpoints, initial - racing only)
- `wellbet_20251229_122512.json` - WellBet (4 endpoints, multi-sport) ✅ **ENHANCED**
- `betgalaxy_20251229_122555.json` - BetGalaxy (4 endpoints, multi-sport) ✅ **ENHANCED**
- `wellbet_20260104_053950.json` - WellBet (targeted rerun)
- `betgalaxy_20260104_054029.json` - BetGalaxy (targeted rerun)

**Kindred** (New discovery 2025-12-30):
- `unibet_20251230_071610.json` - Unibet (14 endpoints, 1.9MB odds data) ✅ **COMPLETE**

**Total Data**: 17 JSON files representing 11 bookmakers across 5 platforms (includes targeted reruns)

---

## Summary of Findings

### What's Working Now (3 bookmakers)
✅ **Entain (Ladbrokes + Neds)**: 2 bookmakers working (same platform/API)
✅ **Betfair (Exchange)**: 1 exchange working

### What's Ready to Implement (81+ bookmakers)
✅ **Punterstech (21 bookmakers)**: Complete API documented. Single scraper handles all 21 sites.
✅ **Kindred/Unibet (1 bookmaker)**: Complete API discovered. 1.9MB single endpoint for all matches.
✅ **BetMakers (33 bookmakers)**: SSR approach clear. Use Playwright + DOM parsing.
✅ **BetCloud (26 bookmakers)**: Sports odds endpoints confirmed; parse `main_markets`/`propositions`.

### What Needs Investigation (22 bookmakers)
⚠️ **Generation Web (22 bookmakers)**: Configuration endpoints found. Odds endpoint still hidden; betapi JS endpoints identified.

### Blockers Resolved (2026-01-04)
- ✅ Multi-sport automated research working
- ✅ Can now test platforms across soccer, AFL, NRL to find all endpoints
- ✅ Eliminated false hypothesis that hidden endpoints only in certain sports
- ✅ Confirmed BetCloud sports odds endpoints (`/punter/sports/*`) and header requirement (non-www Origin/Referer)
- ✅ **Corrected ownership**: Unibet is Kindred (NOT Entain), confirmed Neds works with Ladbrokes scraper
- ✅ **Discovered Unibet API**: Complete with 1.9MB football endpoint

---

**Last Updated**: 2026-01-04
**Tool**: `discovery.py` (Enhanced Playwright-based automated multi-sport research)
**Status**: Ready to start implementation (BetCloud endpoints confirmed)
**Next Steps**:
1. Build PunterstechScraper (2-3 days, 21 bookmakers)
2. Build UnibetScraper (1-2 days, 1 Premium bookmaker)
3. Build BetCloud scraper using `/punter/sports/*` endpoints
4. Continue Generation Web discovery (find odds endpoint or DOM fallback)
