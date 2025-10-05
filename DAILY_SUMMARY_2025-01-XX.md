# Daily Summary - Matched Betting MVP

## Date: January 2025

---

## 🎯 Main Achievements

### 1. ✅ Database Seeding - Bookmakers & Plans

**Bookmakers Seeded (103 total):**
- Created comprehensive seed script for all Australian bookmakers
- Implemented **cumulative tier structure**:
  - **FREE (2 active):** TAB, Ladbrokes
  - **PREMIUM (14 inactive):** Sportsbet, Neds, Betfair, Pointsbet, UniBet, Betr, BetDeluxe, BetRight, CrossBet, Dabble, EliteBet, TABTouch, Realbookie, Picklebet
  - **PLATINUM (87 inactive):** All remaining bookmakers
  - Total: **16 for Premium users**, **103 for Platinum users**

**Pricing Plans Seeded (3 plans):**
- **Free ($0/mo):**
  - 2 bookmakers (TAB, Ladbrokes)
  - "Make over $70"
  - "Learn the basics"

- **Premium ($25/mo):**
  - 16 bookmakers (includes all free + 14 premium)
  - Advanced matched betting calculators
  - Premium academy courses

- **Diamond ($35/mo):**
  - 100+ bookmakers (includes all premium + platinum)
  - "$1000s of dollars in sign up bonuses"
  - Everything in premium

---

### 2. ✅ Fixed Billing Page UI

**Problem:** Billing page showed raw JSON dump of features

**Solution:**
- Updated `PricingPlans.tsx` component to show clean feature lists
- Matched Outmatched.com.au's simple, professional style
- Updated button text: "Try for free", "Select this plan"
- Removed all technical field names from display

**Before:**
```
bookmakers: 16
bookmaker_list: TAB,Ladbrokes,Sportsbet...
academy_access: true
✓ Email notifications
✗ API access
```

**After:**
```
Premium includes:
Realtime odds comparison from 16 bookmakers
Advanced matched betting calculators
Premium academy courses
```

---

### 3. ✅ Subscription Service - Cumulative Tier Access

**Updated `subscription_service.py`:**
- Modified `get_allowed_bookmakers()` to return cumulative bookmaker lists
- **Free tier:** Returns `["tab", "ladbrokes"]` (2)
- **Premium tier:** Returns free + 14 premium bookmakers (16 total)
- **Platinum tier:** Returns ALL bookmakers from database (103 total)

**Key Logic:**
```python
if plan == "free":
    return ["tab", "ladbrokes"]
elif plan == "premium":
    return ["tab", "ladbrokes", "sportsbet", "neds", "betfair", ...]  # 16 total
elif plan == "platinum":
    return [all bookmakers from database]  # 103 total
```

---

### 4. ✅ Database Migrations Completed

**Ran migrations:**
- `alembic upgrade head` - Created all tables
- Seeded 103 bookmakers into `bookmakers` table
- Seeded 3 pricing plans into `plans` table

**Database Verification:**
```sql
-- Bookmakers by tier
FREE: 2 (active)
PREMIUM: 14 (inactive, to be built)
PLATINUM: 87 (inactive, future)

-- Plans verification
Free: $0, 2 bookmakers
Premium: $25, 16 bookmakers
Platinum: $35, 103 bookmakers
```

---

## 📁 Files Created

### Backend Scripts
1. **`apps/api/src/api/scripts/seed_all_bookmakers.py`**
   - Seeds all 103 Australian bookmakers
   - Stores tier info in `scraping_config` JSON field
   - Only TAB and Ladbrokes set to `is_active=True`

2. **`apps/api/src/api/scripts/seed_plans.py`**
   - Seeds Free, Premium, Diamond pricing plans
   - Includes clean `feature_list` for UI display
   - Matches Outmatched.com.au pricing/features

### Backend Services (Modified)
3. **`apps/api/src/api/services/subscription_service.py`**
   - Added `Bookmaker` import
   - Updated `get_allowed_bookmakers()` with cumulative logic
   - Free tier excludes Betfair (only TAB/Ladbrokes)

### Frontend Components (Modified)
4. **`apps/web/src/components/billing/PricingPlans.tsx`**
   - Added `getFeatureList()` helper
   - Removed `formatFeature()` function (was showing raw JSON)
   - Clean feature list display matching Outmatched style
   - Updated button text to "Try for free" / "Select this plan"

---

## 🗄️ Database Schema Updates

### Bookmakers Table
```
Total: 103 bookmakers
Active: 2 (TAB, Ladbrokes)
Inactive: 101 (to be activated as scrapers are built)

Fields used:
- code, name, display_name, website_url
- is_active (only TAB/Ladbrokes true)
- base_url, api_endpoint
- scraping_config (JSON with tier, platform, difficulty)
```

### Plans Table
```
Total: 3 plans
All active (is_active=true)

Free: $0/mo, 2 bookmakers
Premium: $25/mo, 16 bookmakers
Diamond: $35/mo, 103 bookmakers

features JSON includes:
- bookmakers (count)
- feature_list (array of display strings)
```

---

## 🔧 Technical Decisions

### 1. Cumulative Tier Access
**Decision:** Premium includes Free, Platinum includes Premium
**Rationale:** Matches Outmatched.com.au model - users get everything from lower tiers

### 2. Tier Metadata Storage
**Decision:** Store tier info in `scraping_config` JSON field
**Rationale:** Existing `Bookmaker` model doesn't have `tier` column, JSON flexible for future metadata

### 3. Inactive Bookmakers in Database
**Decision:** Seed all 103 now, mark 101 as inactive
**Rationale:** Database ready for scale, easy to activate as scrapers are built

### 4. Betfair in Premium Tier
**Decision:** Moved Betfair from Free to Premium tier
**Rationale:** Free users use TAB/Ladbrokes only, Premium+ gets exchange access

### 5. Display Name: Platinum → Diamond
**Decision:** Use "Diamond" as display name, keep "platinum" as internal code
**Rationale:** Matches Outmatched branding, maintains code consistency

---

## ✅ Testing Completed

### Database Verification
```bash
# Verified tier distribution
FREE: 2 active bookmakers
PREMIUM: 14 inactive bookmakers
PLATINUM: 87 inactive bookmakers

# Verified plans API
GET /billing/plans returns 3 clean plans with feature_list
```

### API Endpoints Tested
- ✅ `GET /billing/plans` - Returns 3 plans with clean features
- ✅ `GET /billing/subscription` - Returns user subscription status
- ✅ Database queries working correctly

### UI Verification
- ✅ Billing page displays 3 clean pricing cards
- ✅ No raw JSON shown (bookmakers, academy_access, etc.)
- ✅ Feature bullets match Outmatched style
- ✅ "Most Popular" badge on Premium tier
- ✅ Button text: "Try for free" / "Select this plan"

---

## 📊 Current State

### Active Systems
- ✅ Database with 103 bookmakers (2 active)
- ✅ 3 pricing plans (Free, Premium, Diamond)
- ✅ Subscription service with cumulative tier logic
- ✅ Clean billing page UI matching Outmatched

### Ready for Next Phase
- 🔄 API endpoint discovery (TAB, Ladbrokes for EPL/Soccer)
- 🔄 Real scraper implementation
- 🔄 Switch from mock data to real odds
- 🔄 Activate additional bookmakers for Premium/Platinum tiers

### Mock Data Still Active
- ⚠️ Odds Matcher using mock endpoint (`/api/proxy/odds/matcher-mock`)
- ⚠️ No real scrapers running yet
- ⚠️ Need to discover TAB/Ladbrokes API endpoints

---

## 🚀 Next Steps (Tomorrow)

### Priority 1: API Endpoint Discovery
1. Open TAB soccer page: https://www.tab.com.au/sports/soccer
2. Use browser DevTools (F12 → Network → Fetch/XHR)
3. Find API endpoint for EPL/Soccer odds
4. Repeat for Ladbrokes

### Priority 2: Update Scrapers with Real Endpoints
1. Update `apps/worker/src/scrapers/tab_scraper.py`
2. Update `apps/worker/src/scrapers/ladbrokes_scraper.py`
3. Test scraping real EPL matches

### Priority 3: Database Integration
1. Create `save_odds.py` function
2. Test saving scraped odds to database
3. Create scraping job scheduler

### Priority 4: Switch to Real Data
1. Change `OddsMatcherClient.tsx` from `/matcher-mock` to `/matcher`
2. Delete mock files
3. Test end-to-end with real odds

### Priority 5: Betfair API Setup (Optional)
1. Register for Betfair API key
2. Configure SSL certificate auth
3. Test Betfair lay odds scraping

---

## 📝 Notes & Decisions

### Why EPL/Soccer Now?
- AFL is out of season (October)
- EPL is active with matches every weekend
- High Betfair liquidity
- All Australian bookmakers cover EPL heavily

### Why Only 2 Active Bookmakers?
- Focus on quality over quantity
- TAB and Ladbrokes are largest/easiest to scrape
- Get MVP working with 2, then scale to 103
- Premium/Platinum users can still sign up (activation coming soon)

### Why Store Tier in JSON?
- `Bookmaker` model doesn't have `tier` column
- Avoid migration for single field
- Flexible for future metadata (platform, difficulty, etc.)
- Easy to query: `scraping_config->>'tier'`

---

## 🐛 Issues Resolved

### Issue 1: Plans API Returning Empty
**Problem:** Billing page blank, no plans shown
**Root Cause:** No plans in database
**Solution:** Created `seed_plans.py` and seeded 3 plans

### Issue 2: Raw JSON Displayed on Billing Page
**Problem:** UI showing `bookmakers: 16`, `academy_access: true`, etc.
**Root Cause:** `formatFeature()` displaying all feature keys
**Solution:** Created `getFeatureList()` to show only `feature_list` array

### Issue 3: Wrong Tier Field Names
**Problem:** `'tier' is an invalid keyword argument for Bookmaker`
**Root Cause:** Model doesn't have `tier` column
**Solution:** Store tier metadata in `scraping_config` JSON field

### Issue 4: Database Name Mismatch
**Problem:** `psql: database "matched_betting" does not exist`
**Root Cause:** Database actually named `mb_dev`
**Solution:** Updated commands to use correct database name

---

## 💻 Git Commit Summary

**Files to Commit:**
1. `apps/api/src/api/scripts/seed_all_bookmakers.py` (new)
2. `apps/api/src/api/scripts/seed_plans.py` (new)
3. `apps/api/src/api/services/subscription_service.py` (modified)
4. `apps/web/src/components/billing/PricingPlans.tsx` (modified)
5. `DAILY_SUMMARY_2025-01-XX.md` (new)

**Commit Message:**
```
feat: Complete bookmaker & pricing plan seeding with Outmatched-style UI

- Seed 103 Australian bookmakers with cumulative tier structure
  - Free: 2 bookmakers (TAB, Ladbrokes)
  - Premium: 16 bookmakers (Free + 14 more)
  - Platinum: 103 bookmakers (Premium + 87 more)

- Seed 3 pricing plans matching Outmatched.com.au
  - Free: $0/mo, 2 bookmakers, "Make over $70"
  - Premium: $25/mo, 16 bookmakers, "Advanced calculators"
  - Diamond: $35/mo, 100+ bookmakers, "$1000s in bonuses"

- Update subscription service with cumulative tier logic
  - get_allowed_bookmakers() returns correct bookmaker lists

- Fix billing page UI to show clean feature lists
  - Remove raw JSON dumps
  - Match Outmatched's professional style
  - Update button text: "Try for free", "Select this plan"

🚀 Database ready for scale: 103 bookmakers, 3 plans
⏭️  Next: Discover real API endpoints for TAB/Ladbrokes EPL scraping
```

---

## 📈 Progress Tracker

### Phase 0: Foundation ✅ COMPLETE
- Monorepo setup
- Docker infrastructure
- Database schema
- Auth (Clerk)

### Phase 1: Billing ✅ COMPLETE
- Stripe integration
- Subscription management
- **Pricing plans seeded** ✅
- **Billing UI cleaned up** ✅

### Phase 2: Bookmaker Setup ✅ COMPLETE
- **103 bookmakers seeded** ✅
- **Tier structure implemented** ✅
- **Subscription service updated** ✅

### Phase 3: Odds Matcher Core 🔄 IN PROGRESS
- UI components built ✅
- Mock data working ✅
- Real API endpoints needed ⏳
- Scrapers need real endpoints ⏳
- Database integration pending ⏳

### Phase 4: Real Data Scraping ⏳ NEXT
- Discover TAB API endpoint
- Discover Ladbrokes API endpoint
- Update scrapers with real endpoints
- Test scraping EPL matches
- Save to database
- Switch UI to real data

---

## 🎯 Tomorrow's Goals

1. ✅ Commit today's work to git
2. 🔍 Discover TAB EPL API endpoint (browser DevTools)
3. 🔍 Discover Ladbrokes EPL API endpoint
4. 🔧 Update scrapers with real endpoints
5. 🧪 Test scraping real EPL matches
6. 💾 Create save-to-database function
7. 🔄 Switch UI from mock to real data

**Success Criteria for Tomorrow:**
- TAB scraper fetching real EPL odds
- Ladbrokes scraper fetching real EPL odds
- Real odds saved to database
- UI displaying real matched betting opportunities

---

## 📚 Documentation Updated

- Created this comprehensive daily summary
- Updated inline code comments
- Documented tier structure in seed scripts
- Added feature list documentation in plans seed

---

**End of Day Summary**

✅ Major milestone achieved: Database fully seeded and ready for scale
✅ Billing page professional and clean
✅ Subscription service handles cumulative tier access correctly
⏭️ Ready to discover real API endpoints tomorrow and connect real data

**Total Lines of Code Today:** ~800+ (2 new scripts, 2 modified services/components)
**Database Records Created:** 106 (103 bookmakers + 3 plans)
**Time Invested:** Full development day
**Status:** On track for MVP launch 🚀
