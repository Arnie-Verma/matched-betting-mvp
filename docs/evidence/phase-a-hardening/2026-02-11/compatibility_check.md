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
