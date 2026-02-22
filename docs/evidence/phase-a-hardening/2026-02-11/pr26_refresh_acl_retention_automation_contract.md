# PR26 Refresh ACL/Audit Retention Automation Contract

Date: 2026-02-22
Slice: PR-A2b (Retention Automation + Guardrails)
Status: Implemented

## Scope
1. Added automated/scheduled execution path for refresh ACL retention cleanup.
2. Added single-run lock guard for retention automation.
3. Added hard abort guardrails before execute-mode deletes:
- abort on non-terminal delete risk
- abort on max-delete cap breach unless explicit override flag
4. Added structured retention run summary and observability outcome signals.
5. Preserved terminal-only cleanup semantics from PR-A2a.

## Implemented Behavior
1. Automation service:
- `execute_refresh_acl_retention_automation(...)`
- `run_refresh_acl_retention_schedule(...)`
2. Single-run lock:
- default lock key: `maintenance:refresh_acl_retention:lock`
- default lock TTL: `900` seconds
- aborted run reason when lock unavailable: `lock_not_acquired`
3. Guardrails:
- hard abort reason: `non_terminal_delete_risk` when `non_terminal_job_delete_candidates > 0`
- hard abort reason: `delete_cap_exceeded` when candidate totals exceed configured caps and cap override is not enabled
4. Structured run summary includes:
- run status (`success|aborted|failure`)
- reason code
- dry-run/execute mode
- candidate/deleted counts
- guardrail decisions
- lock acquisition state
- run duration
5. Observability signal emitted per run:
- metric: `refresh_acl_retention_run`
- action type: `refresh_acl_retention_success|refresh_acl_retention_aborted|refresh_acl_retention_failure`

## Automation Commands
```bash
# one-shot guarded cleanup (dry-run default)
python -m api.scripts.cleanup_refresh_acl_retention --audit-retention-days 30 --terminal-job-retention-days 14

# scheduled automation loop
python -m api.scripts.run_refresh_acl_retention_automation --max-runs 2 --interval-seconds 0 --audit-retention-days 30 --terminal-job-retention-days 14

# execute mode with explicit cap override (only when intentionally approved)
python -m api.scripts.run_refresh_acl_retention_automation --execute --allow-cap-breach --max-runs 1
```

## Reproducible Command Log
```powershell
python -m py_compile apps/api/src/api/services/refresh_acl_retention_service.py apps/api/src/api/services/refresh_acl_retention_automation_service.py apps/api/src/api/scripts/cleanup_refresh_acl_retention.py apps/api/src/api/scripts/run_refresh_acl_retention_automation.py apps/api/src/api/scripts/generate_pr26_refresh_acl_retention_automation_runs.py apps/api/tests/test_refresh_acl_retention.py apps/api/tests/test_refresh_acl_retention_automation.py
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_refresh_acl_retention_automation.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_refresh_acl_retention.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_refresh_acl_durable.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_security_controls.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
$env:PYTHONPATH='apps/api/src'; python -m api.scripts.generate_pr26_refresh_acl_retention_automation_runs
$env:PYTHONPATH='apps/api/src'; python -m api.scripts.cleanup_refresh_acl_retention --audit-retention-days 30 --terminal-job-retention-days 14
$env:PYTHONPATH='apps/api/src'; python -m api.scripts.run_refresh_acl_retention_automation --max-runs 2 --interval-seconds 0 --audit-retention-days 30 --terminal-job-retention-days 14
$env:PYTHONPATH='apps/api/src'; python -m api.scripts.run_refresh_acl_retention_automation --execute --max-runs 1 --interval-seconds 0 --audit-retention-days 30 --terminal-job-retention-days 14
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "SELECT code, is_active FROM bookmakers WHERE code='unibet';"
```

Lock contention proof is sourced from:
1. `apps/api/tests/test_refresh_acl_retention_automation.py` (`test_automation_lock_guard_aborts_when_lock_not_acquired`)
2. `docs/evidence/phase-a-hardening/2026-02-11/pr26_refresh_acl_retention_automation_runs.json` (`lock_not_acquired` scenario).

## Acceptance Mapping
1. Automated dry-run/execute paths produce structured output: PASS.
2. Single-run lock prevents concurrent execution: PASS (`lock_not_acquired`).
3. Non-terminal risk guard aborts with no deletes: PASS.
4. Delete-cap guard aborts with no deletes unless explicit override: PASS.
5. Execute success path preserves non-terminal ACL authority: PASS.
6. Test coverage includes scheduler path, lock behavior, guard aborts, cap aborts, and success path: PASS.

## Freeze Verification
1. `mb_api`: `BOOKMAKER_FREEZE_UNIBET=true`
2. `mb_worker`: `BOOKMAKER_FREEZE_UNIBET=true`
3. DB: `unibet | is_active = false`
