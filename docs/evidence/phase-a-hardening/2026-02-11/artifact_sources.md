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
