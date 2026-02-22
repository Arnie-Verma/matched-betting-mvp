# PR-L2 Activation Gate Contract

## Objective

Prevent promotion to live lifecycle states unless machine-verifiable evidence is present, fresh, and passing.

## Enforced Transition Gates

### `validation_passed -> canary_active`

Required evidence:
- `validation_evidence` (inline object) or `validation_evidence_path` (JSON file path)

Required checks:
1. Evidence exists.
2. Evidence timestamp is present and valid (`generated_at|completed_at|ended_at|timestamp`).
3. Evidence recency <= `BOOKMAKER_VALIDATION_EVIDENCE_MAX_AGE_SECONDS` (default `21600`).
4. `in_scope_fail_count == 0` (accepted fields: `in_scope_fail_count`, `in_scope_fail_cycle_count`, `validation_gate_metrics.in_scope_fail_cycle_count`, `summary.in_scope_fail_count`).

### `canary_active -> active`

Required evidence:
- `canary_evidence` (inline object) or `canary_evidence_path` (JSON file path)

Required checks:
1. Evidence exists.
2. Evidence timestamp is present and valid (`ended_at|generated_at|completed_at|timestamp`).
3. Evidence recency <= `BOOKMAKER_CANARY_EVIDENCE_MAX_AGE_SECONDS` (default `21600`).
4. `gate.pass == true`.
5. `gate.thresholds` must match existing gate contract:
   - `min_cycles=10`
   - `min_duration_seconds=1800`
   - `requires_in_scope_fail_zero=true`
   - `min_scrape_success_rate=0.75`
   - `max_open_breaker_cycle_count=0`
   - `max_scrape_p95_seconds=360.0`

## Denial Contract

Denials return:
- `reason_code`
- `message`
- `from_state`
- `to_state`
- `failed_criteria` (machine-readable list)

Examples:
- `validation_evidence_missing`
- `validation_evidence_stale`
- `validation_in_scope_fail_detected`
- `canary_evidence_missing`
- `canary_evidence_stale`
- `canary_gate_failed`
- `canary_threshold_contract_mismatch`

## Reproducible Commands

```bash
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_bookmaker_lifecycle.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
```

```bash
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "select code, is_active from bookmakers where code='\''unibet'\'';"
```

## Observed Results

- Lifecycle tests: `13 passed`
- Freeze tests: `6 passed`
- Unibet freeze integration: `1 passed`
- Runtime freeze verification:
  - `mb_api`: `BOOKMAKER_FREEZE_UNIBET=true`
  - `mb_worker`: `BOOKMAKER_FREEZE_UNIBET=true`
  - DB: `unibet | f`
