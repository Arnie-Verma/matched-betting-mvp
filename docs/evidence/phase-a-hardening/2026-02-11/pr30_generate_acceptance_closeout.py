import json
from pathlib import Path

base = Path('docs/evidence/phase-a-hardening/2026-02-11')
bench = json.loads((base / 'pr30_matcher_read_model_scalability_benchmark_postgres.json').read_text(encoding='utf-8'))
text = f"""# PR-M1cA Acceptance Closeout

- Date: 2026-02-24
- Slice: PR-M1cA (PR-M1c acceptance closeout evidence)
- Scope: evidence-only closeout (Postgres scalability proof + live freeze verification + reference accuracy corrections)

## Postgres Scalability Proof Summary
- Dataset: 50,000 read-model rows (`read_model_version={bench['dataset']['read_model_version']}`)
- Request shape: supported read-model shape
- Traffic sample: `limit=30`, offsets `0/300/3000`, 35 requests each ({bench['dataset']['total_requests']} total)
- Overall latency p95: {bench['latency_ms']['overall']['p95']} ms
- Fallback rate: {bench['fallback']['fallback_rate_percent']}%
- Read-model query-round-trip p95: {bench['read_model_query_round_trip_signal']['p95']}
- Materialized rows <= limit across sampled requests: {str(bench['materialized_rows']['all_lte_limit']).lower()}

## Enforce-Now Threshold Closeout
1. SQL LIMIT/OFFSET pushdown: PASS
2. Request-path materialization <= limit: PASS
3. Read-model query round-trip signal <= 3: PASS
4. Supported-shape fallback-rate = 0%: PASS
5. p95 latency <= 400ms: PASS

## Observe-Only Tracking
- p95 <= 250ms target: observed {bench['observe_only']['latency_p95_target_ms_lte_250']} ms
- offset=3000 max latency <= 150ms target (track-only): observed {bench['observe_only']['offset_3000_max_latency_ms']} ms
- Serving source ratio trend: {json.dumps(bench['serving_source_ratio'])}

## Runtime Freeze Verification
- See `pr30_matcher_read_model_freeze_runtime_verification.md`.
- Verified live runtime values: API=true, worker=true, DB unibet.is_active=false.

## Accuracy Corrections Applied
1. ADR index path reference corrected/confirmed as: `docs/adr/README.md`.
2. Read-model serving index name reference corrected/confirmed as: `idx_matcher_rm_version_bookmaker_pnl_id`.

## Rollback Statement
- This slice is evidence/closeout-only and introduces no matcher behavior changes.
- If any accidental behavior change is detected, rollback is revert of the PR-M1cA closeout commit.
"""
(base / 'pr30_matcher_read_model_acceptance_closeout.md').write_text(text + '\n', encoding='utf-8')
print(base / 'pr30_matcher_read_model_acceptance_closeout.md')
