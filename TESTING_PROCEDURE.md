# Testing Procedure: Betfair Scraper + Fuzzy Matching

This document provides step-by-step testing procedures to verify the matched betting platform is working correctly after the Betfair scraper and fuzzy matching implementation.

## Prerequisites

- Docker containers running: `pnpm dev:up`
- Database seeded with bookmakers and plans
- Clerk authentication configured

---

## Test Suite 1: Scraper Tests (Isolated)

### Test 1.1: TAB Scraper
**Purpose**: Verify TAB scraper still works correctly

```bash
# Run from repository root
docker exec mb_api bash -c "cd /workspace && python test_tab_scraper.py"
```

**Expected Results:**
- ✅ Status: SUCCESS
- ✅ Events scraped: ~10 EPL events
- ✅ Odds scraped: ~30+ odds (home/away/draw for each event)
- ✅ Each event shows:
  - Event name (e.g., "Liverpool v Man United")
  - Competition: English Premier League
  - Start time (future date)
  - Home/away/draw odds with decimal format

**Failure Indicators:**
- ❌ Status: FAILED
- ❌ No events captured
- ❌ HTTP errors or timeouts
- ❌ "No EPL markets found" error

---

### Test 1.2: Betfair Scraper
**Purpose**: Verify Betfair scraper works and bypasses Cloudflare

```bash
docker exec mb_api bash -c "cd /workspace && timeout 90 python test_betfair_scraper.py"
```

**Expected Results:**
- ✅ Status: SUCCESS
- ✅ Events scraped: 5 EPL events (limited to 5 in test)
- ✅ Odds scraped: 15 odds (3 per event: home/away/draw lay odds)
- ✅ Each event shows:
  - Event name (e.g., "Man City v Everton")
  - Lay odds with decimal format
  - Liquidity amounts (e.g., "$1345.89")
  - Selection keys: home/away/draw

**Failure Indicators:**
- ❌ Status: FAILED
- ❌ "No events captured from Betfair"
- ❌ Playwright timeout or browser crash
- ❌ "No bymarket data found"
- ❌ All events show "no name" or "no odds"

---

### Test 1.3: Both Scrapers + Fuzzy Matching
**Purpose**: Verify both scrapers work together and events match correctly

```bash
docker exec mb_api bash -c "cd /workspace && timeout 120 python test_both_scrapers.py"
```

**Expected Results:**
- ✅ TAB Events: 10
- ✅ Betfair Events: 10
- ✅ Matched Events: 8-10 (80-100% match rate)
- ✅ Total Opportunities: 24-30
- ✅ Match scores shown:
  - Perfect matches (100%): e.g., "Fulham v Arsenal"
  - Good matches (80-99%): e.g., "Man United" vs "Man Utd" (86%)
- ✅ Matched opportunities show:
  - TAB back odds
  - Betfair lay odds
  - Profitability indicator

**Failure Indicators:**
- ❌ Matched Events: 0-5 (below 50% match rate)
- ❌ No opportunities found
- ❌ Scraper errors from either TAB or Betfair
- ❌ Match scores all below 70%

---

## Test Suite 2: Database Integration

### Test 2.1: Check Database Seeding
**Purpose**: Verify bookmakers and plans are seeded

```bash
docker exec -it mb_db psql -U postgres -d mb_dev
```

**SQL Queries:**
```sql
-- Check bookmakers exist
SELECT code, display_name, tier, is_active
FROM bookmakers
WHERE code IN ('tab', 'betfair')
ORDER BY code;

-- Expected: 2 rows (tab and betfair), both active

-- Check plans exist
SELECT code, display_name, price_monthly, bookmaker_limit
FROM plans
ORDER BY price_monthly;

-- Expected: 3 rows (free, premium, diamond)

-- Exit psql
\q
```

**Expected Results:**
```
Bookmakers:
code    | display_name | tier | is_active
--------|--------------|------|----------
betfair | Betfair      | FREE | t
tab     | TAB          | FREE | t

Plans:
code    | display_name | price_monthly | bookmaker_limit
--------|--------------|---------------|----------------
free    | Free         | 0.00          | 2
premium | Premium      | 29.00         | 16
diamond | Diamond      | 99.00         | 103
```

**Failure Indicators:**
- ❌ No bookmakers found
- ❌ Bookmakers are inactive
- ❌ No plans found

---

### Test 2.2: Manual Scrape + Database Save
**Purpose**: Verify scrapers can save data to database with fuzzy matching

```bash
# Start containers with logs visible
docker exec -it mb_api bash

# Inside container, run scrape service manually
cd /workspace
python -c "
import sys
sys.path.insert(0, 'apps/worker/src')
sys.path.insert(0, 'apps/api/src')

import asyncio
from jobs.scrape_service import trigger_scrape

async def test():
    result = await trigger_scrape(sport='soccer', limit=5)
    print('\n=== SCRAPE RESULT ===')
    print(f'Success: {result[\"success\"]}')
    print(f'Bookmakers scraped: {result[\"bookmakers_scraped\"]}')
    print(f'Events saved: {result[\"events_saved\"]}')
    print(f'Odds saved: {result[\"odds_saved\"]}')
    print(f'Errors: {result[\"errors\"]}')

asyncio.run(test())
"

# Exit container
exit
```

**Expected Results:**
- ✅ Success: True
- ✅ Bookmakers scraped: 2 (TAB + Betfair)
- ✅ Events saved: 5-10
- ✅ Odds saved: 50-100+
- ✅ Errors: 0 or minimal
- ✅ Log messages show:
  - "Fuzzy matched event: 'X' -> 'Y' (score: 0.XX)"
  - "Creating new event: X"
  - "Saved scrape result"

**Failure Indicators:**
- ❌ Success: False
- ❌ Bookmakers scraped: 0 or 1
- ❌ Database connection errors
- ❌ "Bookmaker 'betfair' not found in database"
- ❌ Multiple "Failed to save event" errors

---

### Test 2.3: Verify Data in Database
**Purpose**: Confirm events and odds are in database with correct fuzzy matching

```bash
docker exec -it mb_db psql -U postgres -d mb_dev
```

**SQL Queries:**
```sql
-- Check events were saved
SELECT id, name, start_time, status,
       jsonb_object_keys(external_ids) as bookmaker_id
FROM events
WHERE competition_id IN (
  SELECT id FROM competitions WHERE name LIKE '%Premier League%'
)
ORDER BY start_time
LIMIT 10;

-- Should show events with external_ids from both TAB and Betfair

-- Check odds snapshots exist for both bookmakers
SELECT
  e.name as event_name,
  b.code as bookmaker,
  s.name as selection,
  os.decimal_odds,
  os.available_amount as liquidity
FROM odds_snapshots os
JOIN selections s ON os.selection_id = s.id
JOIN markets m ON s.market_id = m.id
JOIN events e ON m.event_id = e.id
JOIN bookmakers b ON os.bookmaker_id = b.id
WHERE b.code IN ('tab', 'betfair')
  AND os.is_current = true
ORDER BY e.name, b.code, s.name
LIMIT 20;

-- Should show odds from both TAB (back) and Betfair (lay) for same events

-- Check fuzzy matching worked - events with multiple external_ids
SELECT
  name,
  start_time,
  jsonb_object_keys(external_ids) as external_id_keys,
  jsonb_array_length(jsonb_object_keys(external_ids)::jsonb) as num_bookmakers
FROM events
WHERE jsonb_typeof(external_ids) = 'object'
  AND external_ids != '{}'::jsonb
ORDER BY start_time DESC
LIMIT 10;

\q
```

**Expected Results:**
- ✅ Events exist with future start times
- ✅ external_ids contains keys from both bookmakers
- ✅ Odds exist from both TAB and Betfair for same events
- ✅ TAB odds don't have liquidity (NULL)
- ✅ Betfair odds have liquidity values

**Failure Indicators:**
- ❌ No events in database
- ❌ external_ids only has one bookmaker
- ❌ Only TAB odds or only Betfair odds (not both)
- ❌ All events are duplicated (fuzzy matching failed)

---

## Test Suite 3: API Endpoints

### Test 3.1: Start Development Environment
**Purpose**: Ensure web app and API are running

```bash
# From repository root
pnpm dev:up

# Check containers are healthy
pnpm dev:ps
```

**Expected Results:**
- ✅ mb_web (port 3000) - healthy
- ✅ mb_api (port 8000) - healthy
- ✅ mb_db (port 5432) - healthy
- ✅ mb_redis (port 6379) - healthy

---

### Test 3.2: Test Odds Refresh Endpoint (via UI or cURL)

**Option A: Via UI (Recommended)**
```bash
# Open browser
http://localhost:3000/dashboard/odds-matcher

# Login with Clerk (if not logged in)
# Click "Refresh Odds" button
# Observe loading state and results
```

**Option B: Via cURL (if you have JWT token)**
```bash
# Get your JWT token from browser DevTools:
# Open Network tab → Click "Refresh Odds" → Copy Authorization header

curl -X POST http://localhost:8000/odds/refresh \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"force": false}'
```

**Expected Results:**
- ✅ Status: 200 OK
- ✅ Response body:
  ```json
  {
    "success": true,
    "message": "Refreshed 2 bookmakers - XX odds updated",
    "opportunities_count": 50+,
    "last_refresh": "2025-10-12T..."
  }
  ```
- ✅ Takes 60-90 seconds (normal for browser automation)
- ✅ Subsequent calls within 5 minutes return cached data

**Failure Indicators:**
- ❌ Status: 500 Internal Server Error
- ❌ Status: 429 Rate limit (if called too frequently)
- ❌ "Refresh failed" message
- ❌ success: false
- ❌ Timeout after 120 seconds

---

### Test 3.3: Test Odds Matcher Endpoint

**Via UI:**
```bash
# Open browser
http://localhost:3000/dashboard/odds-matcher

# After odds refresh completes, page should show:
# - Table with matched betting opportunities
# - Each row shows event name, bookmaker, back/lay odds, profit/loss
```

**Via cURL:**
```bash
curl -X GET "http://localhost:8000/odds/matcher?stake=100&bet_type=normal&limit=20" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE"
```

**Expected Results:**
- ✅ Status: 200 OK
- ✅ Array of opportunities (5-20 items)
- ✅ Each opportunity has:
  - event_name, sport_name, competition_name
  - back_bookmaker_code (e.g., "tab")
  - back_odds, back_stake
  - lay_odds, lay_stake, lay_liability
  - profit_if_back_wins, profit_if_lay_wins
  - qualifying_loss (negative for normal bets)
  - rating (0-100)

**Example Response:**
```json
[
  {
    "event_name": "Liverpool v Man United",
    "back_bookmaker_code": "tab",
    "back_odds": 1.62,
    "lay_odds": 1.66,
    "qualifying_loss": -2.47,
    "pnl_percentage": -2.47,
    "rating": 95.3
  }
]
```

**Failure Indicators:**
- ❌ Empty array `[]` (no opportunities found)
- ❌ Status: 500 Internal Server Error
- ❌ Status: 403 Forbidden (plan access issue)
- ❌ All opportunities have matching event names but no odds

---

## Test Suite 4: UI/Frontend Tests

### Test 4.1: Login Flow
**Purpose**: Verify Clerk authentication works

```bash
# Open browser
http://localhost:3000

# Should redirect to Clerk login
# Login with test account
# Should redirect to /dashboard
```

**Expected Results:**
- ✅ Redirects to Clerk login page
- ✅ After login, redirects to /dashboard
- ✅ User menu shows logged in state
- ✅ Dashboard navigation visible

**Failure Indicators:**
- ❌ Stuck on login page after submitting credentials
- ❌ "Invalid credentials" errors
- ❌ White screen or React errors
- ❌ Clerk environment variables not set

---

### Test 4.2: Odds Matcher UI
**Purpose**: Verify odds matcher page displays correctly

```bash
# Navigate to odds matcher
http://localhost:3000/dashboard/odds-matcher
```

**Expected Results:**
- ✅ "Odds Matcher" heading visible
- ✅ Filters panel:
  - Stake input (default: $100)
  - Bet Type dropdown (Normal/Bonus)
  - Bookmaker filters
  - Competition filters
- ✅ "Refresh Odds" button visible
- ✅ Table with columns:
  - Event, Sport, Time
  - Bookmaker, Back Odds, Lay Odds
  - Stake, Profit/Loss, Rating
- ✅ Calculator button on each row

**Failure Indicators:**
- ❌ 404 Not Found
- ❌ React error boundary
- ❌ Missing components (filters, table, buttons)
- ❌ Styling broken (Tailwind not loading)

---

### Test 4.3: Refresh Odds Flow
**Purpose**: Verify full scrape → save → display pipeline

**Steps:**
1. Click "Refresh Odds" button
2. Observe loading state (button disabled, spinner visible)
3. Wait 60-90 seconds for scraping to complete
4. Observe success message: "Refreshed odds successfully"
5. Table auto-refreshes with new data
6. Verify opportunities are displayed

**Expected Results:**
- ✅ Button shows loading state
- ✅ After completion, success toast/notification
- ✅ Table populates with 10-30 opportunities
- ✅ Events show EPL matches
- ✅ Odds are recent (within 5 minutes)
- ✅ Ratings are between 70-100

**Failure Indicators:**
- ❌ Button never re-enables
- ❌ Error toast: "Refresh failed"
- ❌ Table remains empty after refresh
- ❌ Network error in browser console
- ❌ 500 error from API

---

### Test 4.4: Calculator Modal
**Purpose**: Verify bet calculator works

**Steps:**
1. Click calculator icon on any row
2. Modal opens with pre-filled odds
3. Adjust stake amount
4. Observe calculations update in real-time
5. Check profit/loss scenarios

**Expected Results:**
- ✅ Modal opens smoothly
- ✅ Back odds, lay odds pre-filled from selected opportunity
- ✅ Stake input works (default $100)
- ✅ Calculations show:
  - Lay stake required
  - Lay liability
  - Profit if back wins
  - Profit if lay wins
  - Qualifying loss (average)
- ✅ Numbers update as stake changes
- ✅ Close button works

**Failure Indicators:**
- ❌ Modal doesn't open
- ❌ Odds not pre-filled
- ❌ Calculations show NaN or Infinity
- ❌ Typing in stake input doesn't update calculations
- ❌ Modal can't be closed

---

## Test Suite 5: Error Handling

### Test 5.1: Rate Limiting
**Purpose**: Verify rate limiting works

**Steps:**
1. Click "Refresh Odds" button
2. Immediately click "Refresh Odds" again (within 30 seconds)

**Expected Results:**
- ✅ Second click shows error: "Please wait 30 seconds between refresh requests"
- ✅ Status: 429 Too Many Requests
- ✅ Button remains enabled after error
- ✅ Can retry after 30 seconds

---

### Test 5.2: No Odds Available
**Purpose**: Verify graceful handling when no odds available

**Steps:**
1. Clear all odds from database:
   ```bash
   docker exec -it mb_db psql -U postgres -d mb_dev -c "UPDATE odds_snapshots SET is_current = false;"
   ```
2. Navigate to odds matcher page
3. Observe empty state

**Expected Results:**
- ✅ Table shows empty state message: "No opportunities found"
- ✅ No React errors
- ✅ Refresh button still works
- ✅ After refresh, odds populate again

---

### Test 5.3: Scraper Failure Recovery
**Purpose**: Verify system handles scraper failures gracefully

**Steps:**
1. Stop internet connection temporarily (simulate network failure)
2. Click "Refresh Odds"
3. Observe error handling
4. Restore internet
5. Try refresh again

**Expected Results:**
- ✅ Error message displayed to user
- ✅ No white screen or crash
- ✅ After restoring connection, refresh works
- ✅ Cached odds still available (if within 5 min cache window)

---

## Test Suite 6: Regression Tests

### Test 6.1: Existing Features Still Work
**Purpose**: Ensure new code didn't break existing functionality

**Checklist:**
- ✅ User registration via Clerk works
- ✅ Billing/pricing page accessible (/billing)
- ✅ Plans display correctly (Free, Premium, Diamond)
- ✅ Dashboard navigation works
- ✅ Logout works
- ✅ Mobile responsive design intact
- ✅ Dark mode toggle (if implemented)

---

### Test 6.2: Database Migrations
**Purpose**: Verify database schema is correct

```bash
# Check migration status
docker exec mb_api alembic current

# Should show current revision

# Run any pending migrations
docker exec mb_api alembic upgrade head

# Verify no errors
```

---

## Quick Smoke Test (5 minutes)

If you're short on time, run this minimal test suite:

```bash
# 1. Check containers
pnpm dev:ps
# Expected: All containers running

# 2. Test scrapers
docker exec mb_api bash -c "cd /workspace && python test_both_scrapers.py"
# Expected: 8-10 matched events

# 3. Open UI
# Navigate to: http://localhost:3000/dashboard/odds-matcher
# Expected: Page loads without errors

# 4. Click "Refresh Odds"
# Expected: Completes in ~90s, shows success message

# 5. Verify opportunities displayed
# Expected: Table shows 10+ rows with odds
```

---

## Troubleshooting Common Issues

### Issue: Betfair scraper fails with "No events captured"
**Solution:**
- Check Playwright browser is installed: `docker exec mb_api playwright install chromium`
- Verify Cloudflare isn't blocking: Check logs for "403 Forbidden"
- Increase timeout if network is slow

### Issue: Fuzzy matching creates duplicate events
**Solution:**
- Check match threshold (should be ≥0.75)
- Verify time window (±3 hours)
- Check normalization logic in `normalize_team_name()`

### Issue: No odds in UI after refresh
**Solution:**
- Check API logs: `docker logs mb_api`
- Verify bookmakers are active: `SELECT * FROM bookmakers WHERE is_active = true;`
- Check plan permissions: User might not have access to bookmakers

### Issue: UI shows old odds after refresh
**Solution:**
- Clear Redis cache: `docker exec mb_redis redis-cli FLUSHALL`
- Hard refresh browser: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
- Check `is_current` flag in database

---

## Success Criteria Summary

✅ **All tests pass** = System is working correctly
⚠️ **1-2 tests fail** = Investigate specific failures, may be environment-specific
❌ **3+ tests fail** = Major issue, review recent changes and logs

---

## Logging and Debugging

**View API logs:**
```bash
docker logs mb_api -f --tail 100
```

**View web logs:**
```bash
docker logs mb_web -f --tail 100
```

**View database queries:**
```bash
# Enable query logging in PostgreSQL
docker exec -it mb_db psql -U postgres -d mb_dev
ALTER SYSTEM SET log_statement = 'all';
SELECT pg_reload_conf();
```

**Check Redis cache:**
```bash
docker exec -it mb_redis redis-cli
KEYS *
GET odds_last_refresh_global
```

---

## Contact

If you encounter issues not covered in this guide:
1. Check logs for error messages
2. Review git commits for recent changes
3. Consult CLAUDE.md for project architecture
4. Check GitHub issues

---

**Document Version**: 1.0
**Last Updated**: 2025-10-12
**Author**: Claude Code Session
