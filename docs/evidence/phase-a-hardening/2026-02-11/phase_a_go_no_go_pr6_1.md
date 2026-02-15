# Phase A GO/NO-GO Report (PR6.1)

Date: 2026-02-15

## Gate Checklist

1. Priority competitions validated (`epl`, `nba`, `nhl`, `boxing`, `nbl`): PASS
2. No unresolved critical FAILs for in-scope books: FAIL
3. Local canary complete (30-60 min, 10-20 cycles): PASS

## Evidence Pointers

- Live validation artifacts:
  - `validation_live_epl_pr6_1.json`
  - `validation_live_nba_pr6_1.json`
  - `validation_live_nhl_pr6_1.json`
  - `validation_live_boxing_pr6_1.json`
  - `validation_live_nbl_pr6_1.json`
  - `pr6_1_reason_breakdown_after.json`
  - `pr6_1_fail_warn_reduction_summary.json`
  - `priority_competition_summary_table_live_pr6_1.md`
- Canary artifacts:
  - `phase_a_canary_pr6_1.json`
  - `phase_a_canary_pr6_1.md`
- DB evidence queries:
  - `pr6_1_db_query_outputs.md`

## Key Results

- PR6.1 fixed NBL false FAILs for out-of-scope books:
  - `betblitz`, `starsports`, `truebet`, `wizbet` now `SKIP` on NBL zero-event windows.
- Current live status totals after canary refresh state:
  - `PASS=48`, `WARN=17`, `SKIP=4`, `FAIL=36`
- In-scope FAIL clusters:
  - EPL: 18 books (`event_coverage=53.19%`, fail threshold `55%`)
  - Boxing: 18 books (`coverage=0% < 70%`)
- Canary:
  - Duration: `1815.28s` (~30.25 min)
  - Cycles: `14`
  - Breaker open cycles: `0`
  - In-scope FAIL cycles: `14/14`

## Decision

NO-GO for Phase A promotion to Unibet onboarding.

## Rollback Notes

1. Keep `BOOKMAKER_FREEZE_UNIBET=true` and `unibet.is_active=false`.
2. Do not promote any new bookmaker to active onboarding flow.
3. Keep current PR6.1 scope policy for NBL (`out_of_scope` mapping) because it fixed proven false FAILs.
4. Next remediation must address in-scope EPL/boxing FAIL clusters before re-running canary and reconsidering GO.
