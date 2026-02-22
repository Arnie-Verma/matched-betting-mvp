# PR27 Retention Lock Correctness + Cap-Override Hardening Contract

Date: 2026-02-22
Slice: PR-A2c
Status: Implemented

## Scope
1. Fixed retention lock release to atomic compare-and-delete semantics.
2. Added race-safe lock correctness tests for TTL expiry/reacquire behavior.
3. Removed env/config-based persistent cap-breach bypass behavior for automation runs.
4. Enforced cap-breach override as explicit per-run operator intent only.
5. Preserved existing retention semantics (terminal-only pruning + non-terminal safety invariants).

## Implemented Runtime Behavior
1. Lock release correctness:
- lock release now uses a single atomic compare-and-delete operation (Lua eval in Redis client).
- stale lock owner token cannot delete a newly acquired lock token.
2. Contention behavior:
- if lock acquisition fails, run aborts with `lock_not_acquired` and does not enter cleanup execution path.
3. Cap override behavior:
- guardrail config loaded from env always uses `allow_cap_breach=false`.
- automation execution always derives `allow_cap_breach` from explicit per-run override flag only.
- without explicit override, cap breach aborts with `delete_cap_exceeded`.
- with explicit override, execute path is allowed.

## Reproducible Command Log
```powershell
python -m py_compile apps/api/src/api/services/refresh_acl_retention_automation_service.py apps/api/src/api/services/refresh_acl_retention_service.py apps/api/src/api/scripts/cleanup_refresh_acl_retention.py apps/api/src/api/scripts/run_refresh_acl_retention_automation.py apps/api/src/api/scripts/generate_pr27_retention_lock_guardrail_scenarios.py apps/api/tests/test_refresh_acl_retention_automation.py
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_refresh_acl_retention_automation.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_refresh_acl_retention.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_refresh_acl_durable.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_security_controls.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
$env:PYTHONPATH='apps/api/src'; python -m api.scripts.generate_pr27_retention_lock_guardrail_scenarios
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "SELECT code, is_active FROM bookmakers WHERE code='unibet';"
```

## Acceptance Mapping
1. Lock release race-safe under expiry/reacquire: PASS.
2. Contended runs do not overlap cleanup execution: PASS.
3. Cap guard cannot be bypassed by env-only configuration: PASS.
4. Cap override requires explicit per-run flag: PASS.
5. Existing retention safety invariants preserved: PASS.
6. Freeze baseline unchanged and verified: PASS.
