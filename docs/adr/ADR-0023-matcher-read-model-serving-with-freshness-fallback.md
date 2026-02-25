# ADR-0023: Matcher Read-Model Serving Behind Feature Flag With Freshness Fallback

- Status: Accepted
- Date: 2026-02-22
- Owners: @api

## Context
PR-M1a introduced matcher read-model persistence and non-serving parity checks.
Serving from read-model rows is required for scalable matcher latency, but direct cutover would risk request-path regressions if data is stale, missing, or incompatible with request filters.

## Decision
Add an explicit feature-flagged serving path for `GET /odds/matcher`:
1. Runtime path remains default (`MATCHER_READ_MODEL_SERVING_ENABLED=false`).
2. Read-model path is enabled only when:
- feature flag is on
- latest build exists for configured version
- build freshness is within `MATCHER_READ_MODEL_MAX_AGE_SECONDS`
- read-model rows exist
- request shape is currently supported for parity-safe serving
3. If read-model is missing/stale/unhealthy/unsupported, endpoint falls back to runtime path with deterministic reason code:
- `read_model_missing_build`
- `read_model_invalid_built_at`
- `read_model_stale`
- `read_model_no_rows`
- `read_model_query_error`
- `read_model_invalid_payload`
- `read_model_unsupported_*`
4. Matcher telemetry includes serving provenance:
- `serving_source=runtime|read_model|runtime_fallback`
- `fallback_reason_code`

## Consequences
Benefits:
- Enables incremental, reversible read-model serving adoption.
- Prevents stale/unhealthy read-model data from breaking matcher responses.
- Preserves response schema contract while exposing deterministic fallback reasons for operations.

Tradeoffs:
- Added branching complexity in matcher request path.
- Initial read-model serving supports a conservative subset of request shapes; unsupported shapes use runtime fallback.

Operational impact:
- Serving behavior controlled by env vars:
  - `MATCHER_READ_MODEL_SERVING_ENABLED`
  - `MATCHER_READ_MODEL_VERSION`
  - `MATCHER_READ_MODEL_MAX_AGE_SECONDS`

## Alternatives Considered
1. Immediate hard cutover to read-model:
- rejected due higher regression risk and no runtime safety fallback.
2. Keep runtime-only matcher path:
- rejected because it blocks the read-model serving rollout step needed for scale.
3. Background-only read-model parity with no serving:
- rejected because it delays production validation of serving behavior.

## Rollback
If read-model serving is noisy or incorrect:
1. Set `MATCHER_READ_MODEL_SERVING_ENABLED=false`.
2. Keep running read-model builder/parity checks in non-serving mode.
3. Investigate fallback reason distribution and parity deltas before re-enabling.

## Follow-ups
1. Expand read-model serving support to additional request filters once parity-safe.
2. Define promotion criteria for default-on read-model serving.
3. Add read-model freshness/usage alerts using `serving_source` and fallback reason telemetry.

## Follow-up Status (PR-M1c, 2026-02-24)
Completed in PR-M1c:
1. Request-path read-model serving moved to SQL-scaled count + paged fetch (no full payload load in request path).
2. Unsupported request shapes now deterministically runtime-fallback with explicit reason codes.
3. Serving telemetry now includes read-model query-mode/materialization/query-round-trip fields.

Still open after PR-M1c:
1. Serving remains feature-flagged (`MATCHER_READ_MODEL_SERVING_ENABLED=false` default).
2. Default-on cutover criteria and broader filter-shape support are pending.
