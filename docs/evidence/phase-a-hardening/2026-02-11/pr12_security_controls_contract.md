# PR-S1 Security Controls Contract

Date: 2026-02-21  
Slice: PR-S1 (Security Controls)

## Scope
- Enforced ownership/ACL authorization on `GET /odds/refresh/status`.
- Protected `/health/scrapers` behind auth/internal access policy.
- Added regression tests for unauthorized/authorized access paths.
- Added ADR with rollback procedure.

## Security Policy
### `GET /odds/refresh/status`
- Allow if caller is:
  - job owner (`payload.requested_by`), or
  - explicitly shared merged reader (`payload.shared_user_ids`)
- Deny all other authenticated users with `403`.

### `GET /health/scrapers`
- Allow authenticated users.
- Allow internal token callers when `HEALTH_SCRAPERS_INTERNAL_TOKEN` is configured and request sends `X-Internal-Health-Token`.
- Optional role gate when `HEALTH_SCRAPERS_ALLOWED_ROLES` is configured.
- Unauthenticated/no-internal-token callers return `401`.

## ADR
- Added: `docs/adr/ADR-0015-refresh-status-ownership-and-scraper-health-access-policy.md`
- Indexed in: `docs/adr/README.md`

## Reproducible Commands
```powershell
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_security_controls.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_health.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; python apps/api/src/api/scripts/generate_pr12_security_controls_results.py
```

## Command Output Summary
- `apps/api/tests/test_security_controls.py`: `3 passed`
- `apps/api/tests/test_health.py`: `1 passed`
- `apps/api/tests/test_unibet_freeze_integration.py`: `1 passed`
- `apps/api/tests/test_bookmaker_freeze.py`: `6 passed`
- Results JSON generated successfully.

## Evidence JSON
- `docs/evidence/phase-a-hardening/2026-02-11/pr12_security_controls_results.json`
- Confirms:
  - cross-user refresh status request => `403`
  - owner refresh status request => `200`
  - unauthenticated `/health/scrapers` => `401/403` (observed `401`)
  - authenticated `/health/scrapers` => `200`
