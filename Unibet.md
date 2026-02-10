# Unibet (Kindred/FDJ) Implementation Plan

**Date**: 2026-02-01  
**Goal**: Add Unibet as a Premium back-bookmaker in the odds matcher, following the same production patterns as `EntainScraper` + `PunterstechScraper` (config-driven, consistent normalization, test coverage, validation-friendly).

---

## 0.1) Latest Reality Check (2026-02-03)

Unibet/Kindred is now **active** and producing data in DB for:
- Soccer: EPL, La Liga, Bundesliga, Serie A, Ligue 1, A-League, UCL, MLS
- Basketball: NBA (**NBL missing**, see below)
- Ice Hockey: NHL (moneyline)
- Boxing: Boxing

### Known Gaps / Bugs

1. **NBL is not scraping (Unibet)**
   - Current `KindredScraper` competition filter path is `basketball/nbl`, which returns **0** event items.
   - Unibet's own `sports/a-z` feed indicates the correct filter path is: `basketball/australia/nbl`.
   - Impact: no Unibet NBL opportunities; validation coverage will look worse than reality.

2. **A-League naming mismatch (Unibet vs Betfair)**
   - Unibet competition: `A-League`
   - Betfair competition: `A-League Men`
   - Impact: event grouping can split across bookmakers unless competition normalization unifies them.

3. **NHL market hygiene**
   - Unibet NHL now uses a **2-way moneyline** approach (via Kambi betoffers).
   - Older 3-way `Match Odds` NHL markets may still be marked `is_current=true` in DB from previous runs.
   - Impact: inflated NHL odds counts and noisier QA, even if the matcher prefers moneyline.

### "0 events" does not automatically mean broken

- AFL/NRL can legitimately be 0 within the current horizon depending on season timing + Unibet offering.

## 0) Current State (Repo Reality)

- Unibet **is not Entain** (it’s Kindred/FDJ). We already re-tagged it in seeding as `platform=kindred`, `scraper_class=kindred`.
- Kindred/Unibet scraper is implemented: `apps/worker/src/scrapers/kindred_scraper.py` (`KindredScraper`) and registered in `apps/worker/src/jobs/scrape_service.py` as `scraper_class=kindred`.
- Odds matcher now selects Betfair lay odds **per market-rank** (prevents cross-market mismatches like NHL Match Odds vs Moneyline).
- Odds matcher grouping is robust to competition naming differences because it groups by:
  - `normalize_event_name(event.name)` + `normalize_competition_name(event.competition.name)`
  - And selection grouping prefers `selection_key` (`home`/`away`/`draw`) first.

**Implication**: Unibet is implemented and active; remaining work is a small checklist (NBL filter-path fix, pipeline stale-market clearing, and a few targeted verification steps).

---

## 1) Data Sources + Request Model (Repo Reality)

### 1.1 Matches feed (primary)

Unibet exposes a public JSON feed that returns upcoming matches, markets, and odds:

```
GET https://www.unibet.com.au/sportsbook-feeds/views/filter/{filter_path}/matches?includeParticipants=true&useCombined=true
```

Important nuance (vs the earlier “one request per sport” framing):
- While `/{sport}/all/matches` exists, in practice it can be **incomplete**.
- The current implementation uses **competition filter paths** for coverage.

### 1.2 Filter-path discovery (source of truth)

Use this to confirm/derive correct `filter_path` strings (e.g., NBL nesting under Australia):

```
GET https://www.unibet.com.au/sportsbook-feeds/views/sports/a-z
```

### 1.3 Settings (optional)

```
GET https://www.unibet.com.au/sportsbook-feeds/settings?clientId=polopoly_desktop
```

### 1.4 NHL Moneyline (Kambi betoffers)

For NHL, the sportsbook-feeds list view often provides a 3-way regular-time market which does **not** match other bookmakers' 2-way moneyline (incl OT/SO).

Implemented approach:
- Use sportsbook-feeds to discover NHL event IDs + start times
- Fetch Kambi event betoffers per event:

```
GET https://oc-offering-api.kambicdn.com/offering/v2018/ubau/betoffer/event/{event_id}.json?lang=en_AU&market=AU&channel_id=1
```

### 1.5 Expected request volume + resilience knobs

Current feed plan in `apps/worker/src/scrapers/kindred_scraper.py`:
- Soccer: 8 competition feeds
- Basketball: 2 competition feeds (NBA + NBL)
- AFL: 1 competition feed
- NRL: 1 competition feed
- Boxing: 1 competition feed
- NHL: 1 competition feed **plus** 1 Kambi betoffer request per NHL event discovered

So a full Unibet scrape is roughly:
- Base feeds: `8 + 2 + 1 + 1 + 1 + 1 = 14` requests
- NHL Kambi: `+N` where `N = number of NHL events within horizon`

Resilience/rate-limit strategy (current implementation):
- Concurrency cap: `max_concurrent_requests` (default 4) in `KindredScraper`
- Retries/backoff: `max_retries` (default 3) with incremental sleep
- Timeouts: `timeout_seconds` (default 30)

If Unibet/Kambi starts responding with 429/5xx:
- Reduce `max_concurrent_requests`
- Increase backoff (add exponential + jitter) and respect `Retry-After` if present
- Keep logs tagged by `sport/competition_code` so failures are diagnosable

### Response Shape (Observed)

- Top-level: `{ viewId, session, layout, _links }`
- Odds live in: `layout.sections[].widgets[].matches.groups[].subGroups[].events[]`
- Each “event item” has:
  - `event`: `{ id, name, homeName, awayName, start, group, participants[], path[] ... }`
  - `betOffers`: list of markets
  - each bet offer has `betOfferType`, `criterion`, `outcomes[]` with `oddsDecimal`

---

## 2) Current Implementation (Already Built)

These items are already implemented in the repo and should **not** be re-built:

### 2.1 Scraper

- `apps/worker/src/scrapers/kindred_scraper.py`: `KindredScraper` implemented (direct HTTP via `httpx.AsyncClient`)
- Scrapes via competition filter paths (not sport/all) for coverage
- NHL: uses Kambi betoffers per event to extract 2-way moneyline

### 2.2 Registry wiring

- `apps/worker/src/jobs/scrape_service.py`: `"kindred": KindredScraper` exists in `SCRAPER_CLASSES`

### 2.3 Seed config (activation)

- `apps/api/src/api/scripts/seed_all_bookmakers.py`: `unibet` is active with:
  - `platform="kindred"`, `scraper_class="kindred"`
  - `horizon_days=21`

---

## 3) Parsing + Normalization Rules (Critical for Cross-Bookmaker Matching)

### 3.1 Sport mapping (Unibet → internal)

Implement `SPORT_SLUGS` in the Kindred scraper (initial scope aligned with current matcher support):

- `soccer` → `football`
- `basketball` → `basketball`
- `ice_hockey` → `ice_hockey` (feed slug uses underscores)
- `afl` → `australian_rules` (feed slug uses underscores)
- `nrl` → `rugby_league` (feed slug uses underscores)
- `boxing` → `boxing`

Note: the "website" sport slugs used for `source_url` are best-effort and can differ (hyphenated), but do not impact scraping.

### 3.1.1 Competition filter paths (critical)

Unibet "filter" paths are **not always** `/{sport}/{league}`. Example: NBL is nested under country.

- Incorrect (returns 0): `basketball/nbl`
- Correct: `basketball/australia/nbl`

Source of truth for these paths:
- `GET https://www.unibet.com.au/sportsbook-feeds/views/sports/a-z`

### 3.2 Competition selection (reduce noise + keep MVP scope tight)

Unibet returns *everything* (including esports). We should:

- Skip any event where `event.start` is missing or `start_time < now`
- Skip live events (`event.state == "STARTED"` or `item.liveData` present) for now (your matcher is “scheduled” oriented)
- Skip esports (detect in `event.path` or group name containing `esports`)
- Apply a competition allowlist per sport using values from:
  - `event.group` (often league like `NBA`, `NHL`, `Premier League`, `Upcoming Fights`)
  - or `event.path[]` names (league hierarchy)

If a Unibet league name doesn’t normalize into your known competition codes, add it to:
- `apps/api/src/api/services/normalization_service.py` → `COMPETITION_MAP`

### 3.3 Market selection (match-winner only)

We should only emit odds that your matcher already queries for:

- **Soccer**: “Match Result / 1X2” style (3 outcomes)
  - Identify bet offers where outcomes include `OT_ONE`, `OT_CROSS`, `OT_TWO`
  - Prefer regular-time markets over extra-time variants if both exist
  - Normalize market name to **`Match Result`**
- **AFL / NRL**: match winner (2 outcomes)
  - Prefer “Including Overtime”, then “Regular Time”
  - Normalize market name to **`Match Winner`**
- **Basketball**: **Moneyline** (2 outcomes)
  - Prefer `criterion.englishLabel` containing “Moneyline”
  - Normalize market name to **`Money Line`**
- **Ice Hockey (NHL)**: **Moneyline incl. overtime/shootout** (2 outcomes)
  - Discover events via sportsbook-feeds
  - Fetch event betoffers from Kambi (see section 1)
  - Select criterion containing “Moneyline” + “Including Overtime”
  - Normalize market name to **`Moneyline`**
- **Boxing**: “Bout Odds” / fight winner (2 outcomes + optional draw)
  - Same OT_* mapping works; normalize market name to **`Fight Betting`**

### 3.4 Selection key logic (must match other bookmakers)

Map Unibet outcomes using the stable `type` field:

- `OT_ONE` → `home` (selection name = home participant)
- `OT_TWO` → `away` (selection name = away participant)
- `OT_CROSS` → `draw` (selection name = `Draw`)

For team sports, “home/away” is real and should match other bookies.

For boxing (home/away is effectively arbitrary), we should:
- Treat `selection_key` as potentially unstable across bookmakers.
- Unibet/Kindred enforces deterministic fighter ordering (sorted by normalized name) and maps outcomes by participant name when available.
- Use the go/no-go rule in section 4.5 to decide whether to adjust boxing grouping strategy.

---

## 4) Tests (What Exists + What To Add)

### 4.1 What already exists

- `apps/worker/tests/test_kindred_scraper.py` already covers:
  - feed-shape parsing variants (groups/events/highlightedEvents)
  - market selection for soccer/basketball/afl/nrl/boxing
  - NHL moneyline via mocked Kambi payload
  - horizon/esports filtering
  - error handling + parallel aggregation

### 4.2 Add one regression test for the NBL filter path (no live dependency)

Goal: prevent future regressions like `basketball/nbl` returning 0.

Add a unit test that:
- patches `KindredScraper._request_json` and records called URLs
- calls `scrape_sport("basketball")`
- asserts the NBL request URL contains `views/filter/basketball/australia/nbl/matches`

Do **not** rely on live NBL availability; the test should validate URL selection logic and basic parsing on a minimal fixture feed.

---

## 4.5) Remaining Changes (Engineer Checklist)

This section is intentionally “diff/checklist style” so an engineer can execute without re-discovery.

### Change 1 — Fix Unibet NBL feed path (bug)

**Code**
- File: `apps/worker/src/scrapers/kindred_scraper.py`
- Location: `KINDRED_COMPETITION_FILTERS["basketball"]`
- Quick find: search for `("nbl",`
- Diff:
  - from: `("nbl", "basketball/nbl")`
  - to: `("nbl", "basketball/australia/nbl")`

**Tests (no live dependency)**
- File: `apps/worker/tests/test_kindred_scraper.py`
- Add a regression test that patches `KindredScraper._request_json`, calls `scrape_sport("basketball")`, and asserts the NBL request URL contains `views/filter/basketball/australia/nbl/matches`.

**Verify (DB)**
- After a scrape, confirm Unibet NBL current odds exist within horizon:
  - `docker exec mb_db psql -U postgres -d mb_dev -c "SELECT b.code, sp.code AS sport, c.name AS competition, COUNT(DISTINCT e.id) AS events, COUNT(o.id) AS odds FROM odds_snapshots o JOIN selections s ON o.selection_id = s.id JOIN markets m ON s.market_id = m.id JOIN events e ON m.event_id = e.id JOIN competitions c ON e.competition_id = c.id JOIN sports sp ON c.sport_id = sp.id JOIN bookmakers b ON o.bookmaker_id = b.id WHERE o.is_current = true AND b.code = 'unibet' AND sp.code = 'basketball' AND c.name = 'NBL' AND e.start_time >= NOW() AND e.start_time < NOW() + INTERVAL '21 days' GROUP BY b.code, sp.code, c.name;"`

### Change 2 — A-League naming: verify only (should already be handled)

This should not require code changes unless the proof fails:
- `apps/api/src/api/services/normalization_service.py` maps both `a-league` and `a-league men` → `aleague` (see `COMPETITION_MAP` under the “A-League” block).

**Proof**
- In odds matcher UI/API, filter to A-League and confirm at least one fixture groups Unibet back odds and Betfair lay odds together (same competition code `aleague`).

### Change 3 — NHL market hygiene: clear stale markets per event (pipeline fix)

Why this is needed:
- Persistence currently clears “current odds” only for incoming `selection_id`s.
- When the market changes (e.g., 3-way Match Odds → 2-way Moneyline), the old market’s selections can remain `is_current=true`.

**Code**
- File: `apps/worker/src/jobs/save_odds.py`
- Current logic to change: stale clearing at the selection_id level (`delete(OddsSnapshot).where(...)`, currently around lines ~120–128; quick find: `# First, mark old odds as not current`).
- Implement event-level stale clearing for the events being updated (clear all current odds for this bookmaker for those events before upserting new odds).

**Verify (DB)**
- After a fresh Unibet NHL scrape, ensure only moneyline is current:
  - `docker exec mb_db psql -U postgres -d mb_dev -c "SELECT m.name AS market, COUNT(o.id) AS odds FROM odds_snapshots o JOIN selections s ON o.selection_id = s.id JOIN markets m ON s.market_id = m.id JOIN events e ON m.event_id = e.id JOIN competitions c ON e.competition_id = c.id JOIN bookmakers b ON o.bookmaker_id = b.id WHERE o.is_current = true AND b.code = 'unibet' AND c.name = 'NHL' GROUP BY m.name ORDER BY COUNT(o.id) DESC;"`

### Change 4 — Boxing selection stability: go/no-go rule

Risk:
- Boxing has no true home/away; if bookmakers disagree on participant ordering, `selection_key` can mismatch and grouping can be wrong.

**Go**
- Boxing events match across Unibet and Betfair (or reference bookmaker) with high coverage (≥90%) and no repeated “swapped fighter” anomalies.

**No-go (requires follow-up)**
- Repeated mismatches where the same fight is grouped but fighters are swapped, or match coverage drops <90%.

If NO-GO triggers, prefer one of:
- change odds-matcher selection grouping for boxing to prefer normalized `selection_name` even when `selection_key` exists, or
- align deterministic ordering across all boxing-capable scrapers so `selection_key` becomes consistent everywhere.

---

## 5) Execution Runbook (After Changes)

1. Run unit tests:
   - `docker exec mb_worker pytest -q`
2. Re-seed bookmakers only if config changed:
   - `docker exec mb_api python -m api.scripts.seed_all_bookmakers`
3. Run a manual scrape:
   - `docker exec mb_api python ../worker/src/manual_scrape.py`
4. Run validation for core comps:
   - `docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition epl --bookmaker unibet`
   - `docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition nba --bookmaker unibet`
   - `docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition nhl --bookmaker unibet`
   - `docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition boxing --bookmaker unibet`
   - `docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition nbl --bookmaker unibet` (after NBL fix)
5. Odds matcher sanity:
   - Confirm Unibet appears as a back bookmaker and that NHL uses moneyline-only markets.

---

## 6) Rollout Strategy (Safe + Incremental)

1. **Stage 1 (low risk)**: soccer only (EPL + A-League + UCL)
2. **Stage 2**: NBA + NHL moneyline
3. **Stage 3**: boxing
4. Expand competitions once validation reports are clean and matching parity is stable.

---

## Confirmed Decisions (2026-02-01)

1. **Sport scope**: include all supported sports from day 1 (same as Entain/Punterstech): `soccer`, `afl`, `nrl`, `basketball`, `ice_hockey`, `boxing`.
2. **Competition allowlist** (standardized MVP set):
   - Soccer: A-League, EPL, French Ligue 1, German Bundesliga, Italian Serie A, MLS, Spanish La Liga, UEFA Champions League
   - AFL: AFL
   - NRL: NRL
   - Basketball: NBA, NBL
   - Ice Hockey: NHL
   - Boxing: Boxing
3. **Boxing selection stability**: treat as a go/no-go item (see section 4.5). If cross-bookmaker boxing mismatches appear, adjust grouping strategy or standardize deterministic ordering across scrapers.

---

## Addendum (2026-02-03): Confirmed Findings

1. **Unibet NBL filter path**: `basketball/australia/nbl` (not `basketball/nbl`).
2. **NHL**: use Kambi betoffer endpoint to extract 2-way moneyline (avoid 3-way regular-time mismatch).
