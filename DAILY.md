# Daily Progress Log

Track daily work. Compress old entries weekly to keep focused on current tasks.

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
