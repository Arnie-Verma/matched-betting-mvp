# 🧪 Testing Procedure - Complete Matched Betting Flow

## ✅ Prerequisites Checklist

Before testing, verify these are complete:

```bash
# Check Docker containers
docker ps

# Should see:
# - mb_web (healthy)
# - mb_api (healthy)
# - mb_db (healthy)
# - mb_redis (healthy)

# Check database has data
docker exec mb_db psql -U postgres -d mb_dev -c "
SELECT
  (SELECT COUNT(*) FROM events) as events,
  (SELECT COUNT(*) FROM odds_snapshots WHERE is_current = true) as odds,
  (SELECT COUNT(DISTINCT bookmaker_id) FROM odds_snapshots WHERE is_current = true) as bookmakers;
"

# Should show:
# events: 3
# odds: 916 (458 TAB + 458 Betfair)
# bookmakers: 2
```

---

## 🎯 Test 1: Access Odds Matcher Page

### Steps:
1. Open browser to: **http://localhost:3000**
2. Log in with Clerk (if not already)
3. Navigate to: **http://localhost:3000/dashboard/odds-matcher**

### Expected Results:
✅ Page loads without errors
✅ See filter controls (stake, bet type, search)
✅ See "REFRESH ODDS" button
✅ See loading state or existing opportunities

---

## 🔄 Test 2: Refresh Button (First Click)

### Steps:
1. Click the **"REFRESH ODDS"** button
2. Watch for loading spinner

### Expected Results:
✅ Button shows spinning icon
✅ Button becomes disabled during refresh
✅ After 5-15 seconds, see message: "Refreshed 1 bookmakers - XXX odds updated"
✅ "Last updated:" timestamp appears
✅ See opportunities appear in table (or "No opportunities found")

### What's Happening:
- Frontend calls `/api/proxy/odds/refresh`
- Backend checks Redis cache (should be empty first time)
- Backend triggers TAB scraper
- TAB scrapes 3 EPL matches (~468 odds)
- Saves to database
- Updates Redis cache (5 min TTL)
- Returns result to frontend

---

## ⏱️  Test 3: Rate Limiting (Second Click)

### Steps:
1. Immediately click **"REFRESH ODDS"** again

### Expected Results:
✅ See error message: "Please wait 30 seconds between refresh requests"
✅ Button remains enabled (can try again)
✅ **HTTP 429** error shown

### What's Happening:
- Backend checks per-user rate limit in Redis
- User has key `odds_refresh_ratelimit:{user_id}` with 30s TTL
- Request rejected to prevent abuse

---

## 💾 Test 4: Global Cache (Third Click after 30s)

### Steps:
1. Wait 30 seconds
2. Click **"REFRESH ODDS"** again

### Expected Results:
✅ Button works (rate limit expired)
✅ Response is INSTANT (< 1 second)
✅ Message: "Using cached odds (updated XXs ago)"
✅ No actual scraping happens

### What's Happening:
- Rate limit key expired
- Global cache still valid (< 5 minutes)
- Backend returns cached timestamp
- No scraping triggered

---

## 🎲 Test 5: View Matched Betting Opportunities

### Steps:
1. After successful refresh, scroll through the opportunities table
2. Look for real EPL data:
   - Nottingham Forest vs Chelsea
   - Brighton vs Newcastle
   - Other EPL matches

### Expected Results:
✅ See 3 EPL events
✅ Each event has multiple market types (Result, Double Chance, etc.)
✅ TAB back odds (e.g., 3.25)
✅ Betfair lay odds (e.g., 3.30 - slightly higher)
✅ Calculated values:
   - Lay Stake
   - Lay Liability
   - Qualifying Loss / Profit
   - Rating (0-100)
   - PnL%

### Sample Expected Data:
```
Event: Nottingham Forest v Chelsea
Market: EPL Nott For-Chelsea Result
Selection: Nottinghm Forest
TAB Back: 3.25 @ $100
Betfair Lay: 3.30
Lay Stake: ~$98.48
Qualifying Loss: ~$1.52
Rating: 98.5
```

---

## 🔍 Test 6: Filter by Stake

### Steps:
1. Change stake from $100 to $200
2. Click "Search Opportunities"

### Expected Results:
✅ All lay stakes DOUBLE
✅ Qualifying losses DOUBLE
✅ PnL percentages STAY THE SAME
✅ Ratings STAY THE SAME

---

## 🎁 Test 7: Toggle Bet Type (Normal → Bonus)

### Steps:
1. Change "Bet Type" from "Normal" to "Bonus"
2. Click "Search Opportunities"

### Expected Results:
✅ Qualifying Loss becomes POSITIVE (profit!)
✅ PnL% changes dramatically
✅ Ratings recalculated

### Why:
- Bonus bets don't return the stake
- This changes the matched betting math
- Usually results in guaranteed profit

---

## 🔎 Test 8: Search for Specific Event

### Steps:
1. Type "Chelsea" in search box
2. Click "Search Opportunities"

### Expected Results:
✅ Only shows opportunities with "Chelsea" in event name
✅ Filter works immediately
✅ No API call needed (filters locally)

---

## 🧮 Test 9: Bet Calculator Modal

### Steps:
1. Find any opportunity
2. Click **"OPEN"** button
3. Modal appears with bet calculator

### Expected Results:
✅ Modal shows:
   - Event details (name, date, market)
   - Back bet details (bookmaker, odds, stake)
   - Lay bet details (odds, stake, liability, commission)
   - Outcome Matrix (2 scenarios)
   - Summary (qualifying loss/profit)

4. **Edit the back odds** (e.g., change 3.25 to 3.00)

### Expected Results:
✅ Lay stake recalculates instantly
✅ Outcome matrix updates
✅ Summary updates
✅ No page reload

5. **Edit the stake** (e.g., change $100 to $500)

### Expected Results:
✅ All values recalculate
✅ Liability scales proportionally

6. Click outside modal or "Close"

### Expected Results:
✅ Modal closes
✅ Return to opportunities table

---

## 🕐 Test 10: Cache Expiry (Wait 5+ Minutes)

### Steps:
1. Wait 6 minutes
2. Click **"REFRESH ODDS"**

### Expected Results:
✅ Takes 5-15 seconds (scraping happens)
✅ Message: "Refreshed 1 bookmakers - XXX odds updated"
✅ New timestamp
✅ Cache refreshed

### What's Happening:
- Global cache expired (5 min TTL)
- Backend triggers new scrape
- Fresh odds from TAB
- Updates database with new current odds (marks old as not current)
- Updates cache

---

## 🚫 Test 11: Error Handling

### Steps:
1. Stop the API container:
   ```bash
   docker stop mb_api
   ```

2. Click **"REFRESH ODDS"**

### Expected Results:
✅ Error message appears: "Failed to refresh odds"
✅ Red error box shows
✅ No crash

3. Restart API:
   ```bash
   docker start mb_api
   ```

---

## 📊 Test 12: Database Verification

### Check odds are being updated:
```bash
docker exec mb_db psql -U postgres -d mb_dev -c "
SELECT
  e.name as event,
  b.code as bookmaker,
  s.name as selection,
  os.decimal_odds as odds,
  os.is_current as current,
  os.timestamp
FROM odds_snapshots os
JOIN selections s ON s.id = os.selection_id
JOIN markets m ON m.id = s.market_id
JOIN events e ON e.id = m.event_id
JOIN bookmakers b ON b.id = os.bookmaker_id
WHERE e.name LIKE '%Chelsea%'
AND s.name = 'Chelsea'
ORDER BY os.timestamp DESC
LIMIT 5;
"
```

### Expected Results:
✅ See multiple timestamps for same event/selection
✅ Most recent has `is_current = true`
✅ Older ones have `is_current = false`

---

## ✅ Success Criteria

All tests pass if:

1. ✅ Odds matcher page loads with real data
2. ✅ Refresh button triggers scraping
3. ✅ Rate limiting prevents abuse (30s)
4. ✅ Global cache works (5 min)
5. ✅ See real EPL events with TAB + Betfair odds
6. ✅ Filters work (stake, bet type, search)
7. ✅ Calculator modal works with live calculations
8. ✅ Database stores historical odds
9. ✅ Error handling doesn't crash page
10. ✅ System scales to multiple users (global cache)

---

## 🐛 Troubleshooting

### "No opportunities found"
**Cause:** No matching odds in database
**Fix:** Run `docker exec mb_api python test_save_tab_odds.py`

### "Failed to refresh odds"
**Cause:** API not running or scraper error
**Fix:** Check `docker logs mb_api` for errors

### "Please wait 30 seconds"
**Cause:** Rate limit active
**Fix:** This is correct behavior! Wait 30 seconds

### Odds look wrong
**Cause:** Mock Betfair odds might be stale
**Fix:** Re-run `docker exec mb_api python seed_mock_betfair.py`

### Calculator doesn't update
**Cause:** JavaScript error in browser
**Fix:** Check browser console (F12)

---

## 📈 Performance Benchmarks

### Expected Response Times:
- **Page Load:** < 2 seconds
- **First Refresh (scraping):** 5-15 seconds
- **Cached Refresh:** < 1 second
- **Filter/Search:** < 100ms
- **Calculator Open:** < 50ms

### Expected Data Volumes:
- **Events:** 3-10 EPL matches
- **Odds per Event:** ~156 (21 markets × ~7 selections avg)
- **Total Opportunities:** Varies based on filters
- **Database Growth:** ~1000 odds per scrape session

---

## 🎉 You're Ready!

If all tests pass, you have a **working matched betting platform** with:
- ✅ Real TAB odds scraping
- ✅ Mock Betfair lay odds
- ✅ User-triggered refresh system
- ✅ Smart caching (5 min global)
- ✅ Rate limiting (30s per user)
- ✅ Interactive bet calculator
- ✅ Mobile-responsive UI
- ✅ Database persistence

Next steps:
1. Add Ladbrokes scraper
2. Implement real Betfair API
3. Deploy to production!
