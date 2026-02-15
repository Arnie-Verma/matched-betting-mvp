# Next Steps: Production-Ready Scraper Implementation

**Last Updated**: 2025-12-29
**Discovery Status**: Complete for 4 platforms
**Ready to Implement**: Punterstech (21 bookmakers)

---

## Punterstech Platform - All 21 Bookmakers

These are the bookmakers using the Punterstech platform. A **single scraper** will handle all of them.

### Complete Punterstech Bookmaker List (21 total)

| Bookmaker | Code | Website | Tier | Status |
|-----------|------|---------|------|--------|
| AlphaBet | alphabet | https://www.alphabetbetting.com | Diamond | ✅ Discovered |
| BetBlitz | betblitz | https://www.betblitz.com.au | Diamond | ✅ Discovered |
| BetChamps | betchamps | https://www.betchamps.com.au | Diamond | ✅ Discovered |
| BetFocus | betfocus | https://www.betfocus.com.au | Diamond | ✅ Discovered |
| BlondeBet | blondebet | https://www.blondebet.com.au | Diamond | ✅ Discovered |
| CashCage | cashcage | https://www.cashcage.com.au | Diamond | ✅ Discovered |
| HavaBet | havabet | https://www.havabet.com.au | Diamond | ✅ Discovered |
| LightningBet | lightningbet | https://www.lightningbet.com.au | Diamond | ✅ Discovered |
| MintBet | mintbet | https://www.mintbet.com.au | Diamond | ✅ Discovered |
| StarSports | starsports | https://www.starsports.com.au | Diamond | ✅ Discovered |
| TopBet | topbet | https://www.topbet.com.au | Diamond | ✅ Discovered |
| TradieBET | tradiebet | https://www.tradie.bet | Diamond | ✅ Discovered |
| TrueBet | truebet | https://www.truebet.com.au | Diamond | ✅ Discovered |
| VinBet | vinbet | https://www.vinbet.com.au | Diamond | ✅ Discovered |
| WizBet | wizbet | https://www.wizbet.com.au | Diamond | ✅ Discovered |

**Additional Punterstech bookmakers (6 more = 21 total)**:
- BetVista, TeamBet, XBet, MillennialBet, BetReal, RipperBet (mentioned in SCRAPER_STRATEGY.md)

---

## Recommended Implementation Roadmap

### Phase 1: Implement PunterstechScraper (21 bookmakers) - THIS WEEK
**Effort**: 2-3 days
**Value**: 20% of 102-bookmaker target
**Difficulty**: Easy

**Steps**:
1. Copy `ladbrokes_scraper.py` → `punterstech_scraper.py`
2. Update class name: `LadbrokesScraper` → `PunterstechScraper`
3. Change API base: `api.{domain}` → `api.public.{domain}`
4. Update endpoints:
   - `/api-events/public/next-to-go/batch` (primary endpoint)
   - `/api-events/public/open-event-types`
   - `/api-events/public/markets/{event-id}`
   - `/sportssilks/supportedsports`
5. Test with: TradieBET, MintBet, TopBet
6. Update `scrape_service.py` to register `PunterstechScraper`
7. Run seed script to mark bookmakers active

**Expected Output**:
- PunterstechScraper handles 21 bookmakers
- All 21 bookmakers return odds to odds_matcher
- Betfair + Ladbrokes + Punterstech = 37 bookmakers live

---

### Phase 2: Complete Generation Web + BetCloud Research (1-2 days)
**Effort**: Manual browser testing only
**Blocker**: Need to find sports betting APIs

**Generation Web (22 bookmakers)**:
- Manually browse EliteBet.com.au sports page
- Use Chrome DevTools Network tab
- Find full sports betting API endpoints
- Document response structure

**BetCloud (26 bookmakers)**:
- Manually browse WellBet.com.au sports page
- Use Chrome DevTools Network tab
- Find `/punter/sports/*` endpoint pattern
- Document response structure

**Once complete**: Can implement 48 more bookmakers (Gen Web + BetCloud)

---

### Phase 3: Implement BetMakersScraper (33 bookmakers) - PARALLEL
**Effort**: 3-5 days (after Phase 1 complete)
**Value**: 32% of target (33/102)
**Difficulty**: Medium (SSR approach)

**Sites to test**: RealBookie, CrossBet, TerryBet

**Approach**:
1. Create `betmakers_scraper.py` (use Playwright like Ladbrokes)
2. Load sports page with Playwright
3. Extract odds from DOM using:
   - Page selectors: `page.querySelectorAll('[data-odds]')`
   - HTML parsing: Regex for odds patterns
   - Window objects: `page.evaluate("window.__ODDS_DATA__")`
4. Test with 3 representative sites
5. Register in scrape_service.py

**Expected Output**:
- BetMakersScraper handles 33 bookmakers (largest platform)
- Combined total: 37 + 33 = 70 bookmakers (68% of target)

---

### Phase 4: Implement Generation Web + BetCloud Scrapers (3-10 days)
**Effort**: Once Phase 2 research complete
**Value**: 48 bookmakers (47% of target)
**Difficulty**: Medium

**Generation Web (22 sites)**:
- Implement `generation_web_scraper.py`
- Use discovered API pattern
- Test: EliteBet, WinnersBet, GoldBet

**BetCloud (26 sites)**:
- Implement `betcloud_scraper.py`
- Use discovered API pattern
- Test: WellBet, BetGalaxy, PuntCity

**Expected Output**:
- Combined total: 37 + 33 + 22 + 26 = 118 bookmakers
- **Exceeds 102-bookmaker target!**

---

## Current Status Summary

### What's Already Working
- ✅ **Ladbrokes** (Entain) - 1 bookmaker live
- ✅ **Betfair** - Exchange working
- ✅ **Database seeding** - 102 bookmakers in DB with platform tags
- ✅ **Tier enforcement** - Free/Premium/Diamond tiers configured
- ✅ **API discovery** - All 4 platforms researched
- ✅ **Bookmaker scraping_config** - Platform/scraper_class tags set

### What's Ready to Build
1. **PunterstechScraper** - 21 bookmakers (API fully documented)
2. **BetMakersScraper** - 33 bookmakers (approach clear, SSR)
3. **GenerationWebScraper** - 22 bookmakers (needs 1-2 day research first)
4. **BetCloudScraper** - 26 bookmakers (needs 1-2 day research first)

### Timeline to Full Coverage

| Phase | Action | Timeline | Cumulative |
|-------|--------|----------|-----------|
| Now | Working: Ladbrokes + Betfair | - | 2 bookmakers |
| Week 1 | Build PunterstechScraper | 2-3 days | 23 bookmakers |
| Week 1-2 | Research Gen Web + BetCloud | 1-2 days | 23 bookmakers |
| Week 2 | Build BetMakersScraper | 3-5 days | 56 bookmakers |
| Week 2-3 | Build Gen Web + BetCloud | 6-10 days | 102 bookmakers |

**Total Implementation**: 2-3 weeks for 102-bookmaker coverage

---

## Development Guidelines

### For Each Scraper Implementation

1. **Create new file**: `apps/worker/src/scrapers/{platform}_scraper.py`
2. **Inherit from BaseScraper**
3. **Implement required methods**:
   - `scrape_sport(sport, limit)` - Main entry
   - `parse_event(event_data)` - Event parsing
   - `parse_odds(odds_data, event)` - Odds extraction
4. **Configure in database**:
   - Add `scraper_class: "{platform_name}"`
   - Set `base_url` per bookmaker if configurable
5. **Test with 3 representative sites** before marking complete
6. **Register in scrape_service.py**:
   ```python
   SCRAPER_CLASSES = {
       "punterstech": PunterstechScraper,
       "betmakers": BetMakersScraper,
       "generation_web": GenerationWebScraper,
       "betcloud": BetCloudScraper,
   }
   ```

### Testing Checklist
- [ ] Scraper instantiates without errors
- [ ] Connects to API/site successfully
- [ ] Parses events correctly
- [ ] Extracts odds with correct format (decimal)
- [ ] Returns ScrapeResult with status=SUCCESS
- [ ] Tests on 3 representative bookmakers
- [ ] Logs output matches production format

---

## Key Technical References

### API Patterns Discovered
- **Punterstech**: `POST /api-events/public/next-to-go/batch` (116KB response)
- **BetMakers**: DOM-based (SSR), no JSON API
- **Generation Web**: `/sportutility/*` endpoints (partial)
- **BetCloud**: `/punter/races/*` working, `/punter/sports/*` missing

### Discovery Tool
```bash
# If needed, re-run discovery:
docker exec mb_api bash -c "cd /workspace && python discovery.py --platform punterstech"
```

### Seed Script (Already Run)
```bash
docker exec mb_api python -m api.scripts.seed_all_bookmakers
```

### Current Active Bookmakers
```sql
SELECT code, scraping_config->>'platform' as platform
FROM bookmakers
WHERE is_active = true;
-- Result: ladbrokes, betfair (both working)
```

---

## Success Criteria

- ✅ Phase 1 Complete: PunterstechScraper working for 21 bookmakers
- ✅ Phase 1 Complete: All 21 Punterstech bookmakers appearing in odds_matcher
- ✅ Phase 1 Complete: Tier 2 pricing offers 37 bookmakers (Ladbrokes + Neds + Betfair + 21 Punterstech)
- ✅ Phase Complete: All 102 bookmakers scraped with 4 platform scrapers

---

## Questions to Address Before Starting

1. **Priority**: Start PunterstechScraper immediately, or research Gen Web/BetCloud first?
   - **Recommendation**: Start Punterstech (highest ROI, no blockers)

2. **Testing approach**: Test each scraper with 3 sites, or fully test before moving to next?
   - **Recommendation**: Fully test 3 sites before marking complete

3. **Database updates**: Activate bookmakers as scrapers finish, or all at once?
   - **Recommendation**: Activate progressively (week by week)

4. **Monitoring**: Add Sentry error tracking, or wait until all scrapers done?
   - **Recommendation**: Add basic logging now, Sentry after Phase 2

---

**Ready to start PunterstechScraper implementation?**
