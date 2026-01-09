# Daily Progress Log

Track daily work. Compress old entries weekly to keep focused on current tasks.

---

## 2026-01-09 (Friday)

### Session 3: System Verification & Full Scrape Test

**Goal**: Verify all scrapers working after previous session's Entain fix, run full system test

**Verification Results** ✅:

1. **Ladbrokes (Entain) Scraper**: Soccer: 97 events, 342 odds; Basketball: 13 events, 30 odds
2. **Betfair Scraper**: Soccer: 111 events, 329 odds (~33s)
3. **Neds (Entain) Scraper**: Soccer: 97 events, 342 odds (~49s)
4. **Parallel Scrape Test**: Betfair + Ladbrokes: 108s total
5. **Full Manual Scrape**: 18/21 bookmakers, 1,857 events, 4,999 odds saved, 24,806 total current odds

**Competition Coverage**: Champions League (864), NHL (682), EPL (522), Bundesliga (453), Serie A (366), NBA (360), La Liga (336), A-League (246)

**Fix Applied**: Increased all-sports scrape timeout from 120s → 180s in [scrape_service.py:489](apps/worker/src/jobs/scrape_service.py#L489)

### Status: System Working ✅

---

### Session 2: Multi-Sport Odds Matcher Investigation

**Completed**:
- Fixed Entain scraper with `COMPETITION_URLS` dict for competition-specific URLs
- Scraper now iterates through EPL, NBA, etc. to capture legacy API data
- Wait time increased to 8s for legacy API
- Verified 29 soccer opportunities found

**Key Changes**: [entain_scraper.py](apps/worker/src/scrapers/entain_scraper.py) - Lines 70-97, 194-450

---

### Session 1 (Earlier)

- Web app build issues: ChunkLoadError, API proxy routes need force-dynamic

---

## 2026-01-07 (Wednesday)

### Session 4: Market Filter Fix

- **Fixed**: Market filter pattern `'%moneyline%'` → `'%money%line%'` for Basketball/Hockey
- **Commit**: aba9dda

### Session 3: Production Scale Assessment

**Current State**: 21 active bookmakers, 79s parallel scraping, queue-based refresh working

**Gaps for 100+ bookmakers**:
- Proxy infrastructure needed for TAB/Entain at scale
- BetMakers (33), Generation Web (22), BetCloud (26) not implemented
- Connection pool needs increase from 5 → 20+

### Sessions 1-2: Odds Matcher Filters

- Fixed competition code normalization between frontend/backend
- 973 opportunities working with filters

---

## 2026-01-04 (Sunday)

- BetCloud sports endpoints confirmed + required headers found
- Generation Web betapi payloads captured (odds endpoint still hidden)
- Updated SCRAPER_STRATEGY.md and DISCOVERY_SUMMARY.md

---

## 2026-01-03 (Friday)

- Fixed Docker memory issue (removed uvicorn --reload)
- Enabled 18 Punterstech bookmakers total
- chasebet & betalpha: DNS failures (offline)

---

## 2026-01-02 (Friday)

- Fixed 7 Punterstech URLs, enabled 10 bookmakers
- Full scrape: 1,423 odds (452 events, 5 bookmakers)
- Cross-bookmaker matching validated

---

## 2026-01-01 (Thursday)

- Created apps/marketing Next.js app with unified brand system
- Restyled apps/web pages to match brand

---

## Historical Summary (Dec 2025)

### Week of Dec 30

- **EntainScraper created** - Config-driven platform scraper for Ladbrokes/Neds/Unibet
- **Dynamic Scraper Registry** - SCRAPER_CLASSES maps config to implementation
- **Sentry integration** + health check endpoints
- **Platform discovery** - Punterstech (21), BetMakers (33), Generation Web (22), BetCloud (26)

### Week of Dec 27-28

- **Phase 0-4 COMPLETE**:
  - Phase 0: Queue/cache/circuit breaker
  - Phase 1: Parallel scraping (131s → 91s)
  - Phase 2: Dynamic waits (91s → 79s)
  - Phase 3: DB optimization (cleanup service + indexes)
  - Phase 4: NormalizationService (-580 lines duplication)
- **5 Calculators implemented** (Back/Lay, Dutching, True Odds, Multi, EV)
- **Production scaling strategy** - 4 platforms = 102 bookmakers

### Week of Dec 19-21

- **Ladbrokes scraper complete** - All 6 sports, Playwright-based
- **Event name matching fixed** - Alphabetical team sorting
- **Odds grouping fixed** - Query across all selection IDs
- **Team normalizations** - 200+ mappings for EPL, NBA, NHL, Serie A, Bundesliga

### Earlier (Dec 2-8)

- TAB EPL-only works, Akamai blocks multi-sport
- Betfair timing fix (5s wait + 1s async)
- Free tier strategy: Ladbrokes + Neds + Betfair
- Outmatched.com owner confirmed rotating proxy approach

---

## Current Blockers

1. **NRL/AFL off-season** - No matching until season starts
2. **Generation Web odds endpoint** - Still hidden, needs manual discovery

---

## Guidelines

**Daily format**:
```markdown
## YYYY-MM-DD (Day)
### Completed
- Bullet points
### Blockers
### Next Steps
```

**Weekly compression** (Sunday): Move week's details to compressed section.
