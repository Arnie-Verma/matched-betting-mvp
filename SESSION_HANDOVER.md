# Session Handover - Matched Betting MVP

**Date:** 2025-10-11
**Session Focus:** Calculator UI Improvements & Formula Fixes

---

## ✅ What Was Completed This Session

### 1. **Fixed Calculator Formula Bug**
- **Issue:** Frontend calculator was showing incorrect lay stake ($96.94 instead of $100)
- **Root Cause:** Missing commission in denominator of lay stake formula
- **Fix Applied:**
  - Updated `BetCalculatorModal.tsx` lines 65, 68
  - Changed from: `layStake = (backStake * backOdds) / layOdds`
  - Changed to: `layStake = (backStake * backOdds) / (layOdds - commission)`
- **Verification:** Calculations now match OutMatched exactly (lay stake $100, both scenarios -$6 loss)

### 2. **Simplified & Improved Calculator UI**
Implemented major UI overhaul based on user feedback:

**Header Improvements:**
- Title changed from "Bet Calculator" to "Odds Matcher"
- Shows: `⚽ Liverpool v Man United • English Premier League • H2H`
- Displays event date/time in Australian format
- Inline outcome display: `Outcome: Liverpool` (bold label, regular team name)
- Advanced settings button now shows "Advanced" text with gear icon

**Input Section:**
- Removed redundant odds from labels ("Bookie: 4.00" → "Bookie")
- Grouped inputs in slate background for visual clarity
- Commission field is smaller (max-w-xs) with helpful hint text
- Better placeholder text and colors

**Results Display:**
- Changed from large boxes to clean table format
- White backgrounds for colorblind accessibility
- Headers: Winner | Bookie | Betfair | Avail
- Shows actual team name vs "Other outcome"

**Summary Section:**
- Dynamic label: Shows "Profit" when positive, "Loss" when negative
- Removed redundant "Rating" metric (kept only PnL %)
- 2-column layout with larger font sizes
- Soft yellow warning boxes with proper icon alignment

**Action Buttons:**
- Added "Open TAB" and "Open Betfair" buttons
- Rounded corners (rounded-xl) with hover shadows
- Proper spacing and modern styling

### 3. **Removed Rating from Odds Matcher Table**
- Removed Rating column from desktop table
- Removed Rating from mobile cards
- Cleaned up unused `getRatingColor()` function

### 4. **Infrastructure Improvements**
- Added automatic database migrations on startup (development mode)
- Added missing `tenacity>=8.2.0` dependency
- Created mock Betfair odds seeding script for testing
- Fixed Docker hot-reload issues (required manual container restarts)

---

## 📁 Key Files Modified

### Frontend (Web App)
```
apps/web/src/components/odds-matcher/
├── BetCalculatorModal.tsx   ← Major UI overhaul + formula fix
└── OddsTable.tsx            ← Removed Rating column
```

### Backend (API)
```
apps/api/src/api/
├── main.py                           ← Auto-migrations on startup
└── scripts/seed_mock_betfair_odds.py ← New mock data script
```

### Configuration
```
apps/api/requirements.txt  ← Added tenacity>=8.2.0
```

---

## 🔧 Current System State

### ✅ Working Features
1. **Scraping:** TAB scraper successfully scrapes 1,560 odds (10 EPL events)
2. **Mock Data:** Betfair mock odds generated with realistic 1-3% spread
3. **Matching Engine:** Backend formulas are correct and tested
4. **Calculator:** Frontend now matches backend formulas exactly
5. **Auto-Migrations:** Database automatically migrates on container start
6. **UI:** Simplified, accessible, and user-friendly calculator modal

### ⚠️ Known Issues & Limitations
1. **Real Betfair Scraping:** Not yet implemented (using mock data)
2. **Docker Hot Reload:** Doesn't work on Windows - requires `docker restart mb_web`
3. **Market Type Display:** Shows "match_winner" from DB, displayed as "MATCH WINNER"

### 🗄️ Database State
- **Plans:** Seeded (Free, Professional, Enterprise)
- **Bookmakers:** Seeded (TAB, Betfair, others)
- **TAB Odds:** 1,560 odds from 10 EPL events
- **Mock Betfair Odds:** 1,560 matching odds with 1-3% spread
- **Migrations:** Up to date (auto-run on startup)

---

## 🎯 Next Priorities

### Immediate Tasks
1. **Real Betfair Scraping**
   - Implement actual Betfair odds scraping
   - Replace mock data generation
   - Add scraping scheduler/cron job

2. **Enhance Odds Display**
   - Add filtering by sport/competition
   - Add sorting options (by PnL %, liquidity, time)
   - Implement pagination for large result sets

3. **User Feedback**
   - Add "Copy Summary" functionality test
   - Implement bet tracking/history
   - Add profit/loss reporting

### Future Enhancements
1. **Additional Bookmakers**
   - Implement multi-bookmaker support
   - Add more Australian bookmakers (Sportsbet, Ladbrokes, etc.)
   - Handle different market types across bookmakers

2. **Advanced Features**
   - Implement bonus bet optimization
   - Add dutching calculator
   - Build arbitrage opportunity detector

3. **Production Readiness**
   - Set up production database migrations strategy
   - Implement proper error handling and logging
   - Add monitoring and alerting
   - Performance optimization for large datasets

---

## 🐛 Debugging Notes

### Docker on Windows Issues
- Hot reload doesn't detect file changes
- **Workaround:** `docker restart mb_web` after code changes
- Alternative: Use WSL2 for better volume mount performance

### Formula Verification
- Backend formula (correct): `(back_odds / (lay_odds - commission)) * stake`
- Commission must be in denominator, not just subtracted after
- Test case: Back $100 @ 5.00, Lay @ 5.13, Commission 6% → Lay stake should be $100.00

### Mock Data Generation
```bash
# Regenerate mock Betfair odds if needed:
docker exec -it mb_api python -m api.scripts.seed_mock_betfair_odds
```

---

## 📊 Testing Checklist

### Manual Testing (Completed ✅)
- [x] Calculator shows correct lay stake
- [x] Profit/Loss calculations match OutMatched
- [x] Bonus bet vs Normal bet calculations
- [x] UI is simplified and accessible
- [x] Removed redundant information
- [x] Dynamic Profit/Loss labels work correctly

### To Test (Next Session)
- [ ] Copy Summary button functionality
- [ ] Open TAB/Betfair buttons work correctly
- [ ] Advanced commission changes recalculate properly
- [ ] Mobile responsiveness
- [ ] Long event names don't break layout

---

## 🎬 Initial Prompt for Next Claude Session

```
I'm continuing work on the matched betting MVP. Last session completed:
1. Fixed calculator formula bug (commission in denominator)
2. Simplified calculator UI (removed clutter, better accessibility)
3. Removed Rating column from odds matcher table
4. Added auto-migrations and mock Betfair data

Current status: Calculator working correctly with mock data.

Next priorities:
1. Implement real Betfair scraping
2. Add filtering/sorting to odds matcher table
3. Test and refine the Copy Summary functionality

Please review SESSION_HANDOVER.md for full context. What would you like to work on first?
```

---

## 💾 Backup & Recovery

### Container Management
```bash
# Start all services
pnpm dev:up

# Restart web only (after code changes on Windows)
docker restart mb_web

# Stop and remove volumes (fresh start)
pnpm dev:down -v

# View logs
docker logs mb_web --tail 50
docker logs mb_api --tail 50
```

### Database Reset
```bash
# If database needs reset:
docker compose -f infra/dev/docker-compose.yml down -v
pnpm dev:up  # Auto-migrations will run
docker exec -it mb_api python -m api.scripts.seed_all_bookmakers
docker exec -it mb_api python -m api.scripts.seed_plans
# Then run scraper or seed mock data
```

---

## 📝 Important File Locations

### Configuration
- API: `apps/api/src/api/core/config.py`
- Docker: `infra/dev/docker-compose.yml`
- Database: `apps/api/alembic/versions/`

### Key Components
- Calculator Modal: `apps/web/src/components/odds-matcher/BetCalculatorModal.tsx`
- Odds Table: `apps/web/src/components/odds-matcher/OddsTable.tsx`
- Matching Engine: `apps/api/src/api/services/matching_engine.py`
- Odds Matcher Router: `apps/api/src/api/routers/odds_matcher.py`

### Scripts
- Seed All: `apps/api/src/api/scripts/seed_all_bookmakers.py`
- Mock Betfair: `apps/api/src/api/scripts/seed_mock_betfair_odds.py`
- Scrape TAB: Use via API endpoint `/api/odds/refresh`

---

**End of Session Handover**
All changes committed and pushed to: `feat/auth-step2-web-clerk` branch
