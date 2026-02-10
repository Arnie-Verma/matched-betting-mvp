# Architecture

## Purpose
This document is the implementation-level architecture reference for the current system.
It explains how refresh, scraping, persistence, matching, validation, and plan gating work today.

Use this with:
- `BOOKMAKER_OPERATING_SYSTEM.md` for operating guardrails and lifecycle gates
- `SCRAPER_HARDENING_PLAN.md` for current hardening execution
- `docs/adr/*` for decision rationale and tradeoffs

## System Goal
Build an Outmatched-style AU matched betting platform that:
- aggregates bookmaker back odds + exchange lay odds
- normalizes events/selections across bookmakers
- returns matched-betting opportunities quickly
- isolates bookmaker failures so one break does not take down refresh

## Runtime Topology
Local Docker services (`infra/dev/docker-compose.yml`):
- `mb_web` (Next.js): UI + server proxy routes
- `mb_api` (FastAPI): matcher/read APIs, refresh enqueue APIs, metadata, health
- `mb_worker`: Redis queue consumer + scrape orchestration
- `mb_db` (Postgres): odds/event domain data
- `mb_redis`: queue, job state, breaker state, cache timestamps

Key code:
- API entry: `apps/api/src/api/main.py`
- Worker entry: `apps/worker/src/jobs/refresh_worker.py`

## Core Architectural Decisions (Current)
1. Refresh is asynchronous:
- API enqueues jobs and returns immediately with `job_id`.
- UI polls job status until complete.

2. Scrapers are platform adapters, selected dynamically from DB config:
- `bookmakers.scraping_config.scraper_class` -> class in `SCRAPER_CLASSES`.
- New bookmaker on existing platform is mostly config + validation.

3. Bookmaker execution is isolated:
- Per-bookmaker scrape tasks
- Per-bookmaker circuit breaker state in Redis
- Partial completion is allowed

4. Data model is current-state first:
- `odds_snapshots.is_current=true` is matcher truth
- stale/non-current odds are cleaned aggressively

5. Matching is normalization-driven:
- events grouped by normalized event + normalized competition key
- selection matching prioritizes `selection_key` (`home/away/draw`)

## End-to-End Refresh Flow
### A) Background refresh on page load
1. `OddsMatcherClient` calls `POST /api/proxy/odds/refresh`.
2. Web proxy forwards to API `POST /odds/refresh`.
3. API checks:
- auth and user plan access
- global cache TTL
- in-progress refresh marker
- per-user rate limit
4. API enqueues refresh job in Redis and returns `job_id` (or cache-hit response).
5. UI polls `GET /api/proxy/odds/refresh/status?job_id=...`.
6. Worker consumes queue and runs scrape orchestration.
7. UI fetches matcher data after job success.

### B) User-triggered manual refresh
Same backend path as above, but UI shows explicit status banner and refresh button spinner.

Key code:
- `apps/web/src/components/odds-matcher/OddsMatcherClient.tsx`
- `apps/web/src/app/api/proxy/odds/refresh/route.ts`
- `apps/web/src/app/api/proxy/odds/refresh/status/route.ts`
- `apps/api/src/api/routers/odds_matcher.py`
- `apps/api/src/api/services/refresh_queue.py`
- `apps/worker/src/jobs/refresh_worker.py`

## Queue + Worker Model
Redis-backed queue semantics:
- enqueue: `RPUSH odds_refresh_jobs`
- worker pop: `BRPOP odds_refresh_jobs`
- job state stored at `odds_refresh_job:{job_id}`
- merge behavior: if queue already has pending work, API can return existing pending job
- retry/backoff + DLQ support in worker

Worker orchestration behavior:
- calls `trigger_scrape(sport="all")`
- applies per-bookmaker concurrency cap bookkeeping in Redis
- updates global and per-bookmaker refresh timestamps

Key code:
- `apps/api/src/api/services/refresh_queue.py`
- `apps/worker/src/jobs/refresh_worker.py`

## Scraping Architecture
Scraper contract:
- all scrapers implement `BaseScraper` interface
- outputs `ScrapeResult -> ScrapedEvent[] -> ScrapedOdds[]`

Orchestration:
- load active bookmakers from DB
- dynamically instantiate scraper by `scraper_class`
- run all active bookmakers in parallel
- each bookmaker can run multi-sport scrape (batch-controlled)

Resilience controls:
- circuit breaker per bookmaker (`closed/open/half-open`)
- timeout per bookmaker scrape
- result status supports `SUCCESS`, `PARTIAL`, `FAILED`

Key code:
- `apps/worker/src/scrapers/base.py`
- `apps/worker/src/jobs/scrape_service.py`
- `apps/worker/src/scrapers/entain_scraper.py`
- `apps/worker/src/scrapers/punterstech_scraper.py`
- `apps/worker/src/scrapers/kindred_scraper.py`

## Persistence + Data Lifecycle
Persistence path:
1. scrape result enters `save_scrape_result_to_db`
2. event/market/selection upsert-ish resolution
3. odds upsert into `odds_snapshots` with dedupe key:
- `(selection_id, bookmaker_id, timestamp_bucket, scrape_session_id)`
4. previous current odds for affected event/bookmaker are cleared
5. inserted odds become `is_current=true`

Data hygiene:
- frequent cleanup removes non-current odds
- past events cleanup exists for retention control

Key code:
- `apps/worker/src/jobs/save_odds.py`
- `apps/worker/src/jobs/cleanup_service.py`
- models: `apps/api/src/api/models/odds.py`

## Matcher Read Path
Matcher API (`GET /odds/matcher`) does:
1. plan-gated bookmaker allow-list
2. fetch upcoming scheduled events (next 14 days)
3. group duplicate events by normalized event + normalized competition
4. gather eligible markets and selections
5. collect back odds from allowed bookmakers and lay odds from Betfair
6. compute matched-bet outputs using matching engine
7. one opportunity per bookmaker/selection pairing
8. sort by `pnl_percentage`, paginate, return

Additional behavior:
- market preference ranking to align market types per sport
- ETag/Last-Modified headers for client revalidation

Key code:
- `apps/api/src/api/routers/odds_matcher.py`
- `apps/api/src/api/services/matching_engine.py`
- `apps/api/src/api/services/normalization_service.py`

## Normalization Strategy
Centralized normalization is in one service:
- competition normalization
- team normalization
- event normalization
- selection normalization and fuzzy support

This is foundational for cross-bookmaker matching and validation consistency.

Key code:
- `apps/api/src/api/services/normalization_service.py`

## Access Control + Plans
Plan enforcement is server-side:
- feature checks via `SubscriptionService`
- allowed bookmaker list derived by plan
- metadata endpoints return plan-allowed bookmakers

Key code:
- `apps/api/src/api/services/subscription_service.py`
- `apps/api/src/api/routers/metadata.py`
- `apps/api/src/api/routers/odds_matcher.py`

## Validation + Health
Validation:
- optional post-scrape validation path in worker
- dedicated validation pipeline and CLI
- supports structural/probability/golden checks

Health:
- `/health/scrapers` reports freshness, odds counts, breaker state
- `/health/database` and `/health/detailed` for runtime checks

Key code:
- `apps/worker/src/validation/*`
- `apps/worker/src/scripts/validate_scrapers.py`
- `apps/api/src/api/routers/health.py`

## Configuration Model
Important runtime knobs:
- `SCRAPER_BATCH_SIZE`
- `BOOKMAKER_TIMEOUT_SECONDS`
- `BOOKMAKER_BREAKER_THRESHOLD`
- `BOOKMAKER_BREAKER_COOLDOWN_SECONDS`
- `BOOKMAKER_CONCURRENCY_CAP`
- `ODDS_CACHE_TTL_FAST_SECONDS`
- `ODDS_REFRESH_PER_USER_SECONDS`
- `VALIDATION_ENABLED`

Notes:
- scraper code defaults `SCRAPER_BATCH_SIZE` to `1` if env is absent
- environment files may override this for local constraints/perf testing

## Current Known Constraints
1. Lifecycle and activation gates are documented but not fully code-enforced yet.
2. Validation thresholds still need ongoing calibration across competitions/platforms.
3. Read path still does substantial in-request grouping/processing at API layer.
4. Some plan/bookmaker lists are hardcoded and need long-term config centralization.

These are tracked in:
- `BOOKMAKER_OPERATING_SYSTEM.md`
- `SCRAPER_HARDENING_PLAN.md`

## Related ADRs
See `docs/adr/README.md` for index.

