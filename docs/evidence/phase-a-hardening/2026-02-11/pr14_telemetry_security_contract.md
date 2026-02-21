# PR-S2 Telemetry Security Contract

Date: 2026-02-21  
Slice: PR-S2 (Telemetry Security Hardening)

## Scope
- Tightened operational health endpoint access policy for:
  - `GET /health/scrapers`
  - `GET /health/detailed`
  - `GET /health/telemetry`
- Enforced explicit ops/internal access (no broad authenticated-by-default access).
- Added strict request bounds for telemetry query params:
  - `hours`: `1..24`
  - `limit`: `100..2000`
- Removed raw telemetry event dump fields from default telemetry response:
  - `summary.sample_events`
  - `sample_metric_records`
- Added ADR-0016 with rollback procedure.

## Policy Decision (runtime)
- Internal token path remains allowed via `X-Internal-Health-Token` when `HEALTH_SCRAPERS_INTERNAL_TOKEN` is configured.
- Authenticated access now requires role intersection with:
  - `HEALTH_OPERATIONS_ALLOWED_ROLES`
  - fallback: `HEALTH_SCRAPERS_ALLOWED_ROLES`
  - default: `ops,admin`
- Non-ops authenticated callers receive `403`.

## Reproducible Commands
```powershell
python -m py_compile apps/api/src/api/routers/health.py apps/api/src/api/services/observability_service.py apps/api/tests/test_security_controls.py apps/api/tests/test_telemetry_security.py
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_telemetry_security.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_security_controls.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_health.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_odds_matcher_hot_path.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "select code,is_active from bookmakers where code='unibet';"
```

## Command Output Summary
- `apps/api/tests/test_telemetry_security.py`: `5 passed`
- `apps/api/tests/test_security_controls.py`: `3 passed`
- `apps/api/tests/test_health.py`: `1 passed`
- `apps/api/tests/test_odds_matcher_hot_path.py`: `3 passed`
- `apps/api/tests/test_bookmaker_freeze.py`: `6 passed`
- `apps/api/tests/test_unibet_freeze_integration.py`: `1 passed`
- Freeze checks:
  - `BOOKMAKER_FREEZE_UNIBET=true` in `mb_api`
  - `BOOKMAKER_FREEZE_UNIBET=true` in `mb_worker`
  - `unibet | f` in DB (`is_active=false`)

## Acceptance Mapping
1. Unauthenticated `/health/telemetry` -> covered (`401/403`) in `test_health_telemetry_unauthenticated_denied`.
2. Authenticated non-ops denied -> covered in `test_health_telemetry_denies_non_ops_and_matches_health_endpoints`.
3. Allowed role/internal token -> covered in:
   - `test_health_telemetry_allows_ops_role_and_sanitizes_response`
   - `test_health_telemetry_allows_internal_token`
4. Invalid oversized query params rejected -> covered in `test_health_telemetry_rejects_out_of_range_query_params` (`422`).
5. Sensitive identifiers not exposed in response -> covered via sanitized response assertions (raw sample dump fields absent).
6. `/health/scrapers` + `/health/detailed` policy consistency -> non-ops denied in same shared-policy test.

## Rollback Notes
- See `docs/adr/ADR-0016-health-telemetry-ops-access-and-response-minimization.md`.
- Revert files:
  - `apps/api/src/api/routers/health.py`
  - `apps/api/src/api/services/observability_service.py`
- Re-run:
  - `apps/api/tests/test_security_controls.py`
  - `apps/api/tests/test_telemetry_security.py`
