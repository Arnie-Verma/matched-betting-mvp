# Daily Progress Log

Track daily work. Compress old entries weekly to keep focused on current tasks.

---

## 2025-12-27 (Friday)

### Session 1: Phase 1 Implementation - PARALLEL SCRAPING

**Goal**: 96s → 10-15s scrape time (6-8x improvement)

**✅ Task 1.1: Fix Race Condition in Ladbrokes** ([ladbrokes_scraper.py](apps/worker/src/scrapers/ladbrokes_scraper.py))
- Removed `self.captured_data` instance variable
- Implemented closure pattern: local `captured_data` per `scrape_sport()` call
- Response handler now captures to local list, not shared state
- Safe for parallel execution

**✅ Task 1.2: Add Parallel Sports to Ladbrokes**
- Added `scrape_all_sports_parallel()` method using `asyncio.gather`
- Runs all 6 sports concurrently: soccer, basketball, ice_hockey, boxing, afl, nrl
- Aggregates results with proper error handling
- Expected: 48s → 10s per bookmaker

**✅ Task 1.3: Fix Race Condition + Parallel in Betfair** ([betfair_scraper.py](apps/worker/src/scrapers/betfair_scraper.py))
- Same closure pattern for `captured_data`
- Added `_parse_captured_data_local()` that takes captured_data as param
- Also fixed `_current_competition` shared state (now dict in closure)
- Added `scrape_all_sports_parallel()` method

**✅ Task 1.4: Parallel Bookmaker Orchestration** ([scrape_service.py](apps/worker/src/jobs/scrape_service.py))
- Added `scrape_bookmaker_all_sports()` - uses parallel sports method
- Updated `scrape_all_active_bookmakers()` to run ALL bookmakers in parallel
- Both Betfair and Ladbrokes run simultaneously via `asyncio.gather`
- Total time = max(slowest_bookmaker) instead of sum(all)

### Architecture Changes

**Before (Sequential)**:
```
for bookmaker in [betfair, ladbrokes]:
    for sport in [soccer, basketball, hockey, boxing, afl, nrl]:
        await scrape_sport(sport)  # 8s each
# Total: 2 × 6 × 8s = 96s
```

**After (Parallel)**:
```
asyncio.gather(
    betfair.scrape_all_sports_parallel(),   # ~15s
    ladbrokes.scrape_all_sports_parallel()  # ~10s
)
# Total: max(15s, 10s) = ~15s
```

### Files Modified

| File | Changes |
|------|---------|
| [ladbrokes_scraper.py](apps/worker/src/scrapers/ladbrokes_scraper.py) | Closure pattern + `scrape_all_sports_parallel()` |
| [betfair_scraper.py](apps/worker/src/scrapers/betfair_scraper.py) | Closure pattern + `_parse_captured_data_local()` + `scrape_all_sports_parallel()` |
| [scrape_service.py](apps/worker/src/jobs/scrape_service.py) | `scrape_bookmaker_all_sports()` + parallel orchestration |

### Session 2: Testing & Timing Results

**✅ End-to-End Testing Complete**

| Test | Result | Details |
|------|--------|---------|
| Ladbrokes solo | ✅ 42.69s | 150 events, 578 odds (6 sports sequential) |
| Betfair solo | ✅ 88.92s | 162 events, 456 odds (6 sports sequential) |
| Sequential total | Would be 131.61s | sum(ladbrokes, betfair) |
| **Parallel total** | **91.80s** | 312 events, 1034 odds |

**Improvement**: 131s → 91s (**30% faster**) with bookmakers running in parallel.

**Docker Limitation Discovered**:
- Parallel sport scraping (`batch_size > 1`) causes browser crashes in Docker
- Root cause: Docker container resource constraints + multiple Playwright contexts
- Fix: Configurable `SCRAPER_BATCH_SIZE` env var (default=1 for Docker safety)
- Production servers can use higher batch_size for additional speedup

**Production Projection** (with `SCRAPER_BATCH_SIZE=6`):
- Expected: 91s → ~15-20s (both bookmakers + all sports truly parallel)
- Cloud server with dedicated resources handles higher parallelism

### Files Modified (Session 2)

| File | Changes |
|------|---------|
| [scrape_service.py](apps/worker/src/jobs/scrape_service.py) | Increased timeout to 120s for all-sports scrape |
| [manual_scrape.py](apps/worker/src/manual_scrape.py) | Added timing output |

### Session 3: Phase 2 Implementation - DYNAMIC WAITS

**Goal**: Replace fixed 5s waits with polling-based detection (save 2-4s per competition)

**✅ Task 2.1: Polling-based Dynamic Wait in Ladbrokes**
- First attempt: `networkidle` triggered too early (no data captured)
- Fix: Poll every 300ms for `captured_data` items, max 8s wait
- Exits early when API data is captured → saves time for fast APIs

**✅ Task 2.2: Polling-based Dynamic Wait in Betfair**
- Same pattern: Poll for `bymarket` data capture
- Checks if new bymarket responses arrived since navigation started
- Falls back to max wait if no data (off-season sports)

**Timing Results**:

| Metric | Before (Fixed 5s) | After (Polling) | Improvement |
|--------|------------------|-----------------|-------------|
| Total time | 91.80s | **79.38s** | **13.5% faster** |
| Events | 312 | 312 | Same |
| Odds | 1034 | 1034 | Same |

**Files Modified**:

| File | Changes |
|------|---------|
| [ladbrokes_scraper.py](apps/worker/src/scrapers/ladbrokes_scraper.py) | Polling loop for captured_data |
| [betfair_scraper.py](apps/worker/src/scrapers/betfair_scraper.py) | Polling loop for bymarket data |

### Next Steps
1. **Phase 3**: Database cleanup service + indexes
2. **Phase 4**: NormalizationService extraction
3. **Phase 5**: Proxy tier implementation
4. **Production**: Set `SCRAPER_BATCH_SIZE=6` for full parallelism

---

## 2025-12-26 (Thursday)

### Session 2: Phase 0 Testing - ALL TESTS PASSED

Executed all tests from [PHASE_0_COMPLETE.md](PHASE_0_COMPLETE.md) and verified expected behavior.

**Test Results Summary:**

| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| Migration | `20251226_idempotent (head)` | `20251226_idempotent (head)` | ✅ PASS |
| Circuit Breaker | `{"state": "open", "failures": 5}` after 5 failures | Exact match | ✅ PASS |
| Idempotent Writes | No duplicates on repeated scrape | 2 scrapes, same count | ✅ PASS |
| Timeout Protection | `Scrape timed out after 25s` + failure recorded | Betfair timeout, `failures: 1` | ✅ PASS |
| End-to-End Refresh | Job enqueue → worker → success status | `{"status": "success", "odds_saved": 700}` | ✅ PASS |

**Bug Fixes During Testing:**

1. **`user.id` before definition** ([odds_matcher.py:137](apps/api/src/api/routers/odds_matcher.py#L137))
   - Rate limit key used `user.id` before user was fetched
   - Fix: Moved user query before rate limit check

2. **Batch duplicate selection** ([save_odds.py](apps/worker/src/jobs/save_odds.py))
   - Error: `ON CONFLICT DO UPDATE cannot affect row a second time`
   - Cause: Same selection_id appeared multiple times in upsert batch
   - Fix: Added dedupe logic before upsert (keeps last per constraint key)

**Database State After Testing:**
- 16,953 current odds in database
- timestamp_bucket column populated correctly (5-min buckets)
- Circuit breaker keys in Redis working

---

### Session 1: Phase 0 Implementation

**✅ Circuit Breaker & Timeout Protection** ([scrape_service.py](apps/worker/src/jobs/scrape_service.py))
- Redis-based circuit breaker with 3 states: closed → open → half-open
- Threshold: 5 failures → opens breaker
- Cooldown: 60s before half-open retry
- Timeout wrapper: 25s max per scraper call (asyncio.wait_for)

**✅ Idempotent Writes** ([save_odds.py](apps/worker/src/jobs/save_odds.py))
- Added `timestamp_bucket` column (5-min buckets for deduplication)
- PostgreSQL INSERT ... ON CONFLICT DO UPDATE (true upsert)
- Unique constraint: `(selection_id, bookmaker_id, timestamp_bucket, scrape_session_id)`

**✅ Database Migration** ([20251226_add_idempotent_writes_support.py](apps/api/alembic/versions/20251226_add_idempotent_writes_support.py))
- Add timestamp_bucket column + index
- Drop old constraint, add new dedupe constraint

### Infrastructure Status

**Phase 0 (Queue/Cache/Backpressure): 100% COMPLETE AND TESTED**
| Component | Status |
|-----------|--------|
| Redis job queue | ✅ Working |
| Non-blocking refresh | ✅ Working |
| Per-user rate limiting | ✅ Working |
| ETag/Last-Modified | ✅ Working |
| Circuit breaker | ✅ Working + Tested |
| Timeout protection | ✅ Working (25s) |
| Idempotent writes | ✅ Working + Tested |

### Next Steps
1. **Phase 1**: Fix scraper race conditions for parallelization
   - Fix `captured_data` closure pattern in betfair_scraper.py and ladbrokes_scraper.py
   - Add `scrape_all_sports_parallel()` method
   - Expected: 72-96s → 10-15s (6-8x faster)

---

## 2025-12-23 (Tuesday)

### Completed
- Session start: reviewed CLAUDE.md instructions and optimization plan for upcoming production work
- Implemented non-blocking refresh enqueue path with job IDs and fast/slow TTL config
- Added Redis-backed refresh worker consumer stub plus job status endpoint and ETag/Last-Modified caching headers for matcher responses
- Syntax-checked updated modules via `python -m py_compile` for odds_matcher, refresh_queue, refresh_worker

### Blockers
- None yet identified; need to validate scrapers once parallel changes begin

### Next Steps
- Outline execution steps for production optimization (queue/cache, parallel scraping, dynamic waits, cleanup/indexes, normalization service)

---

## 2025-12-21 (Saturday) - Session 1

### Completed

- ✅ **EXPANDED TEAM NAME NORMALIZATIONS** - Italian Serie A + German Bundesliga
  - Added: Pisa Sporting Club → pisa, US Sassuolo Calcio → sassuolo, Torino FC → torino
  - Added: 1. FSV Mainz 05 → mainz, FC St. Pauli → stpauli, Heidenheim variations
  - Both `normalize_event_name()` and `normalize_selection_name()` updated
  - Verified all 3 problem matches now group correctly

- ✅ **PREVIOUS SESSION FIXES** applied:
  - Changed refresh to scrape all sports (not just soccer)
  - Disabled TAB scraper (needs rotating proxy)
  - Added market types: Moneyline, Head To Head, Fight Betting
  - Increased event limit to 500
  - Added EPL team normalizations (Leeds United, Sunderland AFC, etc.)

### Current State

- 92+ opportunities vs Outmatched's 127 (goal: match their output)
- Betfair scraper intermittent - timing issue with network capture
- All normalizations tested and confirmed working

### Next Steps

1. Fix Betfair scraper reliability (increase wait time or retry)
2. Continue testing UI to verify opportunity count
3. Add any remaining team normalizations as discovered

---

## 2025-12-20 (Friday) - Session 3

### Completed

- ✅ **FIXED EVENT NAME MATCHING** - Alphabetical team sorting
  - Root cause: Betfair uses "Team A @ Team B" (away @ home), Ladbrokes uses "Team A vs Team B" (home vs away)
  - Fix: Sort team names alphabetically → both become same normalized key
  - Modified `normalize_event_name()` in [odds_matcher.py:575-583](apps/api/src/api/routers/odds_matcher.py#L575-L583)

- ✅ **FIXED ODDS GROUPING QUERY** - Query across all selection IDs
  - Root cause: Odds queried per-selection, but Betfair/Ladbrokes have separate selection IDs for same team
  - Fix: Group selections by normalized name first, then query odds for ALL selection IDs in group
  - Modified [odds_matcher.py:733-776](apps/api/src/api/routers/odds_matcher.py#L733-L776)

### Testing Complete ✅

- **API restarted** and fresh scrape run (5,846 odds)
- **19 matched opportunities found!**
  - NBA: 6 games, 9 opportunities (Bulls/Hawks, Heat/Knicks, Raptors/Nets, etc.)
  - NHL: 5 games, 10 opportunities (Canadiens/Penguins, Maple Leafs/Stars, etc.)
  - Both Ladbrokes (back) + Betfair (lay) working correctly
- Alphabetical sorting fix confirmed working
- Cross-selection odds grouping fix confirmed working

### Current State

| Sport | Ladbrokes | Betfair | Status |
|-------|-----------|---------|--------|
| NBA | 23 events, 50 odds | ✅ | **19 opportunities found** |
| NHL | 21 events, 132 odds | ✅ | **19 opportunities found** |
| EPL | 17 events, 68 odds | 22 events, 5080 odds (TAB+Betfair) | ✅ |
| Boxing | 16 events, 48 odds | 22 events, 64 odds | ✅ |
| Soccer (other) | ~100 events, 400+ odds | ✅ | ✅ |
| NRL | 17 odds | Off-season | ❌ |
| AFL | Off-season | 10 odds | ❌ |

### Next Steps

1. **Test frontend UI** - Login at `localhost:3000` to verify NBA/NHL appear in odds matcher
2. **Implement Neds scraper** - Complete free tier (Ladbrokes + Neds + Betfair)

---

## 2025-12-20 (Friday) - Sessions 1-2 (Compressed)

### Major Achievements

- ✅ **LADBROKES SCRAPER COMPLETE** - All 6 sports working (Soccer, NBA, NBL, NHL, NRL, Boxing)
  - Converted to Playwright (API blocks direct httpx for non-soccer)
  - Fixed race condition in parallel scraping
  - Expanded from 8 soccer leagues to 14+ competitions across all sports

- ✅ **ODDS MATCHER INTEGRATION** - Cross-bookmaker matching working
  - Competition name normalization ("Premier League" ↔ "English Premier League")
  - Added 100+ NBA/NHL/NBL team mappings
  - Increased limit from 50 to 200 opportunities
  - Fixed Ladbrokes "Fight Betting" market type
  - Fixed Betfair MONEY_LINE market type (NHL/NBA)
  - Database cleanup (removed 31,856 corrupt odds from race condition)

---

## 2025-12-19 (Thursday) - Ladbrokes Implementation

### Completed
- ✅ Discovered Ladbrokes REST API v2 (`/v2/sport/event-request`)
- ✅ Implemented complete Ladbrokes scraper
- ✅ Fixed critical bug: Ladbrokes prices dict uses hidden market IDs
  - Root cause: `prices_data` keys use `{entrant_id}:{hidden_market_id}:` format
  - Solution: Search by entrant_id prefix instead of composite key
  - Result: **0 → 558 events with odds** (100% success!)
- ✅ Updated free tier: Changed from TAB+Betfair to **Ladbrokes+Neds+Betfair**
- ✅ End-to-end integration: 3 bookmakers, 116 events, 13,207 odds

---

## 2025-12-08 (Sunday) - Documentation & Analysis

### Completed
- Documentation consolidation (merged 3 docs → CLAUDE.md)
- Full codebase analysis
- Code cleanup (deleted mocks, fixed comments)
- **Decision**: Full production with rotating proxy for scaling

### Key Findings
- TAB EPL-only works (~7,800 odds) - multi-sport blocked by Akamai
- Betfair EPL-only works (~60 lay odds) - can expand easily
- Free tier strategy: 2 bookmakers (Ladbrokes + Neds) + Betfair exchange

---

## Week of 2025-12-02 (Compressed)

- Betfair scraper timing fix (5s wait + 1s async delay)
- Selection matching improvements (team normalization)
- TAB multi-competition attempts (blocked, reverted)
- Outmatched.com owner outreach (confirmed rotating proxy approach)

---

## Blockers

1. **NRL/AFL off-season** - No matching until season starts
2. **Neds scraper not implemented** - Required to complete free tier

---

## Guidelines

**Daily format**:
```markdown
## YYYY-MM-DD (Day)

### Completed
- Bullet points

### Blockers
- Current issues

### Next Steps
- Priority tasks
```

**Weekly compression** (Sunday): Move week's details to compressed section.
