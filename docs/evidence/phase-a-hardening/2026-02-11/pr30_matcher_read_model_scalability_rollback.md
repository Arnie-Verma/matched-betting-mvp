# PR-M1c Rollback Runbook

- Date: 2026-02-24
- Slice: PR-M1c

## Immediate Operational Rollback
1. Set `MATCHER_READ_MODEL_SERVING_ENABLED=false`.
2. Restart API process/pod.
3. Verify `GET /odds/matcher` returns header `X-Matcher-Serving-Source: runtime`.

This reverts matcher serving to runtime path only.

## DB Index Rollback (If Migration Applied)
PR-M1c adds migration `20260224_matcher_rm_idx` for read-model serving indexes:
- `idx_matcher_rm_version_pnl_id`
- `idx_matcher_rm_version_bookmaker_pnl_id`

Rollback steps:
1. Run Alembic downgrade one revision:
   - `cd apps/api`
   - `alembic downgrade 20260222_matcher_rm`
2. Verify indexes are removed:
   - Postgres: query `pg_indexes` for `matcher_read_model_rows`.
   - expected: both PR-M1c index names absent.
3. Confirm matcher endpoint still serves via runtime (`MATCHER_READ_MODEL_SERVING_ENABLED=false`).

## Down-Migration Verification Note
- Down migration was authored to drop only PR-M1c indexes and leave read-model tables/data intact.
- Functional rollback validation remains:
  - runtime path healthy
  - no schema regressions outside those two indexes

## Blast Radius Statement
- Rollback affects matcher read-model serving performance path only.
- Functional behavior reverts to runtime matcher computation.
- No lifecycle/freeze policy changes are included.
- No Unibet policy/state changes are included.
