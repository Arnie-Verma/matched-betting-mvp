# ADR-0017: Bookmaker Lifecycle State Enforcement

- Status: Accepted
- Date: 2026-02-22
- Owners: @platform

## Context
Lifecycle and promotion behavior was partially doc-driven. For safe scaling to 100+ bookmakers, lifecycle transitions must be persisted, validated, and auditable in runtime code. Without enforcement, an unsafe state jump (for example direct promotion) can bypass intended rollout discipline.

## Decision
Implement lifecycle enforcement in API persistence and service layers:

1. Persist lifecycle state on each bookmaker:
- `bookmakers.lifecycle_state`
- `bookmakers.lifecycle_state_updated_at`
- `bookmakers.lifecycle_last_transition_at`
- `bookmakers.lifecycle_last_transition_by`
- `bookmakers.lifecycle_last_transition_reason`

2. Persist transition history:
- new table `bookmaker_lifecycle_transitions`
- records `from_state`, `to_state`, `transition_reason`, metadata, actor, source, timestamp

3. Enforce allowed transitions via service:
- `BookmakerLifecycleService.transition_bookmaker_state(...)`
- allowed states:
  - `backlog`
  - `discovery_complete`
  - `adapter_ready`
  - `config_ready`
  - `validation_passed`
  - `canary_active`
  - `active`
  - `degraded`
  - `disabled`
- invalid transitions are rejected with explicit reason codes.

4. Enforce freeze compatibility:
- frozen bookmakers (for Phase A, Unibet) cannot transition into live runtime states (`canary_active`, `active`, `degraded`).

5. Add guarded control surface:
- `POST /admin/bookmakers/{bookmaker_code}/lifecycle`
- allowed for `admin/ops` roles or internal token path.

6. Keep runtime safety aligned:
- model-level synchronization keeps `is_active` consistent with lifecycle state so raw state flips do not become an unsafe promotion path.

## Consequences
Benefits:
- Deterministic lifecycle transitions with explicit audit trail.
- Stronger production safety: no arbitrary jump to live states.
- Better on-call/debugging posture with actor + reason metadata.

Tradeoffs:
- Additional schema and operational complexity.
- Promotion policy is still two-stage: lifecycle transition guards now enforced, but full gate-evidence blocking remains a follow-up.

## Alternatives Considered
1. Keep lifecycle doc-only:
- Rejected: non-deterministic and not auditable enough for scale.

2. Enforce only through endpoint role checks without persistence model:
- Rejected: lacks durable transition history and state integrity.

3. Full gate-enforcement coupling in same slice:
- Deferred to a follow-up slice to keep PR-L1 scope focused and low-risk.

## Rollback
If this policy causes operational issues:
1. Disable transition endpoint exposure in deployment routing or auth policy.
2. Revert service usage to read-only while retaining state/history data.
3. Revert migration in non-production environments with Alembic downgrade.
4. If production rollback is required, keep schema in place and pause writes rather than dropping history.

## Follow-ups
1. Couple `active` promotion to canary/validation gate evidence checks (PR-L2 scope).
2. Add canary/ramp cohort controls (PR-L3 scope).
3. Add lifecycle transition dashboarding on top of persisted history.
