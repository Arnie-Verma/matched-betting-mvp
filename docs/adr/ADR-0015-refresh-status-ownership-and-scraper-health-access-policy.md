# ADR-0015: Refresh Status Ownership + Scraper Health Access Policy

- Status: Accepted
- Date: 2026-02-21
- Owners: @platform

## Context
- `GET /odds/refresh/status` returned job metadata for any authenticated user who knew a `job_id`.
- `/health/scrapers` was publicly readable without authentication.
- These behaviors exposed operational state across users and leaked internal scraper telemetry.

## Decision
1. `GET /odds/refresh/status` enforces access scope:
- allow job owner (`payload.requested_by`)
- allow explicitly shared merged readers (`payload.shared_user_ids`)
- deny all other users with `403`

2. `/health/scrapers` is protected by policy:
- allow authenticated callers
- OR allow internal token access via `X-Internal-Health-Token` when `HEALTH_SCRAPERS_INTERNAL_TOKEN` is configured
- optional role gate when `HEALTH_SCRAPERS_ALLOWED_ROLES` is configured
- unauthenticated/non-internal callers return `401`

## Consequences
- Cross-user job status access is blocked by default.
- Merged refresh semantics remain usable via explicit shared-reader IDs.
- Scraper operational telemetry is no longer publicly exposed.
- Runtime requires auth or internal token distribution for scraper health consumers.

## Rollback Procedure
1. Revert this ADR’s implementation commit.
2. Restore prior behavior in:
- `apps/api/src/api/routers/odds_matcher.py` (remove ownership checks)
- `apps/api/src/api/routers/health.py` (remove access policy dependency)
3. Redeploy API and re-run:
- `apps/api/tests/test_security_controls.py`
- `apps/api/tests/test_health.py`
4. Remove/mark this ADR as superseded if rollback is permanent.

## Alternatives Considered
- Global admin-only gating for both endpoints.
  - Rejected due to merged refresh UX requiring controlled multi-user visibility.
- IP allow-list only for `/health/scrapers`.
  - Rejected as brittle in local/dev and not identity-aware.

## Follow-ups
- Consider migrating refresh-job ACLs to dedicated job metadata schema for stronger typing.
- Add audit logging for denied refresh status access.
