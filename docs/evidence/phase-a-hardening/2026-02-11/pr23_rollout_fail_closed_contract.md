# PR-C2A Rollout Fail-Closed Selection Contract

## Objective

Enforce fail-closed behavior in rollout selection when DB/policy source is unavailable.

Required behavior:
- no static fallback bookmaker selection
- empty runnable set
- deterministic reason code: `selection_source_unavailable`
- blocked-selection observability event emission
- worker refresh-job result includes clear blocked reason

## Implemented Behavior

1. `ScrapeService.get_active_bookmakers_from_db(...)`
- removed static fallback return path
- on DB/policy source failure:
  - returns `[]`
  - sets selection status:
    - `source_available=false`
    - `blocked=true`
    - `reason_code=selection_source_unavailable`
  - emits observability event:
    - `category=scheduler`
    - `metric_name=selection_blocked`
    - `action_type=selection_source_unavailable`

2. `ScrapeService.scrape_all_active_bookmakers(...)`
- when runnable set is empty:
  - returns `success=false`
  - includes `selection_status` with reason code/message
  - returns error message containing deterministic reason code

3. `refresh_worker._process_job(...)`
- when active runnable set is empty due blocked selection:
  - does not call scrape trigger
  - marks job failed with message:
    - `Refresh blocked: selection_source_unavailable`
  - persists structured `result.selection_status`

## Reproducible Commands

```bash
python -m py_compile apps/worker/src/jobs/scrape_service.py apps/worker/src/jobs/refresh_worker.py apps/worker/tests/test_scrape_scheduler.py apps/api/tests/test_unibet_freeze_integration.py
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/worker/tests/test_scrape_scheduler.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_rollout_control.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
```

```bash
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "select code, is_active from bookmakers where code='unibet';"
```

## Acceptance Mapping

1. DB failure cannot result in scraping static fallback books.
- `test_db_unavailable_selection_fails_closed_without_static_fallback`

2. Worker job result clearly reports blocked selection reason.
- `test_refresh_worker_reports_blocked_selection_reason_when_empty_runnable_set`

3. Regression tests pass for fail-closed behavior and rollout authority.
- `apps/worker/tests/test_scrape_scheduler.py`
- `apps/api/tests/test_rollout_control.py`

4. Freeze baseline verification:
- `mb_api`: `BOOKMAKER_FREEZE_UNIBET=true`
- `mb_worker`: `BOOKMAKER_FREEZE_UNIBET=true`
- DB: `unibet | f`
