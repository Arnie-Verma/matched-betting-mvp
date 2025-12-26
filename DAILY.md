# Daily Progress Log

Track daily work. Compress old entries weekly to keep focused on current tasks.

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
