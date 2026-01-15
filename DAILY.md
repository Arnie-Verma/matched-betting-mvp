# Daily Progress Log

Track daily work. Compress old entries weekly to keep focused on current tasks.

---

## 2026-01-15 (Wednesday)

### Session 3: Validation Framework Implementation

**Goal**: Implement the 4-phase validation pipeline designed in Session 2

**Completed**:
1. Created validation module structure:
   - [config.py](apps/worker/src/validation/config.py) - Thresholds, expected counts, golden fixtures
   - [structural_validator.py](apps/worker/src/validation/structural_validator.py) - Phase 1
   - [probability_validator.py](apps/worker/src/validation/probability_validator.py) - Phase 2
   - [golden_fixtures.py](apps/worker/src/validation/golden_fixtures.py) - Phase 3
   - [score_calculator.py](apps/worker/src/validation/score_calculator.py) - Phase 4
   - [report_generator.py](apps/worker/src/validation/report_generator.py) - Terminal + JSON output
   - [pipeline.py](apps/worker/src/validation/pipeline.py) - Orchestrates all phases

2. Created CLI entry point:
   - [validate_scrapers.py](apps/worker/src/scripts/validate_scrapers.py)
   - Usage: `python -m scripts.validate_scrapers --competition laliga`

3. Integrated with scrape service (non-blocking):
   - Added `VALIDATION_ENABLED` env var
   - Validation runs after successful scrape
   - Alerts on failures via Sentry

4. Comprehensive test suite:
   - [test_validation.py](apps/worker/tests/test_validation.py) - 30 tests, all passing

**Key Features**:
- Implied probability comparison (mathematically correct)
- Market-type aware thresholds (favorites vs longshots)
- Exchange structure-only validation (Betfair)
- Golden fixtures for regression safety
- Non-blocking (never blocks user requests)

**Commands**:
```bash
# Validate from database
docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition laliga

# Enable during scraping
VALIDATION_ENABLED=true docker exec mb_api python ../worker/src/manual_scrape.py
```

---

### Session 2: Scraper Validation Framework Design

**Goal**: Design automated QA layer to validate 100+ bookmakers × 14 leagues without manual checking

**Problem**: Manual comparison with Outmatched doesn't scale. Need systematic, fool-proof validation.

**Solution Designed**: 4-Phase Validation Pipeline

1. **Phase 1 - Structural Validation** (catches 70-80% of issues)
   - Event count sanity (vs expected per league)
   - Event matching rate (normalized teams + start time)
   - Market presence (moneyline has 2-3 outcomes)
   - Odds bounds (1.01 ≤ odds ≤ 1001)
   - Timestamp freshness

2. **Phase 2 - Odds Sanity via Implied Probability**
   - Convert odds → implied probability: `p = 1/odds`
   - Compare to Ladbrokes (bootstrap reference)
   - Compare to consensus median (long-term)
   - Market-type aware thresholds (3-6pp moneyline, 5-10pp longshots)
   - Betfair = structure only (exchange odds ≠ bookmaker odds)

3. **Phase 3 - Golden Fixtures**
   - 5-10 curated fixtures per league
   - Always scrape, always validate
   - Fast regression detection

4. **Phase 4 - Scoring & Anomaly Output**
   - Per bookmaker × league: PASS / WARN / FAIL
   - Coverage %, anomaly count, top N outliers
   - Human review = "check top anomalies" only

**Key Design Decisions**:
- Non-blocking: Never block user requests on validation
- Implied probability: More meaningful than raw odds %
- Ladbrokes as bootstrap reference, consensus as long-term truth
- Quarantine feed (not crash) on failures

**Output**: Created [VALIDATION_FRAMEWORK.md](VALIDATION_FRAMEWORK.md) with full design

---

### Session 1: Outmatched Parity Verification

**Goal**: Verify we have parity with Outmatched for MintBet La Liga opportunities

**Analysis**:
- Outmatched shows 48 rows, we show 30 rows
- Root cause: Outmatched displays duplicate price points for same selection (e.g., Real Madrid 1.12 AND 1.03)
- Their duplicates are historical prices, not unique opportunities

**Verification**:
- Unique matches covered: 10 (both systems identical)
- Unique opportunities: 30 (home/draw/away for each match)
- Real Madrid v Levante ✓
- Atletico Madrid v Alaves ✓
- Real Sociedad v Barcelona ✓
- Espanyol v Girona ✓
- Osasuna v Oviedo ✓
- Mallorca v Athletic Bilbao ✓
- Getafe v Valencia ✓
- Celta Vigo v Rayo Vallecano ✓
- Betis v Villarreal ✓
- Elche v Sevilla ✓

**Conclusion**: Full parity achieved. Our approach (current best odds only) is superior to Outmatched (showing duplicate historical prices)

---

## 2026-01-14 (Tuesday)

### Session 3: Team Normalization Fix for Atletico Madrid

**Issue**: Atletico Madrid v Alaves not matching across bookmakers

**Root Cause**: Accented character "Atlético de Madrid" wasn't matching "Atletico Madrid"
- Betfair: `alavesvatletico`
- MintBet: `alavesvatléticodemadrid` (with accent + "de madrid")

**Fix Applied**:
- **[normalization_service.py:169-170](apps/api/src/api/services/normalization_service.py#L169-L170)**: Added accented variants `atlético de madrid` → `atletico`
- **[normalization_service.py:192](apps/api/src/api/services/normalization_service.py#L192)**: Added `elche cf` → `elche`
- Updated 1,966 event normalized_names in database

**Result**: All La Liga matches now match across Betfair + MintBet + 15 Punterstech bookmakers

### Session 2: Punterstech API Endpoint Fix

**Goal**: Fix MintBet La Liga missing odds for matches 3+ days in future

**Root Cause**: Punterstech `/quick-markets/{EventKey}` only returns odds for events close to start time (~1-2 days). Discovered `/markets/{EventKey}` endpoint returns full odds for ALL scheduled events.

**Fix Applied**:
- **[punterstech_scraper.py:281-292](apps/worker/src/scrapers/punterstech_scraper.py#L281-L292)**: Changed from `/quick-markets` → `/markets` endpoint
- **[punterstech_scraper.py:647-698](apps/worker/src/scrapers/punterstech_scraper.py#L647-L698)**: Updated parsing to handle both response formats
- **[punterstech_scraper.py:870](apps/worker/src/scrapers/punterstech_scraper.py#L870)**: Fixed selection key parsing for "Real Madrid Win" → "home"

**Verification**:
- MintBet now captures 10 La Liga events with full odds:
  - Espanyol v Girona (Jan 16)
  - Real Madrid v Levante (Jan 17): 1.13 / 12.00 / 6.25
  - Atletico Madrid v Alaves (Jan 18)
  - Real Sociedad v Barcelona (Jan 19)
  - And 6 more...
- Full scrape: 19,914 odds saved across 14 bookmakers
- Cross-bookmaker matching confirmed: Real Madrid v Levante has odds from MintBet, Betfair, Ladbrokes, and 15+ Punterstech bookmakers

### Session 1: Punterstech La Liga Matching Investigation

**Goal**: Fix MintBet La Liga not showing opportunities in frontend

**Investigation Results**:

1. **Root Cause Identified**: Punterstech scraper's `result_limit` was 200, but La Liga events start at index 203 in MintBet's `next-to-go` API response
2. **Secondary Issue**: MintBet only publishes odds for imminent events (1-2 days out). Matches on Jan 17-19 have no odds yet in API

**Fix Applied**:
- **[punterstech_scraper.py:349](apps/worker/src/scrapers/punterstech_scraper.py#L349)**: Increased `result_limit` from 200 → 500

**Verification**:
- Espanyol v Girona (Jan 16) now shows 3 matching opportunities:
  - Espanyol: Back 1.80 (MintBet) vs Lay 2.02 (Betfair)
  - Draw: Back 3.10 vs Lay 3.70
  - Girona: Back 3.80 vs Lay 4.60
- Cross-bookmaker event grouping confirmed working (`espanyolvgirona_laliga` matches events from "Spanish La Liga" and "2025/2026 Spain La Liga - Round 20")

**Architecture Notes**:
- Punterstech's `next-to-go` API returns events sorted by proximity, with popular leagues appearing later (index 200+)
- `/quick-markets/{EventKey}` returns empty for events >2 days in future → use `/markets/{EventKey}` instead
- Event matching logic correctly groups by `{normalized_event_name}_{normalized_competition}` across different competition naming schemes

---

## 2026-01-13 (Monday)

### Session: Scraper Validation & Data Quality Fixes

**Goal**: Systematic validation framework + fix La Liga matching issues

**Issues Discovered**:
1. **Betfair scraper bug**: A-League events mislabeled as "Spanish La Liga", La Liga events as "German Bundesliga"
2. **Team name normalization gaps**: Missing Spanish La Liga team mappings
3. **Stale corrupted data**: 23 mislabeled events in database

**Root Causes**:
- Betfair scraper overwrote competition name on duplicate events (kept LAST page instead of FIRST)
- Missing team mappings: "Real Mallorca" → "mallorca", "Real Betis" → "betis", etc.

**Fixes Applied**:
1. **[betfair_scraper.py](apps/worker/src/scrapers/betfair_scraper.py:517-528, 580-592)**: Preserve original competition assignment
2. **[normalization_service.py](apps/api/src/api/services/normalization_service.py:166-189)**: Added 8 La Liga team mappings
3. **Database cleanup**: Deleted 23 corrupted events (17 A-League as La Liga, 6 La Liga as Bundesliga)

**Verification**:
- Team normalization now matches: "Rayo Vallecano v Real Mallorca" ↔ "Rayo Vallecano v Mallorca" ✅
- Re-scrape completed: 1944 events, 5590 odds
- No more mislabeled events in DB

**Next Steps**: Verify La Liga matching produces expected ~40-50 opportunities

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
