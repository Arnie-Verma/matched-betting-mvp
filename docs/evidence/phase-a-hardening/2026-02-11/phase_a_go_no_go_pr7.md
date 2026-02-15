# Phase A GO/NO-GO Report (PR7)

Date: 2026-02-15

## Gate Checklist

1. Priority competitions validated (`epl`, `nba`, `nhl`, `boxing`, `nbl`): PASS
2. No unresolved critical FAILs for in-scope books: PASS
3. Local canary complete (30-60 min, 10-20 cycles): PASS

## Evidence Pointers

- Decomposition matrix (required PR7 step):
  - `pr7_failure_decomposition_matrix.json`
  - `pr7_failure_decomposition_matrix.md`
- Live validation artifacts:
  - `validation_live_epl_pr7.json`
  - `validation_live_nba_pr7.json`
  - `validation_live_nhl_pr7.json`
  - `validation_live_boxing_pr7.json`
  - `validation_live_nbl_pr7.json`
  - `priority_competition_summary_table_live_pr7.md`
  - `pr7_reason_breakdown_after.json`
  - `pr7_fail_warn_reduction_summary.json`
- Canary artifacts:
  - `phase_a_canary_pr7.json`
  - `phase_a_canary_pr7.md`
- DB evidence:
  - `pr7_db_query_outputs.md`

## Key Results

- PR7 fail decomposition (from PR6.1 baseline):
  - `coverage denominator mismatch`: 18 (EPL)
  - `event mapping miss`: 18 (boxing)
  - `market-shape/key mismatch`: 0
  - `probability anomaly`: 0
- PR7 live status totals:
  - `PASS=52`, `WARN=31`, `SKIP=22`, `FAIL=0`
- EPL status:
  - `PASS=7`, `WARN=14`, `FAIL=0`
- Boxing status:
  - `WARN=3`, `SKIP=18`, `FAIL=0`
- Canary (`phase_a_canary_pr7.json`):
  - Duration: `1852.80s` (~30.9 min)
  - Cycles: `13`
  - Breaker open cycles: `0`
  - In-scope FAIL cycles: `0/13`
  - Gate pass: `true`

## Decision

GO for Phase A hardening gate.

## Rollback Notes

1. Keep `BOOKMAKER_FREEZE_UNIBET=true` and `unibet.is_active=false` until explicit onboarding activation decision.
2. If validation quality regresses (in-scope FAIL reappears), immediately revert PR7 scope-policy/filter changes and rerun canary:
   - `apps/worker/src/scrapers/punterstech_scraper.py`
   - `apps/worker/src/validation/config.py`
   - `apps/worker/src/validation/score_calculator.py`
3. Preserve PR7 evidence artifacts for traceability before any policy rollback.
