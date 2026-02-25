# Architecture Decision Records

This folder stores key architecture decisions and their rationale.

## When to add/update an ADR
Create or update an ADR when any of the following changes:
- refresh/scrape orchestration design
- data retention or persistence semantics
- platform adapter model
- concurrency/isolation policy
- normalization/matching strategy
- rollout/activation guardrail design

## ADR Index
- `ADR-0001-async-refresh-queue.md`
- `ADR-0002-dynamic-scraper-registry.md`
- `ADR-0003-local-first-concurrency-policy.md`
- `ADR-0004-current-odds-first-persistence.md`
- `ADR-0005-centralized-normalization-for-matching.md`
- `ADR-0006-bookmaker-isolation-with-circuit-breakers.md`
- `ADR-0007-phase-a-unibet-freeze-enforcement.md`
- `ADR-0008-validation-eligibility-window-semantics.md`
- `ADR-0009-priority-normalization-alias-hardening.md`
- `ADR-0010-market-hygiene-selection-key-enforcement.md`
- `ADR-0011-validation-stabilization-threshold-calibration.md`
- `ADR-0012-bookmaker-competition-coverage-scope-policy.md`
- `ADR-0013-pr7-epl-boxing-fail-remediation.md`
- `ADR-0014-canary-gate-reliability-thresholds.md`
- `ADR-0015-refresh-status-ownership-and-scraper-health-access-policy.md`
- `ADR-0016-health-telemetry-ops-access-and-response-minimization.md`
- `ADR-0017-bookmaker-lifecycle-state-enforcement.md`
- `ADR-0018-activation-gate-evidence-enforcement.md`
- `ADR-0019-canonical-activation-evidence-registry.md`
- `ADR-0020-rollout-control-plane-selection-enforcement.md`
- `ADR-0021-durable-refresh-acl-audit-persistence.md`
- `ADR-0022-matcher-read-model-foundation.md`
- `ADR-0023-matcher-read-model-serving-with-freshness-fallback.md`
- `ADR-0024-matcher-read-model-scalable-serving-contract.md`

## ADR Template
Use this structure:

```md
# ADR-xxxx: Title

- Status: Accepted | Superseded | Proposed
- Date: YYYY-MM-DD
- Owners: @team_or_person

## Context
Problem and constraints.

## Decision
What was decided.

## Consequences
Benefits, tradeoffs, operational impact.

## Alternatives Considered
What was considered and why not chosen.

## Follow-ups
Implementation notes, validation steps, or re-evaluation triggers.
```
