# ADR-0001: Async Refresh Queue via Redis

- Status: Accepted
- Date: 2026-02-10
- Owners: Platform

## Context
Odds refresh can take longer than a typical API request window.
Blocking the request would cause timeouts and poor UI responsiveness.
Multiple users can request refresh simultaneously.

## Decision
Use Redis-backed async queue semantics:
- API enqueues refresh jobs and returns immediately with `job_id`.
- UI polls job status endpoint.
- Worker consumes queue and executes scrape.
- Merge new requests into existing pending work where possible.

## Consequences
Benefits:
- non-blocking user refresh UX
- one shared refresh run can satisfy many users
- predictable failure/retry handling

Tradeoffs:
- eventual consistency (user waits for job completion)
- added queue/job state complexity
- requires healthy worker process

## Alternatives Considered
1. Synchronous refresh in API request:
- rejected due to timeout risk and poor UX.

2. Full Celery/RQ adoption now:
- deferred to keep operational complexity low in current stage.

## Follow-ups
- Formalize queue metrics and alerts (queue depth, job age, DLQ growth).
- Keep merge rules and in-progress pointers aligned with frontend polling behavior.

