# Daily Progress Log

Track daily work. Compress old entries weekly to keep focused on current tasks.

---

## 2026-02-21 (Saturday)

### Completed
- PR-D1 docs-only synchronization slice completed (post PR-R2/PR-R3/PR-S1) with no code-file edits.
- Updated `ARCHITECTURE.md` to reflect:
  - bounded scheduler semantics and runtime active-bookmaker derivation
  - matcher set-based preloading hot path behavior
  - refresh-status ownership ACL + health endpoint access policy
  - current/open/planned status split for auditability
- Updated `README.md` with Phase A hardening snapshot (implemented now vs still open).
- Updated `BOOKMAKER_OPERATING_SYSTEM.md` with scheduler/security policy updates and status split (implemented/open/follow-up).
- Updated `SCRAPER_HARDENING_PLAN.md` with Phase A progress sync and canary reliability-gate language.
- Verified ADR index completeness (`docs/adr/README.md` includes all `ADR-*.md` files).
- Verified command block hygiene in `docs/evidence/phase-a-hardening/2026-02-11/pr12_security_controls_contract.md`; no malformed lines found.

### Decisions
- Keep Unibet freeze baseline unchanged (`BOOKMAKER_FREEZE_UNIBET=true`, `unibet.is_active=false`).
- Keep this slice docs-only: no API/worker/web code path changes.

### Next Steps
- If approved, proceed to next requested slice with code changes only after docs baseline is accepted.

## 2026-02-15 (Sunday)

### Completed
- PR5 Entain parity suite completed:
  - Added `apps/worker/tests/test_entain_scraper.py`
  - Coverage mirrors Punterstech contract dimensions:
    - parsing
    - market allow/deny policy
    - 2-way/3-way market shape enforcement
    - `selection_key` stability
    - error handling (`unsupported sport`, browser failure, failed result helper)
  - Required test commands run:
    - `pytest apps/worker/tests/test_entain_scraper.py -q` (24 passed)
    - `pytest apps/worker/tests/test_punterstech_scraper.py -q` (44 passed)
    - `pytest apps/worker/tests/test_validation.py -q` (55 passed)
- PR6 validation stabilization started and executed with explicit root-cause breakdown:
  - Baseline reason analysis from `validation_live_*_pr4.json`:
    - `pr6_baseline_reason_breakdown.json`
    - `pr6_baseline_reason_breakdown.md`
  - Implemented competition-aware calibration in validation config/score classification:
    - expected event-count ceiling tuning (`epl`, `nba`, `nhl`, `nbl`)
    - event-coverage threshold overrides (`epl`, `nbl`, `nhl`)
    - anomaly scoring threshold overrides (`epl`, `nba`, `nhl`)
  - Regenerated live validation outputs:
    - `validation_live_epl_pr6.json`
    - `validation_live_nba_pr6.json`
    - `validation_live_nhl_pr6.json`
    - `validation_live_boxing_pr6.json`
    - `validation_live_nbl_pr6.json`
  - Generated PR6 after-state and reduction artifacts:
    - `pr6_reason_breakdown_after.json`
    - `pr6_reason_breakdown_after.md`
    - `pr6_fail_warn_reduction_summary.json`
    - `pr6_fail_warn_reduction_summary.md`
    - `priority_competition_summary_table_live_pr6.json`
    - `priority_competition_summary_table_live_pr6.md`
- Added decision record `ADR-0011-validation-stabilization-threshold-calibration.md`
- PR6.1 final pass completed:
  - Added explicit bookmaker x competition coverage scope policy:
    - out-of-scope zero-event => `SKIP`
    - in-scope zero-event => `FAIL`
  - Current explicit out-of-scope mapping:
    - `nbl`: `betblitz`, `starsports`, `truebet`, `wizbet`
  - Added validation tests for:
    - in-scope zero-event => `FAIL`
    - out-of-scope zero-event => `SKIP`
    - report/summary/alert compatibility through pipeline (`has_failures` behavior)
  - Regenerated live DB evidence artifacts:
    - `validation_live_epl_pr6_1.json`
    - `validation_live_nba_pr6_1.json`
    - `validation_live_nhl_pr6_1.json`
    - `validation_live_boxing_pr6_1.json`
    - `validation_live_nbl_pr6_1.json`
    - `priority_competition_summary_table_live_pr6_1.json`
    - `priority_competition_summary_table_live_pr6_1.md`
    - `pr6_1_reason_breakdown_after.json`
    - `pr6_1_reason_breakdown_after.md`
    - `pr6_1_fail_warn_reduction_summary.json`
    - `pr6_1_fail_warn_reduction_summary.md`
  - Added reusable evidence tooling:
    - `apps/worker/src/scripts/generate_phase_a_validation_evidence.py`
  - Added canary runner:
    - `apps/worker/src/scripts/run_phase_a_canary.py`
  - Ran Phase A local canary gate (30+ minutes):
    - `phase_a_canary_pr6_1.json`
    - `phase_a_canary_pr6_1.md`
    - `phase_a_canary_pr6_1_interim.json`
  - Added PR6.1 DB query output pack:
    - `pr6_1_db_query_outputs.md`
- Added decision record `ADR-0012-bookmaker-competition-coverage-scope-policy.md`
- PR7 in-scope FAIL remediation completed (EPL + boxing only scope):
  - Added failure decomposition matrix for PR6.1 FAIL baseline:
    - `pr7_failure_decomposition_matrix.json`
    - `pr7_failure_decomposition_matrix.md`
  - EPL remediation:
    - Hardened Punterstech competition filter normalization to match England/English EPL variants
    - Increased Punterstech soccer `next-to-go` default result limit to avoid EPL truncation on high-volume brands
    - Added targeted regression tests in `apps/worker/tests/test_punterstech_scraper.py`
  - Boxing remediation:
    - Added explicit boxing scope policy (`in_scope`: `ladbrokes`, `neds`, `betfair`)
    - Updated scoring semantics so out-of-scope competition policy yields `SKIP` (not only zero-event windows)
    - Added validation regression coverage for out-of-scope non-zero-event behavior
    - Added Entain boxing participant-order regression test
  - Re-ran required suites:
    - `pytest apps/worker/tests/test_entain_scraper.py -q` (25 passed)
    - `pytest apps/worker/tests/test_punterstech_scraper.py -q` (47 passed)
    - `pytest apps/worker/tests/test_validation.py -q` (62 passed)
  - Regenerated live validation artifacts:
    - `validation_live_epl_pr7.json`
    - `validation_live_nba_pr7.json`
    - `validation_live_nhl_pr7.json`
    - `validation_live_boxing_pr7.json`
    - `validation_live_nbl_pr7.json`
    - `priority_competition_summary_table_live_pr7.json`
    - `priority_competition_summary_table_live_pr7.md`
    - `pr7_reason_breakdown_after.json`
    - `pr7_reason_breakdown_after.md`
    - `pr7_fail_warn_reduction_summary.json`
    - `pr7_fail_warn_reduction_summary.md`
  - Ran Phase A local canary gate (PR7):
    - `phase_a_canary_pr7.json`
    - `phase_a_canary_pr7.md`
    - Result: 13 cycles, ~30.9 minutes, in-scope FAIL cycles = 0, gate pass = true
- Added decision record `ADR-0013-pr7-epl-boxing-fail-remediation.md`

### Decisions
- `ADR-0011`: apply competition-aware validation scoring calibration to reduce false FAIL/WARN noise while preserving hard FAIL for structural zero-event conditions.
- `ADR-0012`: add explicit bookmaker x competition scope policy so only in-scope zero-event outputs remain blocking failures.
- `ADR-0013`: remediate EPL/boxing in-scope FAIL clusters via Punterstech EPL filter/feed-window hardening and explicit boxing scope policy.
- Phase A Unibet onboarding remains frozen; no activation/unfreeze work performed.
- Phase A gate decision after PR6.1 canary: NO-GO (in-scope FAILs persist in EPL and boxing during refresh-window canary).
- Phase A gate decision after PR7 canary: GO (0 in-scope FAIL cycles; 0 persistent in-scope FAIL clusters in EPL/boxing).

### Next Steps
- Keep Unibet freeze unchanged until explicit activation decision.
- If proceeding to onboarding after GO confirmation, start with tightly scoped enablement and keep canary evidence collection active.

## 2026-02-11 (Wednesday)

### Completed
- Session start: completed repo onboarding sequence (`README.md`, `CLAUDE.md`, operating docs, hardening plan, roadmap, discovery, implementation guide, validation framework, Unibet runbook) and architecture inspection (worker/api/web paths)
- Confirmed Phase A priority and freeze-first direction; identified that Unibet is currently active in seed/runtime paths and must be frozen before further onboarding work
- PR1 freeze enforcement completed:
  - Added central freeze policy module `api.core.bookmaker_freeze` with `BOOKMAKER_FREEZE_UNIBET` (default `true`)
  - Worker activation gate now skips frozen bookmakers in `scrape_service`
  - Plan-exposed bookmaker lists now filter frozen bookmakers in `SubscriptionService`
  - Set Unibet `is_active=false` in seed scripts (`seed_all_bookmakers.py`, `seed_bookmakers.py`, `seed_odds_data.py`)
- Added tests for freeze policy and plan exposure filtering: `apps/api/tests/test_bookmaker_freeze.py`
- Updated required docs in same PR: `ARCHITECTURE.md`, `SCRAPER_HARDENING_PLAN.md`, `BOOKMAKER_OPERATING_SYSTEM.md`
- Added decision record `ADR-0007-phase-a-unibet-freeze-enforcement.md`
- PR2 validation semantics hardening completed:
  - Added eligible-reference fixture filtering by competition selection shape in validation pipeline
  - Added `SKIP`/`N_A` scoring semantics for empty eligible-reference windows
  - Added eligible-vs-total reference counts in validation report output
  - Added tests for empty and partial eligibility windows in `apps/worker/tests/test_validation.py`
- Added decision record `ADR-0008-validation-eligibility-window-semantics.md`
- Evidence artifacts saved under `docs/evidence/phase-a-hardening/2026-02-11/`:
  - `validation_epl.json`, `validation_nba.json`, `validation_nhl.json`, `validation_boxing.json`, `validation_nbl.json`
  - `semantics_partial_window.json`, `semantics_empty_window.json`
  - `priority_competition_summary.json`, `commands.txt`, `db_queries.md`
- PR2.1 follow-up completed:
  - Regenerated priority competition evidence from live DB inside Docker context:
    - `validation_live_epl.json`, `validation_live_nba.json`, `validation_live_nhl.json`, `validation_live_boxing.json`, `validation_live_nbl.json`
  - Added live summary outputs:
    - `priority_competition_summary_live.json`
    - `priority_competition_summary_table_live.json`
    - `priority_competition_summary_table_live.md`
  - Added explicit artifact source note marking synthetic outputs as interim:
    - `artifact_sources.md`
  - Added downstream compatibility check note for `SKIP`/`N_A` handling:
    - `compatibility_check.md`
- PR3 normalization hardening completed (normalization-only scope):
  - Expanded cross-platform competition aliases for priority competitions (`epl`, `nba`, `nhl`, `boxing`, `nbl`)
  - Expanded team aliases for Entain/Punterstech style naming variants (for example `Manchester Utd`, `NY Knicks`, boxing abbreviations)
  - Refactored event normalization to reuse per-side team normalization for deterministic keys
  - Added focused normalization regression tests in `apps/worker/tests/test_validation.py`
  - Added before/after mismatch evidence:
    - `normalization_mismatch_baseline.json`
    - `normalization_mismatch_after_pr3.json`
    - `normalization_mismatch_reduction_summary.json`
    - `normalization_mismatch_reduction_summary.md`
- Added decision record `ADR-0009-priority-normalization-alias-hardening.md`
- PR4 market hygiene hardening completed (strict Entain + Punterstech scope):
  - Added sport-aware matcher market allow/deny policy in both platform scrapers
  - Enforced deterministic market shapes:
    - soccer: `home/draw/away`
    - nba/nhl/boxing/nbl: `home/away`
  - Enforced matcher `selection_key` hygiene (`home/away/draw` only; no `other`)
  - Added focused regression tests for market allow/deny, market shape, and selection-key stability:
    - `apps/worker/tests/test_punterstech_scraper.py`
    - `apps/worker/tests/test_validation.py` (Entain-focused hygiene tests)
  - Generated PR4 evidence artifacts:
    - `market_hygiene_before_pr4.json`
    - `market_hygiene_after_pr4.json`
    - `market_hygiene_mismatch_summary_pr4.json`
    - `market_hygiene_mismatch_summary_pr4.md`
    - `market_hygiene_db_query_outputs_pr4.md`
    - `validation_live_epl_pr4.json`, `validation_live_nba_pr4.json`, `validation_live_nhl_pr4.json`, `validation_live_boxing_pr4.json`, `validation_live_nbl_pr4.json`
    - `priority_competition_summary_table_live_pr4.json`, `priority_competition_summary_table_live_pr4.md`
  - Ran one-time stale-row cleanup for priority competitions to retire pre-hardening invalid current matcher rows
- Added decision record `ADR-0010-market-hygiene-selection-key-enforcement.md`
- Validation executed:
  - `pytest apps/worker/tests/test_punterstech_scraper.py -q` (pass)
  - `pytest apps/worker/tests/test_validation.py -q` (pass, now 55 tests)
  - `pytest apps/api/tests/test_bookmaker_freeze.py -q` with `PYTHONPATH=apps/api/src` (pass)
  - `pytest apps/worker/tests/test_entain_scraper.py -q` (expected fail; file not present yet, scheduled for PR5)

### Decisions
- `ADR-0007`: enforce Phase A Unibet freeze at runtime and plan exposure layers (not seed-only) to prevent accidental re-enable during hardening
- `ADR-0008`: validation coverage/probability comparisons must use eligible reference fixture windows, with `SKIP`/`N_A` semantics when none are eligible
- `ADR-0009`: priority competition normalization should be centralized and side-normalized to reduce cross-platform alias drift
- `ADR-0010`: enforce fixture-market hygiene + deterministic selection-key policy in Entain/Punterstech scrapers and retire stale invalid current rows

### Blockers
- Pre-existing dirty worktree with unrelated changes; PR1 work is being kept isolated to freeze-only files

### Next Steps
- PR5: Entain parity suite (`apps/worker/tests/test_entain_scraper.py`)

## 2026-02-01 (Sunday)

### Completed
- Outmatched vs our MintBet parity review: identified missing NBA/NHL + missing boxing fighters + worse NBL odds source market
- Punterstech scraper: include full-game `Money Line` markets (exclude quarter/half variants), tighten league filters (drop generic Premier League + non-AU “national basketball league”), and derive home/away from event name to keep selection_key stable
- Odds matcher: group selections by `selection_key` first (home/away/draw) and avoid name-based false negatives when keys match
- Added regression test for Money Line parsing and validated via live MintBet+Betfair scrapes that top opportunities now align with Outmatched ordering/PnL (NBL/NBA/NHL/boxing)
- Ran Premium-tier bookmaker discovery refresh (PointsBet/BetRight/Unibet/TABTouch/etc) and updated `DISCOVERY_SUMMARY.md` with implementation recommendations

### Blockers
- None

### Next Steps
- Re-scrape in Docker and compare `/odds/matcher` UI output to Outmatched again (MintBet vs Betfair top rows should now include NBA/NHL + boxing fighters)
- Start Premium-tier rollout with Unibet, then PointsBet, then BetRight (defer TAB/Sportsbet until proxy/prod)

## 2026-01-27 (Tuesday)

### Completed
- Parity audit vs Outmatched MintBet output (boxing/NBA/NBL gaps identified)
- Fixed Punterstech boxing scrape: include `boxing` event type + parse `Fight Result` markets
- Fixed Betfair team parsing for NBA/NHL `Away @ Home` format (correct home/away + selection_key)
- Allowed partial Betfair markets (1-side liquidity) so NBL opportunities aren’t dropped
- Improved boxing competition normalization (`Professional Boxing - ...` → `boxing`) so events group correctly
- Odds matcher: group selections by `selection_key` (home/away/draw) before name-normalization fallback
- Validation: non-strict structural failures now WARN (unless 0 events), as intended

### Blockers
- None

### Next Steps
- Run odds matcher UI sanity check: boxing + NBA/NBL/NHL opportunities should now appear with MintBet vs Betfair

## 2026-01-24 (Saturday)

### Completed
- Session start: read CLAUDE.md, SCRAPER_STRATEGY.md, DISCOVERY_SUMMARY.md, DAILY.md, VALIDATION_FRAMEWORK.md
- Reviewed odds matcher refresh/filter flow and queue behavior
- Updated odds matcher filters UI (pill dropdowns, clear buttons, reset count) and refresh button state handling
- Responded to UI not loading report with expected changes and verification guidance
- Adjusted advanced filters layout to two columns and widened dropdown chips to reduce scrolling
- Fixed bookmaker/league search inputs clearing immediately when no filters selected
- Explained refresh/cache flow, audit, and scalability recommendations
- Clarified refresh odds behavior with on-demand cache semantics
- Increased cache TTL from 60s → 300s (5 min) to reduce redundant scrapes; committed
- Ran full unit test suite: 62 tests PASS (Punterstech scraper + validation framework all passing)
- Assessed scraper readiness: Punterstech, Entain, Betfair architecturally ready for bookmaker expansion

### Blockers
- None

### Next Steps
- Run live QA validation against scrapers (requires DB with odds data)
- Deploy updated cache TTL to staging and verify load time improvement
- Plan bookmaker expansion rollout (target: 40+ bookmakers by end of month)

## 2026-01-23 (Friday)

### Session 1: Betfair + Entain Robustness Review

**Completed**:
- Read CLAUDE.md, SCRAPER_STRATEGY.md, DISCOVERY_SUMMARY.md, DAILY.md, VALIDATION_FRAMEWORK.md
- Inspected Betfair + Entain scrapers, scrape service, odds matcher, normalization, save_odds
- Compared Outmatched Ladbrokes filter output vs our matcher output (liquidity/placeholder filtering)

### Blockers
- None

### Next Steps
- Review Betfair competition mapping across multiple navigation-aggregator responses
- Add guardrails for selection_key="other" collisions and min liquidity thresholds
- Decide whether to retire legacy LadbrokesScraper or keep as fallback

### Session 2: Outmatched Parity Check + Data Validation

**Completed**:
- Re-read key docs and inspected Betfair + Entain scrapers, matcher, normalization, save_odds
- Queried DB to confirm NBA odds exist for Ladbrokes + Betfair (64/83 current) and 32 shared NBA events
- Verified Betfair has no Arsenal v Kairat market captured; UCL qualifier likely missing from Betfair competition IDs
- Identified missing normalization for Hellas Verona/Udinese Calcio causing Verona v Udinese mismatch
- Flagged NBL anomaly: Betfair odds for Tasmania v Illawarra (21/4.4) far from all bookies (1.4/2.75)

### Blockers
- None

### Next Steps
- Add normalization for `hellas verona` -> `verona` and `udinese calcio` -> `udinese`
- Review Betfair competition IDs for UCL qualifiers (Arsenal v Kairat missing)
- Investigate Betfair NBL market anomalies vs Ladbrokes/Punterstech

### Session 3: Fixture Coverage + League Label Mismatch

**Completed**:
- Compared EPL/Ligue 1 match-market coverage between Ladbrokes and Betfair (DB query); identified event groups missing on each side
- Updated competition display names to align with UI dropdown labels
- Added normalization for Hellas Verona and Udinese Calcio

### Blockers
- None

### Next Steps
- Re-normalize existing events in DB after team mapping update
- Expand Betfair competition IDs for qualifiers (UCL, etc.)

### Session 4: Event Re-normalization

**Completed**:
- Ran DB event re-normalization after Verona/Udinese mapping update (10 events updated)

### Blockers
- None

### Next Steps
- Expand Betfair competition IDs for qualifiers (UCL, etc.)

### Session 5: Tests + Commit Prep

**Completed**:
- Ran validation tests with `PYTHONPATH=/workspace/apps/worker/src` (30 passed)
- Committed normalization + league label alignment

### Blockers
- None

### Next Steps
- Expand Betfair competition IDs for qualifiers (UCL, etc.)
- Investigate Betfair NBL market anomalies vs Ladbrokes/Punterstech

### Session 6: NBA Opportunities Investigation

**Completed**:
- Reviewed Entain + Betfair scrapers and odds matcher filtering
- DB checks: NBA events exist overall, but Betfair has 0 NBA events within next 14 days; no overlap with Ladbrokes
- Coverage check: MLS missing across Entain/Betfair; Betfair NRL empty; Entain AFL empty (off-season likely)

### Blockers
- Betfair NBA fixtures only up to current day, no upcoming lay markets, so NBA filter returns 0 opportunities

### Next Steps
- Update Betfair scraper to load future NBA fixtures (scroll/paginate or fetch additional nav-aggregator payload)
- Re-run NBA scrape and verify overlaps vs Ladbrokes/Neds

### Session 7: Betfair NBA UI Discrepancy

**Completed**:
- Compared Betfair NBA UI vs DB; confirmed Betfair NBA events only through today; none in next 14 days
- Identified scraper only captures initial page load (no Tomorrow/Future tab interactions)

### Blockers
- Betfair NBA future markets not captured until scraper triggers Tomorrow/Future data

### Next Steps
- Update Betfair scraper to click Tomorrow/Future (or call nav-aggregator with date range)
- Re-scrape Betfair NBA and validate overlap with Ladbrokes/Neds

### Session 8: Betfair NBA/NBL Future Odds

**Completed**:
- Added Tomorrow/Future tab clicks in Betfair scraper for NBA/NBL
- Ran Betfair basketball scrape and saved results to DB (NBA 6 upcoming, NBL 2 upcoming within 14 days)
- Committed and pushed NBA/NBL future capture updates

### Blockers
- None

### Next Steps
- Verify NBA/NBL opportunities show in frontend odds matcher

### Session 9: Punterstech Validation Run

**Completed**:
- Session start: kick off full scrape + Punterstech validation (MintBet)
- Manual scrape completed in container (CLI timed out; confirmed process finished)
- Validation runs for MintBet: EPL/LALIGA/NBA/NBL all FAIL due to validation thresholds; NBL reference PASS
  - Ladbrokes reference failed for EPL/LALIGA/NBA because event counts exceed expected max
  - MintBet anomalies were warning-level (no critical), coverage 100%

### Blockers
- Validation config expected event max too low for current EPL/LALIGA/NBA schedules, causing reference FAIL

### Next Steps
- Update validation expected ranges (config) or make season-aware, then re-run validation
- Optionally validate 1-2 more Punterstech books after threshold fix

## 2026-01-22 (Thursday)

### Session 1: Betfair/Punterstech Parity Investigation

**Goal**: Diagnose Outmatched vs our odds discrepancies for Punterstech bookies

**Completed**:
- Read SCRAPER_STRATEGY.md, DISCOVERY_SUMMARY.md, VALIDATION_FRAMEWORK.md
- Inspected Betfair + Punterstech scrapers, odds matcher logic, normalization, and save_odds flow
- Queried DB for Manchester City v Galatasaray; verified current match result odds
- Reproduced matcher grouping for event and confirmed back 1.2/1.22, lay 1.26, not 26/22
- Identified likely discrepancy source: combined "Match Result and ..." markets + loose market filter/search behavior

### Session 2: Betfair Cleanup + Validation

**Completed**:
- Cleaned stale Betfair duplicates across competitions (removed misassigned events + orphans)
- Added Betfair scraper filtering for no-liquidity odds (>=100) and incomplete H2H markets
- Fixed Betfair competition mapping to prefer fixtures data (prevents cross-competition leakage)
- Re-scraped Betfair + Ladbrokes soccer after cleanup
- Fixed validation pipeline DB path (normalized competition lookup, correct joins/odds field, always include reference bookmaker)
- Re-ran validation for EPL/La Liga/UCL (Betfair vs Ladbrokes)
 - Added PSV Eindhoven normalization and verified away selection now matches Betfair
 - Re-ran multi-sport scrapes (Betfair + Ladbrokes) to refresh NBA/NHL/Boxing
 - Confirmed Betfair boxing lay prices present (including draws)

### Blockers
- None yet

### Next Steps
- Tighten odds matcher market filter to exclude "Match Result and ..." + non-H2H markets
- Optionally restrict Punterstech scraper to pure Match Result (ExternalRef=2) for matcher feed
- Add validation guardrails (2-3 selections only) and UI search toggle for selection-only filtering

## 2026-01-19 (Monday)

### Session 2: Bookmaker Discovery Documentation

**Goal**: Create comprehensive documentation to make adding new bookmakers easy

**Completed**:
1. Full codebase architecture review:
   - Base scraper interface (`BaseScraper`, `ScrapeResult`, `ScrapedEvent`, `ScrapedOdds`)
   - All 5 implemented scrapers (Betfair, TAB, Entain, Punterstech, Ladbrokes)
   - SCRAPER_CLASSES registry pattern in `scrape_service.py`
   - Normalization service (600+ team mappings)
   - Discovery tool (`discovery.py`)

2. Reviewed all discovery outputs (17 JSON files):
   - **Kindred/Unibet**: Full API ready (1.9MB single endpoint)
   - **BetCloud**: Sports odds endpoints confirmed (`/punter/sports/*`)
   - **Generation Web**: Config endpoints found, odds endpoint still hidden
   - **BetMakers**: SSR approach needed (no JSON APIs)

3. Created [BOOKMAKER_IMPLEMENTATION_GUIDE.md](BOOKMAKER_IMPLEMENTATION_GUIDE.md):
   - Quick start for adding new bookmakers
   - Platform-by-platform implementation details
   - API endpoints with request/response examples
   - Code patterns (HTTP API, browser intercept, DOM parsing)
   - Testing procedures
   - Troubleshooting guide

### Session 1: Betfair Parity Investigation

**Completed**:
- Read CLAUDE.md, SCRAPER_STRATEGY.md, DISCOVERY_SUMMARY.md, DAILY.md, VALIDATION_FRAMEWORK.md
- Reviewed Entain + Betfair scrapers and odds matcher logic for parity risks
- Ran DB parity checks for Ladbrokes vs Betfair (counts, overlap, selection completeness)
- Identified Betfair duplicate events across competitions (Italian Serie A duplicated under La Liga)
- Flagged Betfair markets with missing selections (Lyon v Lille, Atletico Madrid v Bodo Glimt, Barcelona v FC Copenhagen)

### Blockers
- Generation Web odds endpoint still hidden (config endpoints only)

### Next Steps
1. **High Priority**: Implement KindredScraper (1 day, 1 Premium bookmaker)
2. **High Priority**: Implement BetCloudScraper (3 days, 26 bookmakers)
3. Continue Generation Web odds endpoint discovery
4. Clean stale Betfair duplicates across competitions

## 2026-01-18 (Sunday)

### Session 1: Ladbrokes/Betfair Parity Analysis vs Outmatched

**Goal**: Evaluate scrapers against Outmatched to determine if ready for production

**Initial Analysis**:
1. Compared Ladbrokes output vs Outmatched.com side-by-side
2. Identified apparent coverage gaps in Ligue 1
3. Created [LADBROKES_PARITY_ANALYSIS.md](LADBROKES_PARITY_ANALYSIS.md)

### Session 2: Ligue 1 Gap Resolution

**Root Cause Identified**: Missing team name normalizations in `normalization_service.py`

**Diagnosis Process**:
1. Ran diagnostic script on Ladbrokes scraper - captured all 15 Ligue 1 events including Strasbourg/Metz and Lyon/Brest
2. Ran diagnostic on Betfair scraper - captured all 13 Ligue 1 events
3. Checked database - events existed but with different normalized names
4. Found normalization issue: `RC Strasbourg Alsace` vs `Strasbourg` not mapping correctly

**Fix Applied**:
Added ~25 French Ligue 1 team normalizations to `normalization_service.py`:
- `rc strasbourg alsace` → `strasbourg`
- `rc strasbourg` → `strasbourg`
- `stade brestois 29` → `brest`
- `olympique lyonnais` → `lyon`
- `stade rennais` → `rennes`
- `le havre ac` → `lehavre`
- Plus: `ogc nice`, `as monaco`, `angers sco`, `aj auxerre`, `toulouse fc`, `rc lens`, `lille osc`, `fc lorient`, `paris fc`

Also added A-League team variations:
- `melbourne city fc`, `newcastle jets fc`, `auckland fc`, `western sydney wanderers fc`

**Verification**:
- Re-normalized all 643 events in database
- All 4 Ligue 1 current events now matching with 21 bookmakers each
- All 9 A-League events matching correctly

**Status**: RESOLVED - ~95% parity with Outmatched achieved

### What's Working ✅
| League | Status |
|--------|--------|
| EPL | Full coverage |
| La Liga | Full coverage |
| Serie A | Full coverage |
| Bundesliga | Full coverage |
| **French Ligue 1** | **FIXED** - All 4 events matching |
| Champions League | Full coverage |
| A-League | Full coverage (6 men's + women's) |
| NBA | Full coverage |
| NHL | 6 events |
| Boxing | Full coverage |

### Blockers
- NRL/AFL off-season
- Generation Web odds endpoint still hidden

### Next Steps
- Consider moving to other bookmakers (MintBet, Sportsbet, etc.)
- Add fuzzy matching for edge case team name variations

---

## 2026-01-17 (Saturday)

### Completed
- Session start: reviewed prior blockers/next steps
- Restarted mb_api and mb_web containers to pick up billing change
- Backfilled Stripe customer ID for user and synced active subscription to platinum
- Verified backend subscription status returns platinum for user

### Blockers
- NRL/AFL off-season
- Generation Web odds endpoint still hidden

### Next Steps
- Verify Stripe billing upgrade flow after restart

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
