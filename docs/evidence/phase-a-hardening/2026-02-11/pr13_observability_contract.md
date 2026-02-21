# PR-O1 Observability Contract

Date: 2026-02-21  
Slice: PR-O1 (Observability Foundation)

## Scope
- Added durable observability sink (Redis stream) with explicit schema version `observability.v1`.
- Emitted scheduler, scrape reliability, matcher performance, and security access-decision telemetry.
- Added threshold evaluation contract with configurable defaults and explicit pass/fail reasons.
- Added secured telemetry report endpoint: `GET /health/telemetry`.

## Telemetry Schema (v1)
Stable event envelope fields:
- `schema_version`
- `recorded_at`
- `category`
- `metric_name`
- `source`
- `endpoint` (when applicable)
- `action_type`
- `bookmaker_code` (when applicable)
- `platform_code` (when applicable)
- `payload` (JSON object)

Primary categories and metric names:
- `scheduler` -> `scrape_scheduler_cycle`
- `scrape_reliability` -> `scrape_bookmaker_result`, `scrape_reliability_cycle`, `breaker_transition`
- `matcher_performance` -> `matcher_request`
- `security` -> `access_decision`

## Threshold Policy (default env-backed values)
- `scrape_success_rate_min = 0.75`
- `scrape_p95_seconds_max = 360`
- `open_breaker_cycle_count_max = 0`
- `matcher_p95_ms_max = 400`
- `acl_denied_rate_max = 0.10` (report-only by default: `OBS_ENFORCE_ACL_DENIED_RATE=false`)

## Runtime Overhead Notes
- Emission is one Redis `XADD` per event with bounded stream length (`OBSERVABILITY_STREAM_MAXLEN`).
- Matcher `query_round_trip_signal` is derived from existing query stages and does not add DB queries.
- Emit path is best-effort; failures are logged and do not block request/scrape execution.

## Reproducible Commands
```powershell
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/worker/tests/test_scrape_scheduler.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_observability_thresholds.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_odds_matcher_hot_path.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_security_controls.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/worker/tests/test_validation.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
$env:PYTHONPATH='apps/api/src'; python apps/api/src/api/scripts/generate_pr13_observability_artifacts.py
docker compose -f infra/dev/docker-compose.yml up -d
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "select code,is_active from bookmakers where code='unibet';"
```

## Command Output Summary
- `apps/worker/tests/test_scrape_scheduler.py`: `5 passed`
- `apps/api/tests/test_observability_thresholds.py`: `6 passed`
- `apps/api/tests/test_odds_matcher_hot_path.py`: `3 passed`
- `apps/api/tests/test_security_controls.py`: `3 passed`
- `apps/worker/tests/test_validation.py`: `62 passed`
- `apps/api/tests/test_bookmaker_freeze.py`: `6 passed`
- `apps/api/tests/test_unibet_freeze_integration.py`: `1 passed`
- artifact generator wrote:
  - `pr13_observability_metrics.json`
  - `pr13_observability_threshold_eval.json`
- runtime freeze verification:
  - `BOOKMAKER_FREEZE_UNIBET=true` in `mb_api`
  - `BOOKMAKER_FREEZE_UNIBET=true` in `mb_worker`
  - `unibet | f` in DB (`is_active=false`)

## Evidence Files
- `docs/evidence/phase-a-hardening/2026-02-11/pr13_observability_metrics.json`
  - telemetry schema, sample records, 24h-equivalent trend summary, overhead note.
- `docs/evidence/phase-a-hardening/2026-02-11/pr13_observability_threshold_eval.json`
  - thresholds used and explicit baseline-pass / stressed-fail evaluations.
