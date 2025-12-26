# Context: Ladbrokes Scraper & Odds Matcher Optimization

**Date**: 2025-12-21
**Focus**: Optimize Ladbrokes scraper and odds matcher for production scale (1000+ users, 100+ bookmakers)

---

## Project Overview

Building **Outmatched.com-style matched betting platform** for Australian market.

**Business Model**:
- Free tier: 2 bookmakers (Ladbrokes + Neds) + Betfair exchange
- Premium ($15/mo): 16 bookmakers
- Diamond ($30/mo): 103 bookmakers (all Australian bookies)

**Scale Requirements**:
- **Target**: 1000+ concurrent users
- **Bookmakers**: Currently 2 (Ladbrokes, Betfair), scaling to 100+
- **Architecture**: Must support global cache shared across all users (5-15 min TTL)
- **Performance**: Currently 75s refresh, target <30s (Outmatched does 20s)

---

## Current Architecture

### Tech Stack
- **Frontend**: Next.js 14 + Clerk auth + Tailwind
- **Backend**: FastAPI + PostgreSQL 16 + Redis
- **Scrapers**: Playwright (Ladbrokes, Betfair) - running in Docker containers
- **Deployment**: Docker Compose (dev), planning Railway/Render (prod)

### Data Flow
```
User clicks refresh
  → API /odds/refresh endpoint
  → Scrape Service (scrape_service.py)
    → Sequential loop: for each sport in [soccer, afl, nrl, basketball, ice_hockey, boxing]
      → Ladbrokes scraper (ladbrokes_scraper.py) - Playwright
        → Navigate to sport page
        → Wait 5 seconds for API responses
        → Intercept network calls
        → Parse JSON response
      → Betfair scraper (betfair_scraper.py) - Playwright
        → Navigate to competition page
        → Wait 5s + 1s async
        → Intercept network calls
        → Parse events + odds
  → Save odds to DB (save_odds.py)
  → Matching engine (matching_engine.py)
    → Group events by normalized name
    → Match bookmaker odds (back) with Betfair (lay)
    → Calculate PnL with 6% commission
  → Return opportunities to frontend
```

### Database Schema (Relevant Tables)
```sql
-- Time-series odds data
events (id, name, sport, competition_id, start_time, status)
markets (id, event_id, name, market_type, is_active)
selections (id, market_id, name)  -- e.g., "Liverpool", "Draw", "Chelsea"
odds_snapshots (id, selection_id, bookmaker_id, decimal_odds, is_current, timestamp)
bookmakers (id, code, display_name, tier)  -- FREE/PREMIUM/PLATINUM

-- User subscriptions
users (id, clerk_user_id, current_plan, plan_status)
subscriptions (id, user_id, plan, stripe_subscription_id)
```

---

## Current Implementation: Ladbrokes Scraper

**File**: `apps/worker/src/scrapers/ladbrokes_scraper.py`

### How It Works
1. **Browser Launch** (first time only): Playwright Chromium headless (~2s)
2. **For each sport** (6 sports sequentially):
   - Navigate to `https://www.ladbrokes.com.au/sports/{sport}`
   - Wait for page load (~2-3s)
   - **Fixed 5-second wait** for API responses (line 149)
   - Intercept `event-request` API calls via Playwright response handler
   - Parse JSON structure:
     ```json
     {
       "events": {event_id: {name, competition, start, ...}},
       "markets": {market_id: {name, event_id, entrant_ids, ...}},
       "prices": {entrant_id: {odds: {numerator, denominator}}},
       "entrants": {entrant_id: {name, market_id, ...}}
     }
     ```
3. **Filter competitions**: Only keep target 14 competitions (EPL, NBA, NHL, etc.)
4. **Convert odds**: Fractional → Decimal (e.g., 5/2 → 3.50)

### Current Performance
- **Per sport**: ~8s (2s nav + 5s wait + 1s parse)
- **Total**: 6 sports × 8s = **48 seconds per scrape**
- **Results**: 177 events, 650 odds

### Known Issues
1. **Sequential bottleneck**: Sports scraped one-by-one (not parallel)
2. **Fixed waits**: 5s wait regardless of actual API response time
3. **Off-season waste**: Scrapes AFL/NRL in summer (0 events, still takes 8s each)
4. **No error recovery**: If one sport fails, no retry logic

---

## Current Implementation: Odds Matcher

**File**: `apps/api/src/api/routers/odds_matcher.py`

### How Matching Works

**Phase 1: Event Normalization** (lines 401-645)
```python
def normalize_event_name(name: str) -> str:
    # 1. Remove "1. " prefix (German teams: "1. FC Heidenheim")
    norm = re.sub(r'^\d+\.\s*', '', norm)

    # 2. Standardize separators: "vs" / "v" / "@" → all become "v"
    norm = re.sub(r'\s+vs\s+', ' v ', norm)

    # 3. Remove club suffixes: "FC", "CF", "AFC", etc.

    # 4. Apply 100+ team name normalizations:
    #    "Manchester United" → "manutd"
    #    "Wolverhampton Wanderers" → "wolves"
    #    "Pisa Sporting Club" → "pisa"

    # 5. Remove all spaces: "Liverpool v Chelsea" → "liverpoolv chelsea"

    # 6. Sort teams alphabetically (handles reversed order):
    #    Betfair: "Celtics @ Raptors" → "celticsvraptors"
    #    Ladbrokes: "Raptors vs Celtics" → "raptorsvsceltics"
    #    After sort both → "celticsvraptors"

    return normalized_key
```

**Phase 2: Event Grouping** (lines 647-659)
```python
# Group events by normalized name + competition
for event in events:
    norm_name = normalize_event_name(event.name)
    norm_comp = normalize_competition_name(event.competition.name)
    group_key = f"{norm_name}_{norm_comp}"

    event_groups[group_key].append(event)
```

**Phase 3: Selection Matching** (lines 712-963)
```python
# For each event group:
for events_in_group in event_groups.values():
    # Get all markets (H2H, Match Odds, Moneyline, etc.)
    markets = get_markets_for_events(events_in_group)

    # Group selections by normalized team name
    # "Liverpool" (Ladbrokes) + "Liverpool FC" (Betfair) → "liverpool"
    selection_groups = normalize_selections(markets)

    # For each selection (e.g., "Liverpool"):
    for norm_name, selections in selection_groups.items():
        # Query odds for ALL selection IDs with same normalized name
        back_odds = get_back_odds(selection_ids)  # Ladbrokes
        lay_odds = get_lay_odds(selection_ids)    # Betfair

        # Find best back (highest) and best lay (lowest)
        best_back = max(back_odds, key=lambda x: x.decimal_odds)
        best_lay = min(lay_odds, key=lambda x: x.decimal_odds)

        # Calculate matched bet
        pnl = matching_engine.calculate_matched_bet(
            back_bet, lay_bet, commission=0.06
        )
```

**Phase 4: Opportunity Ranking** (lines 1048-1055)
```python
# Sort by PnL% (higher = better)
# Normal bets: -1% loss > -5% loss
# Bonus bets: +80% profit > +70% profit
opportunities.sort(key=lambda x: x.pnl_percentage, reverse=True)
```

### Current Results
- **Opportunities found**: 92 (vs Outmatched's 127)
- **Gap**: Missing ~35 opportunities (73% match rate)
- **Coverage**: EPL, Serie A, Bundesliga, La Liga, NBA, NHL, Boxing

### Known Issues
1. **Missing normalizations**: Some Italian/German team names still mismatch
2. **Market filtering**: May be too strict (missing some valid H2H markets)
3. **Betfair scraper unreliable**: Intermittent "No bymarket data found" errors
4. **Performance**: Matching logic takes ~2s (acceptable, but room for optimization)

---

## Team Name Normalizations (100+ mappings)

**Current coverage** (lines 421-627 in odds_matcher.py):
```python
replacements = {
    # EPL (20 teams)
    'wolverhampton wanderers': 'wolves',
    'nottingham forest': 'nottingham',
    'brighton & hove albion': 'brighton',
    'manchester united': 'manutd',
    'leeds united': 'leeds',

    # German Bundesliga (18 teams)
    '1. fsv mainz 05': 'mainz',
    'fc st. pauli': 'stpauli',
    'borussia dortmund': 'dortmund',

    # Italian Serie A (20 teams)
    'pisa sporting club': 'pisa',
    'us sassuolo calcio': 'sassuolo',
    'internazionale': 'inter',

    # NBA (30 teams)
    'los angeles lakers': 'lalakers',
    'philadelphia 76ers': 'sixers',

    # NHL (32 teams)
    'edmonton oilers': 'oilers',
    'toronto maple leafs': 'mapleleafs',

    # A-League, Champions League, etc.
}
```

**Duplicate normalizations**: Same mappings exist in both `normalize_event_name()` and `normalize_selection_name()` (DRY violation - maintenance burden for 100+ bookmakers)

---

## Scaling Challenges (1000+ Users, 100+ Bookmakers)

### 1. **Scraping Performance** (Current Bottleneck)
**Problem**:
- 2 bookmakers × 6 sports × 8s = **96s total** (too slow for 1000+ users)
- With 100 bookmakers: 100 × 48s = **80 minutes** (unacceptable)

**Constraints**:
- All users share same cached odds (global cache, 5-15 min TTL)
- Anti-bot systems require delays (TAB needs 1-3s between requests)
- Rotating proxy costs scale linearly (~$30/mo per 20 bookmakers)
- Playwright browser instances consume memory (~150MB each)

**Questions**:
1. How to parallelize sport scraping without race conditions in `captured_data`?
2. Should we scrape all sports for all bookmakers, or intelligently skip off-season/low-event sports?
3. Can we use dynamic waits (networkidle) instead of fixed 5s delays?
4. Should we move to direct API calls (bypass Playwright) for bookmakers that allow it?

### 2. **Database Growth** (Odds Time-Series)
**Problem**:
- Each bookmaker × 200 events × 3 selections × 1 market = 600 odds per bookmaker
- 100 bookmakers = 60,000 odds per snapshot
- At 5-min intervals = 12 snapshots/hour × 24h × 30 days = 21.6M odds/month
- PostgreSQL performance degrades with 100M+ rows without partitioning

**Current approach**:
- `is_current = true` flag on latest odds
- Old odds deleted immediately (line 317 in save_odds.py)
- **Problem**: No historical data for analytics/trends

**Questions**:
1. Should we implement time-series partitioning (by month)?
2. Archive old odds to S3/cheap storage for analytics?
3. Implement read replicas for 1000+ concurrent matcher queries?

### 3. **Matching Engine Complexity** (100+ Bookmakers)
**Problem**:
- Currently: Match Ladbrokes (back) vs Betfair (lay)
- At scale: Match **best** back across 100 bookmakers vs Betfair
- Event normalization failures compound (100 bookmakers = 100 name variations)

**Current approach**:
- 100+ hard-coded team mappings in Python dict
- Manual discovery of mismatches (user reports + DB queries)

**Questions**:
1. Should we use fuzzy matching (fuzzywuzzy, rapidfuzz) instead of hard-coded mappings?
2. Build auto-learning normalization (log failed matches → ML model suggests mappings)?
3. Centralize team/competition reference data (canonical names table)?
4. How to handle bookmaker-specific quirks (Betfair uses "@", Ladbrokes uses "vs", etc.)?

### 4. **Anti-Bot Detection** (Critical for 100+ Bookmakers)
**Current approach**:
- Playwright with browser fingerprint (User-Agent, viewport, locale)
- Sequential requests (1-3s delays)
- TAB disabled due to Akamai blocking

**Scaling concerns**:
- Each bookmaker has different anti-bot tech (Cloudflare, Akamai, PerimeterX, custom)
- IP reputation shared across all users (single scraping server)
- Rotating proxies expensive at scale ($30/mo × 5 tiers = $150/mo)

**Questions**:
1. Two-tier architecture: Direct HTTP for "easy" bookmakers, proxy for "hard" ones?
2. Rotating user agents / TLS fingerprints per bookmaker?
3. Rate limiting per bookmaker (Redis-based locks)?
4. Should we scrape from multiple IPs (different cloud providers)?

---

## Specific Improvement Requests

### 1. **Ladbrokes Scraper Performance**
**Goal**: Reduce 48s → 15s per bookmaker

**Options to evaluate**:
- Parallel sport scraping via `asyncio.gather()` (estimated 40s savings)
- Dynamic wait times (wait for network idle, not fixed 5s)
- Skip off-season sports (AFL in summer, NRL in winter)
- Direct API calls to `https://api.ladbrokes.com.au/v2/sport/event-request?category_ids=X`

**Constraints**:
- Must not break existing functionality
- Must handle race conditions in `captured_data` list
- Must respect anti-bot delays (1-3s between requests to same domain)

### 2. **Odds Matcher Accuracy**
**Goal**: Increase match rate from 73% → 90%+ (92 → 114+ opportunities)

**Suspected issues**:
- Missing team normalizations (discover via DB query)
- Market type filtering too strict (missing some H2H markets)
- Betfair scraper intermittent failures (timing issue)
- Competition name variations not all covered

**Requests**:
1. Analyze current mismatches (events with both Ladbrokes + Betfair odds but no match)
2. Suggest systematic approach to team normalization (fuzzy matching? ML?)
3. Identify market type patterns we're missing
4. Fix Betfair scraper reliability (increase wait time? retry logic?)

### 3. **Code Quality for Scale**
**Current issues**:
- Team normalizations duplicated in 2 functions (DRY violation)
- Hard-coded competition filters in each scraper
- No centralized bookmaker configuration
- Sequential scraping in `scrape_service.py` (lines 145-150)

**Requests**:
1. Refactor normalizations into centralized service
2. Create bookmaker config schema (YAML/JSON) for 100+ bookmakers
3. Design scraper factory pattern (reduce code duplication)
4. Implement robust error handling + retry logic
5. Add structured logging for production monitoring

---

## Questions for Claude

1. **Architecture**: Should we move to background worker queue (Redis/Celery) vs current synchronous scraping?
2. **Normalization**: Best approach for 100+ bookmakers? (fuzzy matching vs hard-coded vs ML)
3. **Performance**: Which optimization gives best ROI? (parallel sports vs dynamic waits vs direct APIs)
4. **Database**: Time-series partitioning strategy for 100M+ odds?
5. **Anti-bot**: Two-tier proxy strategy (direct + rotating) - how to implement?
6. **Monitoring**: What metrics to track for production? (scrape success rate, match rate, latency, etc.)

---

## Key Files to Review

**Scrapers**:
- `apps/worker/src/scrapers/ladbrokes_scraper.py` (464 lines) - Playwright scraper
- `apps/worker/src/scrapers/betfair_scraper.py` (similar pattern)
- `apps/worker/src/scrapers/base.py` - Abstract base class
- `apps/worker/src/jobs/scrape_service.py` - Orchestrates all scrapers

**Matching**:
- `apps/api/src/api/routers/odds_matcher.py` (1071 lines) - Main matcher endpoint
- `apps/api/src/api/services/matching_engine.py` - PnL calculations
- `apps/api/src/api/services/save_odds.py` - Database persistence

**Database**:
- `apps/api/src/api/models/odds.py` - SQLAlchemy models

---

## Success Metrics

**Current state**:
- Scrapers: 2 bookmakers, 6 sports, 75s total
- Matcher: 92 opportunities (73% vs Outmatched)
- Database: 16,525 odds snapshots

**Target state**:
- Scrapers: 100+ bookmakers, <30s per bookmaker, 90%+ success rate
- Matcher: 90%+ match rate vs competitors
- Database: Handle 100M+ odds with <100ms query time
- Users: Support 1000+ concurrent without performance degradation

---

## Additional Context

- Currently on commit `6a3bf4d` - Italian/German team normalizations
- DAILY.md tracks progress (92+ opportunities vs 127 on Outmatched)
- Performance analysis documented: Sequential scraping is main bottleneck
- All services running in Docker (mb_web, mb_api, mb_db, mb_redis)
- Using Playwright browser reuse (shared instance across scrapes)

**Competitor research**: Outmatched.com owner confirmed:
- Cloud server (not home IP)
- Rotating residential proxy for anti-bot sites (TAB, Sportsbet)
- Direct scraping for easy sites (Betfair)
- ~20s refresh time (vs our 75s)
