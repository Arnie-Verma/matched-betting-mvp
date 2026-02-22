# PR25 Refresh ACL/Audit Retention Contract

Date: 2026-02-22
Slice: PR-A2a (Refresh ACL/Audit Retention Policy)
Status: Implemented

## Scope
1. Add durable retention policy for `refresh_job_audit_events` and terminal `refresh_jobs`.
2. Preserve non-terminal jobs and active ACL authority for valid jobs.
3. Add dry-run-first cleanup utility with execution summary.
4. Add safety-guarded tests for dry-run, execution, and invariants.

## Runtime Policy
1. `REFRESH_AUDIT_RETENTION_DAYS` (default `30`):
- delete audit rows older than cutoff only when their parent job is terminal.
2. `REFRESH_TERMINAL_JOB_RETENTION_DAYS` (default `14`):
- delete terminal jobs older than cutoff.
3. `REFRESH_TERMINAL_JOB_STATUSES`:
- configurable terminal status set (default: `success,failed,cancelled,canceled,expired`).
4. Safety guards:
- no delete candidates for non-terminal jobs.
- no audit-row deletion for non-terminal jobs.
- dry-run is default; `--execute` required to delete.

## Cleanup Utility
`python -m api.scripts.cleanup_refresh_acl_retention`

Examples:
```bash
# Dry-run (default)
python -m api.scripts.cleanup_refresh_acl_retention --audit-retention-days 30 --terminal-job-retention-days 14

# Execute
python -m api.scripts.cleanup_refresh_acl_retention --execute --audit-retention-days 30 --terminal-job-retention-days 14
```

## Reproducible Command Log
```bash
python -m py_compile apps/api/src/api/services/refresh_acl_retention_service.py apps/api/src/api/scripts/cleanup_refresh_acl_retention.py apps/api/tests/test_refresh_acl_retention.py
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_refresh_acl_retention.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_refresh_acl_durable.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_security_controls.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
$env:PYTHONPATH='apps/api/src'; python -m api.scripts.generate_pr25_refresh_acl_retention_before_after
$env:PYTHONPATH='apps/api/src'; python -m api.scripts.cleanup_refresh_acl_retention --audit-retention-days 30 --terminal-job-retention-days 14
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "SELECT code, is_active FROM bookmakers WHERE code='unibet';"
```

## Acceptance Mapping
1. Old audit rows beyond threshold removed in execution mode: PASS.
- Verified by `test_refresh_acl_retention_execute_deletes_only_old_terminal_data` and `pr25_refresh_acl_retention_before_after.json` (`execute.deleted.aged_terminal_audit_rows=1`).
2. Dry-run reports candidate counts and performs no deletes: PASS.
- Verified by `test_refresh_acl_retention_dry_run_reports_candidates_without_deletes` and `before == after` in dry-run summary.
3. Terminal jobs older than threshold handled; non-terminal jobs remain: PASS.
- Verified by execution test (`deleted.terminal_jobs=1`, running job remains).
4. Active ACL authority for valid jobs remains intact: PASS.
- Verified by `test_refresh_acl_retention_preserves_active_acl_authority_for_valid_jobs` (shared allow / outsider deny after cleanup).
5. Safety invariants test-covered: PASS.
- `safety.non_terminal_job_delete_candidates=0` asserted in summaries/tests.

## Freeze Verification
1. `mb_api`: `BOOKMAKER_FREEZE_UNIBET=true`
2. `mb_worker`: `BOOKMAKER_FREEZE_UNIBET=true`
3. DB: `unibet | is_active = false`

## Rollback
1. Stop scheduled cleanup execution (`--execute` jobs).
2. Keep utility in dry-run mode while validating thresholds.
3. Increase retention windows temporarily via env vars if over-pruning is observed.
