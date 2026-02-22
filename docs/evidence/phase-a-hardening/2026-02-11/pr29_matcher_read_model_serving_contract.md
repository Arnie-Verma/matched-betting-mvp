# PR29 Matcher Read-Model Serving Contract

Date: 2026-02-22
Slice: PR-M1b
Status: Implemented

## Scope
1. Add feature-flagged read-model serving mode for `GET /odds/matcher` while keeping runtime path as default.
2. Add deterministic freshness/health fallback from read-model to runtime.
3. Preserve matcher API response schema (no breaking field changes).
4. Keep shadow parity tooling available and emit serving-source telemetry fields.
5. Keep Unibet freeze baseline unchanged.

## Implemented Behavior
1. Serving mode controls:
- `MATCHER_READ_MODEL_SERVING_ENABLED` (default `false`)
- `MATCHER_READ_MODEL_VERSION` (default `matcher_read_model_v1`)
- `MATCHER_READ_MODEL_MAX_AGE_SECONDS` (default `300`)
2. Read-model serving is used only when:
- flag is enabled
- build exists
- build `built_at` is valid and fresh
- read-model rows exist
- request shape is parity-safe for read-model serving
3. Deterministic fallback reason codes:
- `read_model_missing_build`
- `read_model_invalid_built_at`
- `read_model_stale`
- `read_model_no_rows`
- `read_model_query_error`
- `read_model_invalid_payload`
- `read_model_unsupported_*`
4. Matcher observability payload includes:
- `serving_source=runtime|read_model|runtime_fallback`
- `fallback_reason_code`
5. Response headers expose serving provenance:
- `X-Matcher-Serving-Source`
- `X-Matcher-Fallback-Reason` (fallback branch only)

## Reproducible Command Log
```powershell
python -m py_compile apps/api/src/api/routers/odds_matcher.py apps/api/src/api/services/matcher_read_model_service.py apps/api/src/api/scripts/generate_pr29_matcher_read_model_serving_parity.py apps/api/tests/test_matcher_read_model_serving.py
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_matcher_read_model_serving.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_odds_matcher_hot_path.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
$env:PYTHONPATH='apps/api/src'; python -m api.scripts.generate_pr29_matcher_read_model_serving_parity
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "SELECT code, is_active FROM bookmakers WHERE code='unibet';"
```

## Acceptance Mapping
1. API response contract unchanged: PASS.
2. Feature flag cleanly switches serving source: PASS.
3. Freshness fallback deterministic and safe: PASS.
4. Existing matcher regression tests stay green: PASS.
5. Freeze baseline preserved and verified: PASS.
