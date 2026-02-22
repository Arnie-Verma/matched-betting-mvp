# ADR-0018: Activation Gate Evidence Enforcement

- Status: Accepted
- Date: 2026-02-22
- Owners: @platform

## Context
PR-L1 added lifecycle persistence and transition guards, but promotion to live states was not yet coupled to machine-verifiable gate evidence. For production safety at 100+ bookmakers, transitions into live runtime states must be blocked when evidence is missing, stale, or failing.

## Decision
Bind lifecycle promotions to deterministic evidence checks:

1. `validation_passed -> canary_active` requires validation evidence that is:
- present
- fresh within `BOOKMAKER_VALIDATION_EVIDENCE_MAX_AGE_SECONDS` (default 21600s)
- includes `in_scope_fail_count == 0`

2. `canary_active -> active` requires canary evidence that is:
- present
- fresh within `BOOKMAKER_CANARY_EVIDENCE_MAX_AGE_SECONDS` (default 21600s)
- includes `gate.pass == true`
- includes gate thresholds matching existing canary contract:
  - `min_cycles=10`
  - `min_duration_seconds=1800`
  - `requires_in_scope_fail_zero=true`
  - `min_scrape_success_rate=0.75`
  - `max_open_breaker_cycle_count=0`
  - `max_scrape_p95_seconds=360.0`

3. Denials are explicit and machine-readable:
- reason codes (for example `validation_evidence_missing`, `canary_gate_failed`)
- structured `failed_criteria` list in service and API responses.

4. Existing freeze guard remains unchanged:
- frozen bookmakers cannot transition to live runtime states.

## Consequences
Benefits:
- Promotions are deterministic and auditable.
- Unsafe promotions without fresh passing evidence are blocked by code.
- On-call/debugging improves via reason-coded denials and failed criteria payloads.

Tradeoffs:
- Transition requests now require evidence payload/path discipline.
- Operational tooling must consistently provide fresh evidence references.

## Alternatives Considered
1. Role-based promotion without evidence checks:
- Rejected: insufficient safety and auditability.

2. Evidence checks in docs/runbooks only:
- Rejected: non-deterministic and bypassable.

3. Relax threshold/recency requirements:
- Rejected for this slice; policy unchanged to preserve gate rigor.

## Rollback
If this enforcement is too strict/noisy:
1. Temporarily stop live-state transitions operationally.
2. Adjust evidence generation workflow (not thresholds) to provide required payloads.
3. As last resort, revert service-level gate checks and re-evaluate policy with new ADR.

## Follow-ups
1. Add canonical evidence registry/storage instead of ad-hoc path/inline references.
2. Add canary/ramp cohort controls and rollout policy automation (PR-L3 scope).
