# Evidence Source Notes (PR2)

## Authoritative live DB-backed artifacts (Docker context)
Generated from inside `mb_api` with database connectivity (`db` network host):

- `validation_live_epl.json`
- `validation_live_nba.json`
- `validation_live_nhl.json`
- `validation_live_boxing.json`
- `validation_live_nbl.json`
- `priority_competition_summary_live.json`
- `priority_competition_summary_table_live.json`
- `priority_competition_summary_table_live.md`

## Interim synthetic artifacts (kept for traceability)
These were generated before Docker DB connectivity was available for evidence generation and are retained only as interim artifacts:

- `validation_epl.json`
- `validation_nba.json`
- `validation_nhl.json`
- `validation_boxing.json`
- `validation_nbl.json`
- `priority_competition_summary.json`
- `semantics_partial_window.json`
- `semantics_empty_window.json`

Use the `validation_live_*` and `priority_competition_summary_*_live.*` files for PR2 review decisions.

## PR4 live market-hygiene artifacts
Generated from Docker-connected DB context after PR4 scraper changes and stale-row cleanup:

- `market_hygiene_before_pr4.json`
- `market_hygiene_after_pr4.json`
- `market_hygiene_mismatch_summary_pr4.json`
- `market_hygiene_mismatch_summary_pr4.md`
- `market_hygiene_db_query_outputs_pr4.md`
- `validation_live_epl_pr4.json`
- `validation_live_nba_pr4.json`
- `validation_live_nhl_pr4.json`
- `validation_live_boxing_pr4.json`
- `validation_live_nbl_pr4.json`
- `priority_competition_summary_table_live_pr4.json`
- `priority_competition_summary_table_live_pr4.md`

## PR6 live validation-stabilization artifacts
- `validation_live_epl_pr6.json`
- `validation_live_nba_pr6.json`
- `validation_live_nhl_pr6.json`
- `validation_live_boxing_pr6.json`
- `validation_live_nbl_pr6.json`
- `priority_competition_summary_table_live_pr6.json`
- `priority_competition_summary_table_live_pr6.md`
- `pr6_baseline_reason_breakdown.json`
- `pr6_baseline_reason_breakdown.md`
- `pr6_reason_breakdown_after.json`
- `pr6_reason_breakdown_after.md`
- `pr6_fail_warn_reduction_summary.json`
- `pr6_fail_warn_reduction_summary.md`

## PR6.1 live validation + canary artifacts
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
- `phase_a_canary_pr6_1.json`
- `phase_a_canary_pr6_1.md`
- `phase_a_canary_pr6_1_interim.json`
- `pr6_1_db_query_outputs.md`
- `phase_a_go_no_go_pr6_1.md`

## PR7 live validation + canary artifacts
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
- `pr7_failure_decomposition_matrix.json`
- `pr7_failure_decomposition_matrix.md`
- `phase_a_canary_pr7.json`
- `phase_a_canary_pr7.md`
- `pr7_db_query_outputs.md`
- `phase_a_go_no_go_pr7.md`
