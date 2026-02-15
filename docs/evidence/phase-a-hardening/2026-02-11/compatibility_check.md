# Validation Status Compatibility Check (PR2)

Scope checked: reporting, summaries, alerts, and gate/exit behavior for new statuses `SKIP` and `N_A`.

## Reporting
- `apps/worker/src/validation/report_generator.py`
  - Adds explicit status symbols for `SKIP` and `N_A`.
  - Includes `skip_count` and `na_count` in report summaries and JSON.
  - Terminal output labels no-eligible-reference fixture windows explicitly.

Result: compatible.

## Summaries
- `apps/worker/src/validation/score_calculator.py`
  - Batch summarization tracks `skip_count` and `na_count`.
- `apps/worker/src/validation/pipeline.py`
  - Pipeline completion log now includes `SKIP`/`N_A` counts.

Result: compatible.

## Alerts
- `apps/worker/src/jobs/scrape_service.py`
  - Alerts trigger only when `result.has_failures` is true.
- `apps/worker/src/validation/pipeline.py`
  - `has_failures` is computed from `status == "FAIL"` only.

Result: compatible. `SKIP`/`N_A` do not trigger failure alerts, which is expected for neutral no-eligible-window semantics.

## Gates / Exit behavior
- `apps/worker/src/scripts/validate_scrapers.py`
  - CLI exits non-zero only when `has_failures` is true.
  - WARN remains non-blocking; `SKIP`/`N_A` remain neutral.

Result: compatible with current gate policy (critical FAIL blocks; `SKIP`/`N_A` are non-failing evidence states).

## PR6.1 policy check (`out_of_scope + zero-event => SKIP`)
- `apps/worker/src/validation/config.py`
  - Added explicit bookmaker x competition scope policy with `nbl` out-of-scope list.
- `apps/worker/src/validation/score_calculator.py`
  - Applies policy before coverage FAIL rules:
    - out-of-scope + zero-event => `SKIP`
    - in-scope + zero-event => still `FAIL`
- `apps/worker/tests/test_validation.py`
  - Added score-level and pipeline-level tests validating:
    - out-of-scope zero-event => `SKIP`
    - in-scope zero-event => `FAIL`
    - report counts and `has_failures` remain alert-compatible.

Result: compatible. Reporting/summaries/alerts continue to treat `SKIP` as non-failing while preserving `FAIL` for in-scope broken output.

## PR7 policy check (`out_of_scope => SKIP`, boxing in-scope split)
- `apps/worker/src/validation/config.py`
  - Added explicit boxing in-scope policy:
    - `boxing.in_scope = {ladbrokes, neds, betfair}`
  - Non-listed books are out-of-scope for boxing.
- `apps/worker/src/validation/score_calculator.py`
  - Scope policy now applies regardless of event count:
    - out-of-scope => `SKIP`
    - in-scope behavior unchanged (`FAIL` conditions still enforced)
- `apps/worker/tests/test_validation.py`
  - Added coverage for:
    - out-of-scope non-zero-event => `SKIP`
    - pipeline-level reporting/gate behavior for out-of-scope boxing rows

Result: compatible. Report summaries include `SKIP`, alerts still trigger only on `FAIL`, and gate exit behavior remains deterministic for in-scope failure conditions.
