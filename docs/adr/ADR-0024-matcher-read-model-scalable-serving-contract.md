# ADR-0024: Matcher Read-Model Scalable Serving Contract

- Status: Accepted
- Date: 2026-02-24
- Owners: @api

## Context
ADR-0023 introduced feature-flagged read-model serving with runtime fallback safety.
The serving path still loaded full read-model payload sets and applied in-memory filter/sort/pagination, which is not scalable at 50k+ rows and blocks safe default-on consideration.

## Decision
PR-M1c hardens read-model serving to a query-scalable contract:
1. Read-model request path uses DB-side pagination (`LIMIT/OFFSET`) for page fetch.
2. Read-model request path uses DB-side filtered count for response pagination metadata.
3. Supported read-model shape is explicit:
- `stake=100`
- `bet_type=normal`
- no `sport_codes`
- no `competition_ids`
- no `competition_codes`
- no `search`
- optional `bookmaker_codes` and `min_rating` are SQL-filtered
4. Unsupported shapes deterministically fallback to runtime with explicit reason code.
5. Runtime fallback safety semantics from ADR-0023 remain intact (missing/stale/unhealthy read-model states fail over to runtime).
6. Matcher telemetry adds scalable-serving proof fields:
- `read_model_query_mode`
- `read_model_query_round_trip_signal`
- `read_model_materialized_rows`
- `read_model_total_rows`
7. Read-model serving query path is index-backed for large offsets:
- `idx_matcher_rm_version_pnl_id`
- `idx_matcher_rm_version_bookmaker_pnl_id`

## Consequences
Benefits:
- Removes request-path full-table read-model payload loading.
- Removes request-path in-memory full-dataset pagination on read-model serving path.
- Preserves API response schema while making serving behavior auditable.

Tradeoffs:
- Supported shape remains intentionally narrow until additional parity coverage is proven.
- Additional DB indexes increase write/storage overhead on read-model rows.

Operational impact:
- Rollback remains immediate by setting `MATCHER_READ_MODEL_SERVING_ENABLED=false`.
- If needed, PR-M1c indexes can be reverted by downgrading migration `20260224_matcher_rm_idx`.

## Alternatives Considered
1. Keep full-load serving and rely on larger app workers:
- rejected; does not solve request-path scaling and increases cost/risk.
2. Move directly to keyset-only pagination:
- rejected for this slice; would change contract semantics from current offset pagination.
3. Expand all filters in one slice:
- rejected; high regression risk and outside narrow PR-M1c scope.

## Follow-ups
1. Expand parity-safe supported request shapes incrementally.
2. Define default-on cutover gate using sustained parity + latency + fallback-rate evidence.
3. Consider additional index tuning for `min_rating` heavy workloads if telemetry shows drift.
