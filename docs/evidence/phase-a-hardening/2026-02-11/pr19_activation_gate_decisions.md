# PR-L2 Activation Gate Decisions

## Policy Decisions

1. Promotion gates are enforced at lifecycle transition time in `BookmakerLifecycleService`.
2. Freeze guard remains first-class and unchanged.
3. Gate thresholds are not relaxed; active promotion requires canary threshold-contract match.
4. Denials are deterministic and machine-readable (`reason_code` + `failed_criteria`).

## Recency Window Decisions

- `BOOKMAKER_VALIDATION_EVIDENCE_MAX_AGE_SECONDS` default: `21600` (6h)
- `BOOKMAKER_CANARY_EVIDENCE_MAX_AGE_SECONDS` default: `21600` (6h)

Rationale:
- Prevent stale promotion decisions.
- Keep windows strict enough for safety while practical for local operations.

## Reason Codes Introduced

Validation-gate denials:
- `validation_evidence_missing`
- `validation_evidence_timestamp_missing`
- `validation_evidence_timestamp_invalid`
- `validation_evidence_stale`
- `validation_in_scope_fail_count_missing`
- `validation_in_scope_fail_count_invalid`
- `validation_in_scope_fail_detected`

Canary-gate denials:
- `canary_evidence_missing`
- `canary_evidence_timestamp_missing`
- `canary_evidence_timestamp_invalid`
- `canary_evidence_stale`
- `canary_gate_missing`
- `canary_gate_result_missing`
- `canary_thresholds_missing`
- `canary_threshold_contract_mismatch`
- `canary_gate_failed`

## Operational Notes

1. Transition metadata may include evidence inline or via JSON file path:
   - `validation_evidence` or `validation_evidence_path`
   - `canary_evidence` or `canary_evidence_path`
2. No scheduler/matcher/telemetry threshold semantics were changed in PR-L2.
3. Next hardening step should add canonical evidence registry/storage to reduce operator workflow drift.
