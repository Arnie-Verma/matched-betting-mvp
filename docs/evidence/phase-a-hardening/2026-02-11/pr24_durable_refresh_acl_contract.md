# PR24 Durable Refresh ACL Contract

Date: 2026-02-22
Slice: PR-A1 (Durable Refresh ACL + Audit Logging)
Status: Implemented

## Scope
1. Add durable DB-backed refresh job ownership/ACL/audit models.
2. Enforce `/odds/refresh/status` ACL from durable records when present.
3. Keep fallback path only for pre-migration Redis-only jobs.
4. Persist job create/share/unshare/status-access audit decisions.
5. Provide active/recent backfill strategy for legacy jobs.

## Implementation Summary
1. Added persistent models and migration:
- `refresh_jobs`
- `refresh_job_acl_entries`
- `refresh_job_audit_events`
2. Added `RefreshJobAclService`:
- durable job create
- share/unshare updates
- status access decision + reason code + audit row
- legacy payload backfill
- durable runtime status updates
3. Updated `POST /odds/refresh` and `GET /odds/refresh/status` to use durable ACL authority.
4. Added worker best-effort durable status sync (non-fatal) and env kill switch `REFRESH_JOB_DURABLE_SYNC_ENABLED`.
5. Added backfill utility:
- `python -m api.scripts.backfill_refresh_jobs_acl --hours 24`

## Backward Compatibility Contract
1. If durable row exists for a `job_id`, durable ACL is source of truth.
2. If durable row is missing, Redis payload ACL path remains temporarily allowed.
3. Legacy Redis jobs are opportunistically backfilled when status is queried or merged.

## Reproducible Command Log
```bash
python -m py_compile apps/api/src/api/services/refresh_job_acl_service.py apps/api/src/api/routers/odds_matcher.py apps/worker/src/jobs/refresh_worker.py apps/api/src/api/models/odds.py apps/api/src/api/scripts/backfill_refresh_jobs_acl.py apps/api/tests/test_refresh_acl_durable.py
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_refresh_acl_durable.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_security_controls.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
pytest apps/worker/tests/test_scrape_scheduler.py -q
pytest apps/worker/tests/test_validation.py -q
pytest apps/worker/tests/test_entain_scraper.py -q
pytest apps/worker/tests/test_punterstech_scraper.py -q
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "SELECT code, is_active FROM bookmakers WHERE code='unibet';"
```

## Acceptance Mapping
1. Cross-user access impossible via durable ACL checks: PASS.
- Covered by `test_durable_acl_enforces_owner_and_shared_and_writes_access_audit` and `test_durable_acl_precedence_blocks_redis_payload_bypass`.
2. Owner + explicitly shared users can access status: PASS.
- Covered by durable and legacy-backfill scenarios.
3. ACL decisions are queryable/auditable from DB: PASS.
- Covered by assertions on `refresh_job_audit_events` rows.
4. Redis expiry/restart does not lose ACL authority for durable jobs: PASS.
- Covered by `test_durable_acl_survives_redis_expiry_for_backfilled_jobs`.
5. Regression tests cover allow/deny/backward compatibility: PASS.

## Freeze Verification
1. `mb_api`: `BOOKMAKER_FREEZE_UNIBET=true`
2. `mb_worker`: `BOOKMAKER_FREEZE_UNIBET=true`
3. DB: `unibet | is_active = false`

## Rollback Notes
1. Route-level rollback: restore legacy payload ACL-only checks in `/odds/refresh/status`.
2. Disable worker durable sync if needed: `REFRESH_JOB_DURABLE_SYNC_ENABLED=0`.
3. Keep durable tables for forensics; no destructive rollback required during incident response.
