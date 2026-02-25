# PR-M1c Matcher Read-Model Scalability Contract

- Date: 2026-02-24
- Slice: PR-M1c
- Scope: read-model serving request-path scalability hardening only

## Contract Goals
1. No request-path full-table payload load for read-model serving.
2. No request-path in-memory full-dataset sort/paginate for read-model serving.
3. SQL pushdown for supported read-model shape:
   - DB-side count
   - DB-side `ORDER BY ... LIMIT/OFFSET` page fetch
4. Unsupported shape must runtime-fallback with deterministic reason code.
5. `/odds/matcher` response schema and headers remain contract-compatible.

## Supported Read-Model Request Shape (PR-M1c)
- `stake=100`
- `bet_type=normal`
- `sport_codes` unset
- `competition_ids` unset
- `competition_codes` unset
- `search` unset
- optional `bookmaker_codes` and optional `min_rating` are SQL-filtered
- pagination is always SQL `LIMIT/OFFSET` pushdown

## Deterministic Fallback Reason Codes
- `read_model_missing_build`
- `read_model_invalid_built_at`
- `read_model_stale`
- `read_model_no_rows`
- `read_model_query_error`
- `read_model_invalid_payload`
- `read_model_unsupported_stake`
- `read_model_unsupported_bet_type`
- `read_model_unsupported_sport_codes_filter`
- `read_model_unsupported_competition_ids_filter`
- `read_model_unsupported_competition_codes_filter`
- `read_model_unsupported_search_filter`

## Observability Fields (Matcher Request Event)
- `serving_source`
- `fallback_reason_code`
- `read_model_query_mode`
- `read_model_query_round_trip_signal`
- `read_model_materialized_rows`
- `read_model_total_rows`

## Enforcement Notes
- `read_model_materialized_rows <= limit` for healthy served requests.
- Healthy served supported-shape requests are bounded to <= 3 read-model DB round trips:
  - build/freshness lookup
  - filtered count
  - page fetch
