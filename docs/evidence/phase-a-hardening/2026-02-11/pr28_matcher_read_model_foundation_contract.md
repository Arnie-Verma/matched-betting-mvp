# PR28 Matcher Read-Model Foundation Contract

Date: 2026-02-22
Slice: PR-M1a
Status: Implemented

## Scope
1. Added dedicated matcher read-model persistence foundation.
2. Added idempotent builder path with bounded execution controls.
3. Kept `/odds/matcher` runtime serving path as primary.
4. Added optional non-serving shadow parity checks.
5. Added build/parity tests and reproducible evidence artifacts.

## Implemented Behavior
1. New persistence tables:
- `matcher_read_model_builds`
- `matcher_read_model_rows`
2. Freshness metadata persisted:
- `built_at`
- `source_window_start`
- `source_window_end`
- `read_model_version`
3. Idempotent build semantics:
- deterministic row-key upsert within version namespace
- stale-row pruning for same version after successful rebuild
- reruns update existing rows instead of duplicating rows
4. Bounded controls:
- `event_limit`
- `event_batch_size`
- `row_batch_size`
5. Shadow parity mode:
- compares runtime matcher payloads with read-model payload rows
- parity check is non-serving and does not change API response path

## Reproducible Command Log
```powershell
python -m py_compile apps/api/src/api/services/matcher_read_model_service.py apps/api/src/api/scripts/build_matcher_read_model.py apps/api/src/api/scripts/generate_pr28_matcher_read_model_foundation_parity.py apps/api/tests/test_matcher_read_model_foundation.py apps/api/src/api/models/odds.py apps/api/alembic/versions/20260222_matcher_read_model_foundation.py
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_matcher_read_model_foundation.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_odds_matcher_hot_path.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
docker exec mb_api alembic upgrade head
$env:PYTHONPATH='apps/api/src'; python -m api.scripts.build_matcher_read_model --read-model-version pr28_live_probe_v1 --event-limit 50 --event-batch-size 10 --row-batch-size 20 --shadow-parity --shadow-parity-limit 50
$env:PYTHONPATH='apps/api/src'; python -m api.scripts.generate_pr28_matcher_read_model_foundation_parity
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "SELECT code, is_active FROM bookmakers WHERE code='unibet';"
```

## Acceptance Mapping
1. Builder idempotent with no duplicate/corrupt rows on rerun: PASS.
2. Freshness metadata persisted and queryable: PASS.
3. Shadow parity proven on representative fixtures with no response-field drift: PASS.
4. Bounded build controls enforced (`event_limit`, `event_batch_size`, `row_batch_size`): PASS.
5. Tests cover idempotency, freshness, parity, bounded execution: PASS.
6. Unibet freeze baseline unchanged and verified: PASS.
