# ADR-0020: Rollout Control Plane Selection Enforcement

- Status: Accepted
- Date: 2026-02-22
- Owners: @platform

## Context

Lifecycle and activation gates were enforced, but worker runnable selection still depended primarily on active DB rows and freeze checks.
For 100+ bookmakers, runtime control needs deterministic policy surfaces that support:
- bookmaker-level and platform-level kill switches
- canary cohort scoping by sport/competition/bookmaker
- auditable admin/internal control APIs
- immediate rollback behavior without code changes

## Decision

Introduce a rollout control plane baseline with persisted policy and deterministic selection:

1. Add persistent policy tables:
- `platform_rollout_policies`
- `bookmaker_rollout_policies`

2. Add policy schema:
- `rollout_mode`: `full | canary | disabled`
- `kill_switch_enabled`: boolean
- canary cohorts:
  - `sport_cohort`
  - `competition_cohort`
  - `bookmaker_cohort`
- audit metadata (`updated_by`, `updated_by_email`, `updated_at`)

3. Enforce worker runnable selection through `RolloutControlService`:
- evaluate lifecycle eligibility states
- evaluate freeze policy
- evaluate platform policy + kill switch
- evaluate bookmaker policy + kill switch
- emit deterministic exclusion reasons

4. Add admin/internal endpoints:
- set/get bookmaker policy
- set/get platform policy
- set/get bookmaker/platform kill switches
- rollout status summary endpoint for runnable/excluded decisions

5. Ensure refresh worker passes runtime context (`sport`, `competition`, bookmaker subset) into selection and scrape execution to prevent bypass.

## Consequences

Benefits:
- deterministic rollback path (flip kill switch or disable mode)
- explicit, auditable rollout policy controls
- policy-driven canary cohort limiting
- no implicit bypass through generic active-row fanout

Tradeoffs:
- additional policy management complexity
- two-level policy composition (platform + bookmaker) requires clear operator discipline
- selection now depends on context quality (`sport`/`competition`) for canary cohort gates

## Rollback Procedure

If policy is too strict/noisy:
1. Set affected platform/bookmaker `rollout_mode` to `full`.
2. Set `kill_switch_enabled=false`.
3. Clear cohort arrays (`sport_cohort`, `competition_cohort`, `bookmaker_cohort`).
4. Confirm via `GET /admin/rollout/status` that expected bookmakers are runnable.

If the entire feature must be reverted:
1. Revert to previous application commit.
2. Optionally keep policy tables in DB (non-breaking) or apply migration downgrade if required by environment policy.

## Alternatives Considered

1. Keep rollout controls in environment variables only.
- Rejected: hard to audit and insufficient granularity for bookmaker-level control.

2. Encode rollout controls in `bookmakers.scraping_config`.
- Rejected: weak separation of concerns and poor policy discoverability.

3. Implement only platform-level kill switch.
- Rejected: insufficient control for targeted incident rollback.

## Follow-ups

1. Add policy change audit event stream and dashboarding.
2. Add rollout policy history table for immutable change-log.
3. Add cohort-aware UI/operator tooling.
