# ADR-0004: Current-Odds-First Persistence and Cleanup

- Status: Accepted
- Date: 2026-02-10
- Owners: Data Platform

## Context
The matcher needs fresh, query-efficient odds.
Retaining large historical odds volumes increases storage and slows hot-path queries.

## Decision
Persist odds with current-state semantics:
- `odds_snapshots.is_current=true` is matcher truth.
- upsert dedupe key includes `(selection_id, bookmaker_id, timestamp_bucket, scrape_session_id)`.
- stale `is_current=false` odds are cleaned aggressively.
- past events are cleaned with safety guards and buffer.

## Consequences
Benefits:
- fast query path for matcher
- controlled DB growth
- clear operational definition of "current odds"

Tradeoffs:
- limited deep historical replay by default
- cleanup correctness is critical

## Alternatives Considered
1. Keep full historical snapshots long-term:
- rejected for current stage due to cost/performance overhead.

2. Replace-only without snapshot table:
- rejected; loses traceability and short-term diagnostics.

## Follow-ups
- Keep retention and cleanup policies explicit as scale grows.
- Add partitioning strategy when current snapshot volume materially increases.

