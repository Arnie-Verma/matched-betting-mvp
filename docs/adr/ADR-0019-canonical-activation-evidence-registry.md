# ADR-0019: Canonical Activation Evidence Registry

- Status: Accepted
- Date: 2026-02-22
- Owners: @platform

## Context
PR-L2 enforced activation-gate checks but still allowed ad-hoc evidence input via inline/path metadata during promotion requests. That created a trust/audit gap because promotion decisions could depend on unaudited request payloads.

## Decision
Introduce a canonical persisted evidence registry and require lifecycle promotions to consume registry record IDs.

1. Add `bookmaker_activation_evidence` table for canonical activation-gate inputs.
2. Register evidence via admin/internal endpoint from artifact paths:
- `POST /admin/bookmakers/lifecycle-evidence/register`
3. Persist auditable provenance:
- `artifact_path`
- `artifact_sha256`
- `created_by`, `created_by_email`, `created_at`
4. Persist normalized enforcement fields:
- validation: `validation_in_scope_fail_count`, timestamps
- canary: `canary_gate_pass`, `canary_gate_thresholds`, failed criteria, timestamps
5. Promotion checks now require canonical IDs:
- `validation_evidence_id` for `validation_passed -> canary_active`
- `canary_evidence_id` for `canary_active -> active`
6. Enforce evidence-bookmaker binding:
- evidence record bookmaker must equal transition target bookmaker.
7. Keep existing recency windows, threshold contract, and freeze semantics unchanged.

## Consequences
Benefits:
- Removes unaudited ad-hoc evidence path from promotion control.
- Improves determinism and traceability of promotion decisions.
- Enables evidence lineage via hash/path metadata.

Tradeoffs:
- Adds explicit evidence registration workflow before promotions.
- Adds schema/service complexity.

## Alternatives Considered
1. Keep inline/path evidence as fallback:
- Rejected: fails auditability and trust requirements.

2. Store evidence references only in transition metadata:
- Rejected: weaker source-of-truth guarantees and poor discoverability.

## Rollback
If registry rollout causes operational friction:
1. Pause promotions to live states.
2. Keep registration endpoint and DB records intact.
3. Adjust tooling/process around registration.
4. Only if necessary, revert lifecycle service to previous evidence mode via code rollback.

## Follow-ups
1. Add read/list APIs for evidence records and richer querying.
2. Add retention policy and periodic cleanup for old evidence artifacts.
3. Add UI/admin tooling for registry-backed promotion workflows.
