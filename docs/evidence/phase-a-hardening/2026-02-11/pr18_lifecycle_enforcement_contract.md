# PR-L1 Lifecycle State Enforcement Contract

## Scope

PR-L1 implements lifecycle state persistence and transition guards in code, with audited metadata and deterministic admin/internal control surface.

Out of scope in this slice:
- activation-gate evidence coupling to promotion decisions
- canary/ramp cohort control-plane changes

## Implemented Contract

### 1) Persistent lifecycle model

- `bookmakers` now persists lifecycle fields:
  - `lifecycle_state`
  - `lifecycle_state_updated_at`
  - `lifecycle_last_transition_at`
  - `lifecycle_last_transition_by`
  - `lifecycle_last_transition_reason`
- `bookmaker_lifecycle_transitions` persists transition audit history:
  - `bookmaker_id`, `from_state`, `to_state`
  - `transition_reason`, `transition_metadata`
  - `transitioned_by`, `transitioned_by_email`, `transition_source`, `created_at`

### 2) Guarded transition policy

- Allowed states:
  - `backlog`
  - `discovery_complete`
  - `adapter_ready`
  - `config_ready`
  - `validation_passed`
  - `canary_active`
  - `active`
  - `degraded`
  - `disabled`
- Invalid transitions are rejected with explicit reason codes.
- Frozen bookmakers are blocked from transitions into live runtime states (`canary_active`, `active`, `degraded`).

### 3) Minimal control surface

- Endpoint:
  - `POST /admin/bookmakers/{bookmaker_code}/lifecycle`
- Access:
  - authenticated role in `BOOKMAKER_LIFECYCLE_ALLOWED_ROLES` (default `admin,ops`)
  - or internal token header `X-Internal-Admin-Token` matching `BOOKMAKER_LIFECYCLE_INTERNAL_TOKEN`

### 4) Unsafe raw promotion mitigation

- Model synchronization guard keeps `is_active` aligned to lifecycle state and freeze policy.
- Direct raw `is_active=true` flips without a live lifecycle state are normalized back to safe state behavior.

## Reproducible Commands

```bash
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "select code, is_active from bookmakers where code='\''unibet'\'';"
```

```bash
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_bookmaker_lifecycle.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
```

## Observed Outputs

- Freeze verification:
  - `BOOKMAKER_FREEZE_UNIBET=true` in `mb_api`
  - `BOOKMAKER_FREEZE_UNIBET=true` in `mb_worker`
  - DB row: `unibet | f`

- Test verification:
  - `apps/api/tests/test_bookmaker_lifecycle.py`: `5 passed`
  - `apps/api/tests/test_bookmaker_freeze.py`: `6 passed`
  - `apps/api/tests/test_unibet_freeze_integration.py`: `1 passed`

## Files Introduced by Contract

- `apps/api/alembic/versions/20260222_bookmaker_lifecycle_enforcement.py`
- `apps/api/src/api/services/bookmaker_lifecycle_service.py`
- `apps/api/src/api/routers/bookmaker_lifecycle.py`
- `apps/api/src/api/models/odds.py`
- `apps/api/tests/test_bookmaker_lifecycle.py`
