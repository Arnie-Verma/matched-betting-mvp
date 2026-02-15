# Residual risks and open issues (PR2)

1. Entain parity suite is still missing.
- `apps/worker/tests/test_entain_scraper.py` does not exist yet.
- Scheduled for PR5.

2. Live evidence currently reflects seeded/local development bookmaker set.
- Expected for local hardening but not representative of production bookmaker quality.
- Use canary runs (PR6) for trend-based evidence and breaker/latency correlation.

3. `SKIP`/`N_A` are neutral statuses.
- They correctly prevent false FAIL/WARN in no-eligible windows.
- They are not promotion evidence; eligible-window runs are still required for GO.

## PR4 additions (market hygiene)

4. One-time cleanup was required to retire legacy `is_current=true` rows.
- New parser logic prevents new invalid matcher markets, but stale rows persisted from earlier runs until explicitly cleaned.
- Cleanup command + outputs are captured in `market_hygiene_db_query_outputs_pr4.md`.

5. Several priority validation statuses remain `FAIL`/`WARN` due probability thresholds and event-count ranges.
- PR4 scope was market hygiene only; threshold/semantics tuning remains under validation workstream follow-up.

6. NHL/boxing event availability can be sparse by source at certain run windows.
- Empty/low-volume windows can limit confidence in continuous parity despite hygiene correctness.
- Canary (PR6) is still required for trend-based reliability and breaker/latency evidence.

## PR6 additions (validation stabilization)

7. Threshold calibration reduced FAIL/WARN volume significantly, but may hide true pricing drift.
- Competition-aware anomaly thresholds are now less strict for `epl/nba/nhl`.
- Keep this as a temporary stabilization setting until canary trend evidence confirms safe bounds.

8. PR6.1 policy fixed NBL out-of-scope false FAILs, but canary refresh windows exposed new in-scope FAIL clusters.
- EPL: repeated in-scope FAIL for multiple books at `event_coverage=53.19%` versus current fail threshold `55%`.
- Boxing: repeated in-scope FAIL (`Coverage 0% < 70%`) once eligible-reference boxing windows became non-empty.

9. Canary gate remained NO-GO.
- `phase_a_canary_pr6_1.json` completed 14 cycles over 30+ minutes with stable breakers.
- Gate failed due unresolved in-scope FAIL rows in EPL and boxing (not NBL).

10. Promotion risk remains high until competition-scope policy/thresholds are reconciled for EPL and boxing.
- Current policy only classifies NBL out-of-scope books.
- Additional explicit scope policy or threshold recalibration is required before Phase A GO.

## PR7 additions (EPL + boxing remediation)

11. In-scope FAIL clusters for EPL/boxing are resolved, but WARN volume remains high.
- EPL currently carries widespread WARN from anomaly/event-coverage thresholds on non-reference books.
- NBL still has WARN-heavy rows for in-scope books.
- These are non-blocking for current gate policy but should be monitored post-promotion.

12. Boxing policy is explicitly scope-driven.
- Only `ladbrokes`, `neds`, `betfair` are in-scope for boxing in Phase A.
- Out-of-scope books are intentionally classified as `SKIP`, which reduces false FAILs but also excludes them from boxing gate strictness.

13. Betfair scrape failures for some non-priority sport cycles still occur during canary.
- `phase_a_canary_pr7.json` records repeated Betfair failures in basketball/ice_hockey/boxing scrape attempts.
- Breakers remained closed and in-scope validation gate still passed; monitor for production impact.
