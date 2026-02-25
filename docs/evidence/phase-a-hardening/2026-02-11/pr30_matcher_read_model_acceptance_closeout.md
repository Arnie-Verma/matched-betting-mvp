# PR-M1cA Acceptance Closeout

- Date: 2026-02-24
- Slice: PR-M1cA (PR-M1c acceptance closeout evidence)
- Scope: evidence-only closeout (Postgres scalability proof + live freeze verification + reference accuracy corrections)

## Postgres Scalability Proof Summary
- Dataset: 50,000 read-model rows (`read_model_version=pr30_postgres_benchmark_v1`)
- Request shape: supported read-model shape
- Traffic sample: `limit=30`, offsets `0/300/3000`, 35 requests each (105 total)
- Overall latency p95: 129.529 ms
- Fallback rate: 0.0%
- Read-model query-round-trip p95: 3.0
- Materialized rows <= limit across sampled requests: true

## Enforce-Now Threshold Closeout
1. SQL LIMIT/OFFSET pushdown: PASS
2. Request-path materialization <= limit: PASS
3. Read-model query round-trip signal <= 3: PASS
4. Supported-shape fallback-rate = 0%: PASS
5. p95 latency <= 400ms: PASS

## Observe-Only Tracking
- p95 <= 250ms target: observed 129.529 ms
- offset=3000 max latency <= 150ms target (track-only): observed 151.403 ms
- Serving source ratio trend: {"read_model": 105}

## Runtime Freeze Verification
- See `pr30_matcher_read_model_freeze_runtime_verification.md`.
- Verified live runtime values: API=true, worker=true, DB unibet.is_active=false.

## Accuracy Corrections Applied
1. ADR index path reference corrected/confirmed as: `docs/adr/README.md`.
2. Read-model serving index name reference corrected/confirmed as: `idx_matcher_rm_version_bookmaker_pnl_id`.

## Rollback Statement
- This slice is evidence/closeout-only and introduces no matcher behavior changes.
- If any accidental behavior change is detected, rollback is revert of the PR-M1cA closeout commit.

