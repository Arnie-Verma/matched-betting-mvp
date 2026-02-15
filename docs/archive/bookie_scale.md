# Bookie Scale Plan

## Objective
Build an Outmatched-style matcher that can scale to 100+ bookmakers and 1,000+ concurrent users while keeping:
1. Fast user experience.
2. Strong failure isolation per bookmaker.
3. Fresh, low-bloat odds data.
4. Clear operational visibility when any bookmaker breaks.

## Current Baseline (From Audit)
1. Queue-driven refresh exists (`/odds/refresh` + worker queue) and is directionally correct.
2. Bookmaker health and breaker concepts exist (good foundation for isolation).
3. Validation framework exists and is integrated (good for safe scaling).
4. Data cleanup and stale-odds controls already exist (good for freshness).
5. Main scale risks today are:
   - Scraper parallelism defaults are conservative (`SCRAPER_BATCH_SIZE=1`).
   - Matching endpoint does heavy in-memory/N+1 work.
   - Dynamic scraper constructor inconsistency can become an outage risk as more bookies are added.

## Target Product Performance
1. Full refresh (core non-proxy books): P95 <= 12s.
2. Filter change from already-fetched data: P95 <= 2s.
3. Anti-bot/proxy books (for example TAB): P95 <= 25s with explicit UI notice.
4. Partial results always available while slower books continue in background.

## Environment Profiles (Important)
1. `SCRAPER_BATCH_SIZE=1` is a valid **local Docker safety profile** to avoid resource contention.
2. Production should use a separate tuned profile (higher batch/concurrency limits, per-platform caps).
3. Treat concurrency as an environment config concern, not an architecture limitation.
4. Keep profile files explicit:
   - local/dev: stability first
   - staging: production-like with lower caps
   - production: latency SLO tuned with monitoring and rollback thresholds

## Non-Negotiable Guardrails
1. **Bookmaker Isolation**
   - Every bookmaker runs as an independent unit of work with its own timeout, retries, circuit breaker state, and metrics.
   - One bookmaker failure must not block refresh completion for others.
2. **Platform Separation**
   - Implement platform adapters (Entain, Kindred/Kambi, Punterstech, BetMakers, etc.) and map bookmakers to adapters via config.
   - Bookmaker-specific logic is limited to config and edge-case transforms.
3. **Strict Scraper Contract**
   - All scrapers/adapters expose one canonical interface and one canonical output schema.
   - Constructor signatures and runtime hooks must be consistent across all scraper classes.
4. **Freshness Over History**
   - Keep only current odds plus short retention windows.
   - Do not build long historical storage in primary OLTP tables.
5. **Fast Read Path**
   - User-facing matcher reads from pre-computed/current-state data structures.
   - Avoid expensive per-request joins/grouping loops in API hot path.
6. **Observable by Default**
   - Per-bookmaker success rate, scrape latency, parse count, validation score, and last-success timestamp are mandatory metrics.

## Recommended Scale Architecture
1. **Layer 1: Discovery and Mapping**
   - Maintain bookmaker metadata table with:
     - `bookmaker_code`
     - `platform`
     - `status` (`active`, `degraded`, `disabled`)
     - `requires_proxy`
     - `priority_tier`
     - sport/market coverage flags
2. **Layer 2: Adapter Pipeline**
   - `fetch -> parse -> normalize -> validate -> persist -> publish_status`
   - Platform adapters handle fetch/parse.
   - Shared normalization/validation/persistence remain centralized.
3. **Layer 3: Job Execution**
   - Queue jobs per bookmaker with bounded concurrency by platform + global limits.
   - Separate queues:
     - `standard_books`
     - `proxy_books`
   - Use jittered retries and breaker-open skip logic.
4. **Layer 4: Read Model**
   - Build a current-odds read model keyed for matcher queries (event + market + bookmaker).
   - API reads mostly from this current-state model.
   - Background refresh updates this model incrementally.
5. **Layer 5: Cleanup**
   - Time-based + state-based cleanup:
     - delete stale non-current odds aggressively.
     - purge past events on schedule.
   - Keep optional short rolling snapshot store (for debugging only), not long-term history.

## Data Strategy (No Historical Bloat)
1. Primary tables should represent **current truth**.
2. Retention policy:
   - Current odds: keep.
   - Previous odds versions: keep short TTL (for example 24-72 hours) only if needed for diagnostics.
   - Past events: purge quickly after event completion (for example 24 hours).
3. Partition large odds tables by date or event-start buckets once volume increases.
4. Ensure indexes are aligned to matcher query keys, not generic broad indexes.

## Failure Isolation Model
1. Per-bookmaker circuit breaker with states:
   - `closed`: normal.
   - `open`: skip for cooldown.
   - `half_open`: probe with low concurrency.
2. Breaker triggers:
   - consecutive failures
   - timeout rate
   - validation failure spikes
3. Degraded mode behavior:
   - Return partial matcher data with freshness indicators.
   - Mark affected bookmaker as degraded in metadata/health endpoints.
4. Alerting thresholds:
   - no successful scrape in X minutes
   - P95 scrape latency over target
   - sudden drop in selections/markets count

## Frontend/UX Guardrails
1. Initial load should show "refreshing" and stream partial availability.
2. Filters should operate against already-cached/current read model, not trigger full recomputation.
3. Manual refresh triggers async jobs and surfaces per-bookmaker progress.
4. Display explicit performance notice for anti-bot/proxy books.

## Bookmaker Onboarding Standard (Must Pass Before `active`)
1. Discovery artifacts completed (API endpoints, auth, market mapping, anti-bot profile).
2. Adapter integration implemented with canonical contract.
3. Normalization mapping verified against canonical event/market schema.
4. Validation score passes thresholds on multiple runs.
5. Health metrics visible in `/health/scrapers`.
6. Runbook entry created:
   - failure signatures
   - known anti-bot patterns
   - rollback/disable procedure

## Implementation Plan
1. **Phase 1: Hardening Existing Core (Immediate)**
   - Enforce one scraper constructor/interface contract across all scrapers.
   - Raise parallelism safely (batch/concurrency env tuning + guardrails).
   - Remove API hot-path N+1/memory-heavy matching patterns by introducing a read-optimized query/model.
   - Ensure per-bookmaker timeout/retry/breaker settings are config-driven.
2. **Phase 2: Platform Expansion**
   - Add platform adapters for next targets (BetMakers, Generation Web, BetCloud).
   - Onboard bookmakers mostly by config + mapping, not new bespoke scraper classes.
3. **Phase 3: Proxy Tier**
   - Introduce proxy pool only for `requires_proxy=true` books.
   - Keep proxy queue isolated from standard queue to avoid global slowdowns.
4. **Phase 4: Scale Operations**
   - SLO dashboards for scrape and matcher latency.
   - Automated alerts and auto-degrade behavior.
   - Capacity testing and staged rollout by bookmaker cohorts.

## Immediate Next Actions in This Repo
1. Standardize scraper initialization contract in `apps/worker/src/jobs/scrape_service.py` and scraper classes.
2. Tune scraper concurrency defaults (`SCRAPER_BATCH_SIZE`, per-adapter limits) and measure end-to-end refresh latency.
3. Refactor matcher read path in `apps/api/src/api/routers/odds_matcher.py` toward precomputed/current-state queries.
4. Promote bookmaker/platform config as single source of truth for active status, proxy requirement, and priority.
5. Add explicit per-bookmaker SLO/error dashboards using existing health and Redis breaker data.

## Success Criteria
1. New bookmaker integration time drops from "new scraper build" to mostly "config + mapping."
2. One bookmaker outage does not materially degrade full product functionality.
3. Core refresh remains within target latency while bookmaker count grows.
4. Database size remains stable and query latency stays predictable due to freshness-first retention.
