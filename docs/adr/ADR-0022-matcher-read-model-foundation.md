# ADR-0022: Matcher Read-Model Foundation (Non-Serving)

- Status: Accepted
- Date: 2026-02-22
- Owners: @api

## Context
Matcher hot-path query fan-out was reduced in PR-R3, but `/odds/matcher` still performs response assembly directly from source tables on each request.
For sustained 100+ bookmaker scale, the system needs a dedicated matcher read-model with explicit freshness metadata and deterministic build operations.

The first step must not change API response contracts or serving behavior.

## Decision
Introduce a non-serving matcher read-model foundation:
1. Add dedicated persistence tables:
- `matcher_read_model_builds`
- `matcher_read_model_rows`
2. Persist freshness/build metadata:
- `built_at`
- source window (`source_window_start`, `source_window_end`)
- `read_model_version`
- builder run metadata and bounded execution settings
3. Add idempotent builder service:
- deterministic row key per matcher opportunity
- version-scoped upsert behavior
- stale-row pruning for same version after rebuild
4. Enforce bounded builder controls:
- `event_limit`
- `event_batch_size`
- `row_batch_size`
5. Add optional shadow parity mode:
- compare runtime matcher output vs read-model payload rows
- non-serving only (no API contract cutover in this slice)

## Consequences
Benefits:
- Read-model persistence and freshness are now queryable.
- Builder reruns are idempotent and bounded.
- Parity checks provide measurable correctness before serving cutover.

Tradeoffs:
- Added schema and builder complexity before serving is switched.
- Build process currently duplicates runtime matcher computation path.

Operational impact:
- New build command available:
  - `python -m api.scripts.build_matcher_read_model --shadow-parity`
- Read-model refresh cadence and serving cutover policy are follow-up decisions.

## Alternatives Considered
1. Immediate serving cutover in same slice:
- rejected; higher risk and violates single-slice non-breaking scope.
2. Materialized SQL view only:
- rejected; weaker control over idempotent bounded build semantics and metadata.
3. Keep runtime-only matcher path:
- rejected; does not establish scalable read-model foundation.

## Rollback
If issues occur:
1. Stop running read-model builder scripts.
2. Keep `/odds/matcher` on runtime path (already primary in this slice).
3. Revert migration and model/service additions if necessary.
4. Re-run matcher regression and freeze tests after rollback.

## Follow-ups
1. Add scheduled builder execution and freshness SLO alarms.
2. Evaluate read-model serving cutover behind feature flag.
3. Add retention policy for read-model build/version history if row volume grows.

