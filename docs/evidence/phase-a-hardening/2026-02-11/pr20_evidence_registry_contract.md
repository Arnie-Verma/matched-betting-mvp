# PR-L3 Canonical Activation Evidence Registry Contract

## Objective

Require lifecycle promotions to consume canonical persisted evidence records, not ad-hoc inline/path payloads.

## Registry Contract

Canonical table:
- `bookmaker_activation_evidence`

Required persisted fields:
- `evidence_type` (`validation|canary`)
- `bookmaker_code`
- `generated_at` / `ended_at`
- normalized enforcement fields:
  - validation: `validation_in_scope_fail_count`
  - canary: `canary_gate_pass`, `canary_gate_thresholds`, `canary_gate_failed_criteria`
- artifact provenance:
  - `artifact_path`
  - `artifact_sha256`
- audit metadata:
  - `created_by`
  - `created_by_email`
  - `created_at`

Registration surface:
- `POST /admin/bookmakers/lifecycle-evidence/register`

Promotion inputs (enforced):
- `validation_passed -> canary_active` requires `validation_evidence_id`
- `canary_active -> active` requires `canary_evidence_id`

Quality guard:
- lifecycle promotions no longer accept raw inline/path evidence as the primary source.

## Enforcement Checks

1. Required canonical evidence record ID must exist for gated transitions.
2. Evidence record bookmaker must match target bookmaker.
3. Existing recency checks remain in force:
   - `BOOKMAKER_VALIDATION_EVIDENCE_MAX_AGE_SECONDS`
   - `BOOKMAKER_CANARY_EVIDENCE_MAX_AGE_SECONDS`
4. Existing canary threshold contract remains unchanged for active promotion.

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

- `apps/api/tests/test_bookmaker_lifecycle.py`: `16 passed`
- `apps/api/tests/test_bookmaker_freeze.py`: `6 passed`
- `apps/api/tests/test_unibet_freeze_integration.py`: `1 passed`
- Freeze verification:
  - `mb_api`: `BOOKMAKER_FREEZE_UNIBET=true`
  - `mb_worker`: `BOOKMAKER_FREEZE_UNIBET=true`
  - DB row: `unibet | f`
