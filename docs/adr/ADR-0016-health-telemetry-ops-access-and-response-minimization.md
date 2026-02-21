# ADR-0016: Health Telemetry Ops Access And Response Minimization

- Status: Accepted
- Date: 2026-02-21
- Owners: @platform

## Context
- `/health/telemetry` inherited broad authenticated access semantics, which is too permissive for operational telemetry.
- Telemetry reports could include raw `sample_events` that may expose sensitive security payload fields.
- Telemetry read parameters were loosely bounded, increasing expensive-read abuse risk.
- Access semantics across `/health/scrapers`, `/health/detailed`, and `/health/telemetry` needed a consistent non-bypassable policy.

## Decision
1. Use one shared operational-health access dependency for:
- `/health/scrapers`
- `/health/detailed`
- `/health/telemetry`

2. Tighten access policy:
- allow internal token path (`X-Internal-Health-Token`) when configured
- allow authenticated users only when roles intersect ops-allowed roles
- deny broad authenticated-by-default access
- default allowed roles: `ops,admin` (configurable via `HEALTH_OPERATIONS_ALLOWED_ROLES`, fallback `HEALTH_SCRAPERS_ALLOWED_ROLES`)

3. Harden telemetry query bounds:
- `hours`: `1..24`
- `limit`: `100..2000`
- out-of-range values are rejected with validation errors

4. Minimize telemetry response:
- remove raw `sample_events` and `sample_metric_records` from default `/health/telemetry` response
- keep aggregated summary and threshold results only

## Consequences
- Operational health telemetry is no longer visible to generic authenticated users.
- Read-amplification risk is reduced through strict query bounds.
- Security payload identifiers are not exposed via default telemetry response path.
- Existing health endpoints now share one policy path, reducing bypass risk.

## Rollback Procedure
1. Revert PR-S2 commit.
2. Restore previous access behavior in:
- `apps/api/src/api/routers/health.py`
- `apps/api/src/api/services/observability_service.py`
3. Re-run:
- `apps/api/tests/test_security_controls.py`
- `apps/api/tests/test_telemetry_security.py`
4. If rollback remains, mark this ADR superseded.

## Alternatives Considered
- Keep broad auth and hide only sample events.
  - Rejected: still overexposes operational telemetry.
- Telemetry endpoint token-only.
  - Rejected: too rigid for role-based on-call workflows.
- Keep param clamping only.
  - Rejected: explicit rejection is easier to reason about for abuse control.

