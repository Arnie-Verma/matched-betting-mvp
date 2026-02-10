# ADR-0006: Bookmaker Isolation with Circuit Breakers

- Status: Accepted
- Date: 2026-02-10
- Owners: Runtime Platform

## Context
At multi-bookmaker scale, individual bookmaker failures are expected.
A single failing bookmaker must not block system refresh completion.

## Decision
Apply per-bookmaker isolation:
- independent scrape execution per bookmaker
- per-bookmaker breaker state in Redis (`closed`, `open`, `half-open`)
- failure counts trip breaker; cooldown controls retries
- partial refresh results are allowed and returned

## Consequences
Benefits:
- one bookmaker outage does not cascade across system
- faster diagnosis and recovery targeting
- better user experience via partial freshness

Tradeoffs:
- more runtime state to manage
- requires good health telemetry and clear failure thresholds

## Alternatives Considered
1. Global breaker for all bookmakers:
- rejected; blast radius too large.

2. No breaker:
- rejected; repeated failures would waste resources and increase latency.

## Follow-ups
- tune thresholds per platform class (easy vs anti-bot).
- enforce lifecycle/activation gates so unstable books do not promote to active.

