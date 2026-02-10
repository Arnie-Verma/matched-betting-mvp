# ADR-0003: Local-First Concurrency Policy (Batch-Controlled)

- Status: Accepted
- Date: 2026-02-10
- Owners: Platform

## Context
Local Docker resources are constrained during development.
Production-like scrape parallelism can overwhelm local environments and create noisy failures.

## Decision
Use environment-driven concurrency controls:
- scraper sport batching controlled by `SCRAPER_BATCH_SIZE`
- worker bookmaker concurrency controlled by `BOOKMAKER_CONCURRENCY_CAP`
- per-bookmaker timeout and breaker settings via env
- conservative local profile by default; scale up via env/profile, not code forks
- local default policy: `SCRAPER_BATCH_SIZE=1` unless intentionally overridden for capacity testing

## Consequences
Benefits:
- stable local test loops
- same code path across local/staging/production
- explicit control over resource/latency tradeoffs

Tradeoffs:
- local latency can be higher than production targets
- requires profile discipline and clear documentation

## Alternatives Considered
1. Fixed high concurrency in code:
- rejected due to local instability and brittle test behavior.

2. Different code paths for local vs production:
- rejected to avoid drift and hidden bugs.

## Follow-ups
- Keep profile defaults documented in architecture docs.
- Add canary evidence so local results are interpreted with correct profile context.
