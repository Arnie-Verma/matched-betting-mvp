# Production Optimization Plan: Outmatched-Style Architecture

**Created**: 2025-12-23
**Goal**: Build a scalable matched betting platform for 100+ bookmakers and 1000+ concurrent users
**Status**: Planning

---

## Executive Summary

### Scale Requirements

| Dimension | Current | Target (Production) |
|-----------|---------|---------------------|
| **Bookmakers** | 2 | **100+** |
| **Concurrent Users** | 1 | **1,000+** |
| **Scrape Time** | 75s | **9-11s** (bounded by slowest tier) |
| **Database Queries** | ~10/min | **1,000+/min** |
| **Odds Volume** | ~1,200/scrape | **60,000+/scrape** |

### Why Scalability Matters

At 100+ bookmakers with current sequential architecture:
- Current: 2 bookmakers × 48s = 96s
- Scaled: 100 bookmakers × 48s = 4,800s (80 minutes!) ❌ UNUSABLE

At 1,000+ concurrent users with current database:
- Current: Single DB, ~10 queries/min
- Scaled: 1,000 users × 1 query/min = 1,000 QPS on single instance ❌ BOTTLENECK

**This plan ensures architecture scales horizontally from day one.**

---

## How Outmatched Works (Production Reference)

Based on user research of Outmatched.com (competitor with 100+ bookmakers):

| Action | Time | Architecture |
|--------|------|--------------|
| Initial page load | 9-11s | Parallel scrape ALL bookmakers → Cache in DB |
| Filter by bookmaker | <2s | Query cached data (no scraping) |
| Click refresh | 9-11s | Parallel scrape ALL bookmakers → Update DB |
| TAB (proxy required) | 20-25s | Show "Performance Notice" warning |

**Key Insight**: Scrape time is **bounded by the slowest active tier**, not by bookmaker count. Adding bookmaker #101 does not change duration as long as it is in the same speed tier; proxy/anti-bot tiers will set the ceiling (e.g., 9-11s fast tier, 20-25s proxy tier).

---

## Scalability Architecture

### Current Architecture (Does Not Scale)

- Sequential scraping: one bookmaker at a time, one sport at a time
- Single database write after all scraping completes
- Response returns after 75s
- Problems at scale: 100 bookmakers = 80 minutes; 1,000 users waiting = server timeout; single DB = write contention

### Target Architecture (Scales to 100+ Bookmakers)

- Parallel scraping: ALL bookmakers simultaneously via asyncio.gather
- Each bookmaker scrapes all 6 sports in parallel internally
- Batch database write in single transaction
- Response returns after ~10s
- At scale: 100 bookmakers in parallel = 10-15s total; 1,000 users share cached results; batch writes minimize DB contention

### Queue + Cache-First Data Flow (Critical)

- **Backpressure layer**: All refresh requests enqueue a job (Celery/RQ/SQS) instead of calling scrapers directly. Workers pull with per-bookmaker concurrency caps, jittered retries, and DLQ isolation.
- **Cache-first reads**: API serves from Redis (keyed by `event_id:market:bookmaker`) with per-bookmaker TTLs (fast: 30-60s; proxy/slow: 2-5m). UI filters never trigger scraping; refresh enqueues a job.
- **Partial/streamed UI**: Return cached payload in <1-2s, then stream late bookmakers via SSE/WebSocket or polling deltas. Use `etag/last-modified` to skip re-downloading unchanged results.
- **Rate limits + circuit breakers**: Per-bookmaker timeouts, rate limits, and breaker states so TAB-like sources cannot stall the table; reopen with exponential backoff.
- **Idempotent writes**: `scrape_session_id` + unique constraint on `(bookmaker,event_id,market,selection,timestamp_bucket)` to dedupe retries and keep DB clean.

### Database Architecture for 1,000+ Users

- Load balancer distributes traffic across multiple API instances
- Matcher queries (99%) → Read replicas (horizontal scaling)
- Scraper saves (1%) → Primary (single writer)
- Redis cache → Reduce DB load further

---

## Implementation Phases

### Phase 0: Queue + Cache-First & Backpressure (Critical)

**Goal**: Decouple user traffic from scraping, cap load, and deliver sub-2s initial responses from cache.

#### Task 0.1: Introduce job queue for refreshes
- Add queue (Celery/RQ/SQS) between API refresh and workers
- Per-bookmaker concurrency caps, jittered retries, DLQ for poison tasks
- User refresh enqueues; UI returns immediately with cached data + job id

#### Task 0.2: Cache-first API + partial streaming
- Redis cache keyed by `event_id:market:bookmaker`; per-bookmaker TTL (fast 30-60s, proxy/slow 2-5m)
- ETag/Last-Modified support so clients skip unchanged payloads
- Return cached snapshot in <1-2s, stream late bookmakers via SSE/WebSocket or polling deltas

#### Task 0.3: Rate limits and circuit breakers
- Per-bookmaker rate limits + timeouts; breaker opens after N failures, half-open with backoff
- Slow/anti-bot scrapers run in isolated workers so they cannot stall the table

#### Task 0.4: Idempotent writes and dedupe
- Add `scrape_session_id` and timestamp buckets; unique constraint to dedupe retries
- Upsert/merge semantics for odds snapshots to avoid duplicates on retries or overlapping runs

#### Task 0.5: API payload shaping and auth
- Trim payload: only upcoming events, active markets, compact odds fields, pagination
- Enforce auth and per-user rate limits on refresh endpoints to prevent stampedes/abuse

---

### Phase 1: Parallel Scraping Foundation (Critical)

**Goal**: Scrape time = max(slowest_bookmaker), not sum(all_bookmakers)

This is the **critical latency change** once the queue/cache layer is in place.

| Bookmakers | Sequential (Current) | Parallel (Target) |
|------------|---------------------|-------------------|
| 2 | 96s | **10s** |
| 10 | 480s (8 min) | **12s** |
| 50 | 2,400s (40 min) | **15s** |
| 100 | 4,800s (80 min) | **15-20s** |

#### Task 1.1: Fix Race Condition in Scrapers
**File**: `apps/worker/src/scrapers/ladbrokes_scraper.py`
**Priority**: Critical (Blocks all parallelization)
**Estimated Time**: 2 hours

**Problem**: Shared `self.captured_data` list causes race condition when parallel calls overwrite each other.

**Solution**: Use local `captured_data` per call with closure pattern. Each scrape_sport() call gets isolated data capture.

**Acceptance Criteria**:
- 6 sports can run in parallel without data mixing
- 100 concurrent scrape_sport() calls work correctly
- Unit test verifies isolation

#### Task 1.2: Add Parallel Sports Method
**File**: `apps/worker/src/scrapers/ladbrokes_scraper.py`
**Priority**: Critical
**Estimated Time**: 1 hour

Add `scrape_all_sports_parallel()` method that runs all sports via asyncio.gather, aggregates results, and returns combined ScrapeResult.

**Scalability Impact**: 6 sports × 8s sequential = 48s → 6 sports parallel = ~10s

#### Task 1.3: Same Pattern for Betfair Scraper
**File**: `apps/worker/src/scrapers/betfair_scraper.py`
**Priority**: Critical
**Estimated Time**: 1 hour

Apply same race condition fix and add `scrape_all_sports_parallel()` method.

#### Task 1.4: Parallel Bookmaker Orchestration
**File**: `apps/worker/src/jobs/scrape_service.py`
**Priority**: Critical
**Estimated Time**: 1.5 hours

**Current**: Sequential loops - one bookmaker at a time, one sport at a time.

**Target**: Run ALL bookmakers in parallel via asyncio.gather. Each bookmaker internally parallelizes its sports. Include off-season sport filtering to skip unnecessary work.

---

### Phase 2: Dynamic Wait Optimization

#### Task 2.1: Replace Fixed Waits with Smart Waits
**File**: `apps/worker/src/scrapers/ladbrokes_scraper.py`
**Priority**: High
**Estimated Time**: 30 minutes

**Current**: Fixed 5-second wait regardless of when data arrives.

**Target**: Wait for network idle (no requests for 500ms) with 8s max timeout, fallback to 2s if networkidle doesn't fire.

**Scalability Impact**: Fast APIs (boxing, NBL) complete in 2-3s instead of 8s. Saves 2-4s per sport × 6 sports = 12-24s per bookmaker.

---

### Phase 3: Database Optimization for 1,000+ Users

#### Task 3.1: Database Cleanup Service
**File**: `apps/worker/src/jobs/cleanup_service.py` (NEW)
**Priority**: High
**Estimated Time**: 1 hour

**Why This Matters at Scale**:
- 100 bookmakers × 600 odds = 60,000 odds per scrape
- 12 scrapes/hour × 24h × 30 days = 518 million rows/month
- Without cleanup: queries slow to crawl, storage costs explode

**Design Principle**: Store only current odds plus tiny rolling history for debugging (last 3-5 snapshots or 24h max). Safety guard: never delete future events; only delete past-start events and odds older than retention window.

**Implementation**:
- `cleanup_old_odds(hours=24)`: Bulk delete odds older than N hours
- `cleanup_past_events()`: Delete events that have started (cascades to markets, selections, odds)
- `vacuum_database()`: Reclaim disk space after significant deletions
- Run via cron every 6 hours

**Scalability Impact**:

| Scenario | Without Cleanup | With Cleanup |
|----------|-----------------|--------------|
| Odds rows (1 week) | 5M+ | ~60K (current only) |
| Query time | Degrading | Constant <100ms |
| Storage | Growing | Stable ~100MB |

#### Task 3.2: Database Indexes for Scale
**File**: New Alembic migration
**Priority**: High
**Estimated Time**: 30 minutes

Add/adjust indexes for 1,000 QPS:
- **Hot-path index**: `(event_id, market_type, bookmaker_id, selection_id)` with partial filter `is_current = true`
- **Cleanup index**: `(timestamp)` for TTL queries
- **Upcoming events index**: `(start_time, sport)` with partial filter `start_time > now()`
- **Dedupe constraint**: Unique on `(bookmaker_id, event_id, market_type, selection_id, timestamp_bucket)`

**Why Partial Index**: With `is_current = true` or `start_time > now()` filters, indexes only include hot rows, keeping scans fast and sizes small.

#### Task 3.3: Read Replica for Query Scale (Future)
**Priority**: Medium (implement when reaching 500+ users)

At 1,000+ concurrent users, single database becomes bottleneck. Solution: PostgreSQL streaming replication with separate read/write engines. Matcher queries use replica; scraper saves use primary.

---

### Phase 4: Centralized Normalizations (Maintainability at Scale)

#### Task 4.1: Create NormalizationService
**File**: `apps/api/src/api/services/normalization_service.py` (NEW)
**Priority**: Medium
**Estimated Time**: 1.5 hours

**Why This Matters at 100+ Bookmakers**:

Current state: Team mappings duplicated in 3 files (453 lines total).

At 100 bookmakers, each may have unique team name variations. Without centralization: growing maintenance nightmare.

**Design for Scale**:
- Single source of truth for ALL team/competition mappings
- `normalize_team()`: Handle draw variations, remove prefixes/suffixes, apply mappings, LRU cached (10K entries)
- `normalize_event()`: Split team names, normalize each, sort alphabetically (handles Betfair "Away @ Home" vs Ladbrokes "Home vs Away")
- `normalize_competition()`: Map competition name variations to canonical names
- `normalize_selection()`: Alias for normalize_team

**Scalability Impact**:
- Adding new bookmaker: Update ONE file instead of THREE
- LRU cache: ~10K lookups/second, no repeated computation
- Future-proofing: move mappings to admin-editable DB store so new variants don't require code deploys; log unknown names for triage

---

### Phase 5: Anti-Bot Strategy (For TAB and Premium Bookmakers)

**Priority**: Low for MVP, High for scaling to 100+ bookmakers
**Implement when**: Adding bookmakers with strong anti-bot (TAB, Sportsbet)

#### Task 5.1: Two-Tier Proxy Architecture

**Concept**: Only use expensive rotating proxies for bookmakers that need them.

**Bookmaker Configuration**:
- Fast tier (no proxy): Betfair, Ladbrokes - Playwright scraping, 1-2s rate limits
- Proxy tier: TAB (Akamai), Sportsbet (Cloudflare) - residential rotating proxy, show performance notice

**Cost Projection**:
- ~20% of bookmakers need proxies
- SmartProxy: ~$12.50/GB
- Estimated 10GB/month for 20 bookmakers = $125/month
- Much cheaper than 100% proxy ($500+/month)

---

## Observability, Testing, and SLOs

**Metrics**:
- Scrape latency per bookmaker (p50/p95)
- Success rate per bookmaker
- Cache hit rate
- Stale-read percentage
- Queue depth and age
- DB write latency
- API p95 latency
- UI TTFB/paint time
- Circuit breaker open counts

**SLOs**:
- Scrape p95: 12s fast tier / 25s proxy tier
- Matcher read p95: <150ms
- Initial UI paint: <2s
- Queue age p95: <10s
- Stale data: <5% of reads

**Tests**:
- Load test with synthetic 100 bookmakers × 6 sports
- Chaos test (fail 20% of bookmakers, slow 10%)
- Scraper contract tests to detect DOM/API drift
- Retry/timeout tests for circuit breakers

**Alerting**:
- Cache hit rate drop
- Queue age growth
- Breaker opens
- Scrape failures >X%
- UI paint >2s sustained

---

## Implementation Timeline

### Week 1: Foundation (Decouple + Parallel)

| Day | Tasks | Outcome |
|-----|-------|---------|
| 1 | Tasks 0.1-0.3: Queue, cache-first, rate limits/circuit breakers | Refresh decoupled; UI served from cache in <2s |
| 2 | Tasks 0.4-0.5: Idempotent writes, payload shaping/auth | Dedupe enabled; lean responses; abuse-protected refresh |
| 3-4 | Tasks 1.1-1.4: Parallel scraping | 75s → 10-15s (fast tier) |
| 5 | Task 2.1: Dynamic waits + smoke/perf check | Wins back 2-4s/bookmaker |

### Week 2: Data + Maintainability

| Day | Tasks | Outcome |
|-----|-------|---------|
| 1 | Task 3.1: Cleanup with retention guard | DB stays small; no future deletes |
| 2 | Task 3.2: Database indexes (and configure read/write URLs) | <100ms reads at load |
| 3 | Task 4.1: NormalizationService | -400 lines duplication; easier new bookmakers |
| 4 | Load/chaos/perf + observability wiring | Validated SLOs and alerts |
| 5 | Phase 5 readiness: proxy tier toggles/config | Slow/proxy bookmakers isolated |

### Future: Scale (When Needed)

| Trigger | Action |
|---------|--------|
| 10+ bookmakers | Add more scrapers using base pattern |
| 500+ users | Add read replica |
| Adding TAB | Implement proxy tier |
| 50+ bookmakers | Consider Celery workers |

---

## Success Metrics

### Performance

| Metric | Current | Target | At 100 Bookmakers |
|--------|---------|--------|-------------------|
| Scrape time | 75s | 9-11s (bounded by slowest tier) | 10-15s (fast) / 20-25s (proxy) |
| Filter response | 2-3s | <2s | <2s |
| DB query time | ~50ms | <50ms | <100ms |

### Scalability

| Metric | Current | Target |
|--------|---------|--------|
| Concurrent users | 1 | 1,000+ |
| Bookmakers | 2 | 100+ |
| Database growth | Unbounded | Constant ~100MB |
| Cache hit rate | N/A | >85% |
| Code duplication | 453 lines | 0 lines |

### Match Rate

| Metric | Current | Target |
|--------|---------|--------|
| Opportunities found | 92 | 114+ |
| Match rate vs Outmatched | 73% | 90%+ |

---

## Files to Modify

| File | Changes | Priority |
|------|---------|----------|
| `api refresh endpoint` | Cache-first response, enqueue refresh jobs, ETag/Last-Modified | Critical |
| `queue/worker config` | Add queue, rate limits, retries, DLQ, per-bookmaker caps | Critical |
| `ladbrokes_scraper.py` | Fix race condition, add parallel method, dynamic waits | Critical |
| `betfair_scraper.py` | Add parallel method, dynamic waits | Critical |
| `scrape_service.py` | Parallel bookmaker orchestration | Critical |
| `cleanup_service.py` | NEW - Database cleanup | High |
| `normalization_service.py` | NEW - Centralized mappings | Medium |
| `odds_matcher.py` | Use NormalizationService | Medium |
| `save_odds.py` | Use NormalizationService | Medium |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Queue backlog from refresh storms | Rate limit refresh endpoint, cap queue length, expose queue age alert, drop/merge duplicate refreshes |
| Slow/proxy bookmakers block table | Circuit breakers + isolation workers; surface partial results immediately |
| Parallel scraping corrupts data | Local captured_data per call, comprehensive tests |
| Dynamic waits miss data | Fallback timeout, compare event counts before/after |
| Cleanup deletes active data | Only delete past events, 24h buffer for odds |
| New bookmaker breaks normalizations | Centralized service, easy to add mappings |
| DB bottleneck at 1000 users | Read replica ready, indexes optimized |

---

## Questions to Resolve Before Implementation

1. **Cache TTL per tier**: Fast vs proxy/slow bookmakers; acceptable stale window for UI (30-60s vs 2-5m?).
2. **Refresh/backpressure policy**: Per-user refresh limits, queue length cap, and behavior when queue is full (drop/merge/429?).
3. **Retention**: Exact cleanup retention (hours vs last N snapshots) and any audit/logging requirements.
4. **Error handling**: When to retry vs skip a bookmaker; show partial results thresholds; breaker thresholds.
5. **Proxy/anti-bot budget**: Monthly spend and which bookmakers justify proxy tier first.

---

*Document version: 3.0*
*Last updated: 2025-12-23*
*Focus: Scalability for 100+ bookmakers, 1000+ users*
# Production Optimization Plan: Outmatched-Style Architecture

**Created**: 2025-12-23
**Goal**: Build a scalable matched betting platform for 100+ bookmakers and 1000+ concurrent users
**Status**: Planning

---

## Executive Summary

### Scale Requirements

| Dimension | Current | Target (Production) |
|-----------|---------|---------------------|
| **Bookmakers** | 2 | **100+** |
| **Concurrent Users** | 1 | **1,000+** |
| **Scrape Time** | 75s | **9-11s** (bounded by slowest tier) |
| **Database Queries** | ~10/min | **1,000+/min** |
| **Odds Volume** | ~1,200/scrape | **60,000+/scrape** |

### Why Scalability Matters

At 100+ bookmakers with current sequential architecture:
- Current: 2 bookmakers × 48s = 96s
- Scaled: 100 bookmakers × 48s = 4,800s (80 minutes!) ❌ UNUSABLE

At 1,000+ concurrent users with current database:
- Current: Single DB, ~10 queries/min
- Scaled: 1,000 users × 1 query/min = 1,000 QPS on single instance ❌ BOTTLENECK

**This plan ensures architecture scales horizontally from day one.**

---

## How Outmatched Works (Production Reference)

Based on user research of Outmatched.com (competitor with 100+ bookmakers):

| Action | Time | Architecture |
|--------|------|--------------|
| Initial page load | 9-11s | Parallel scrape ALL bookmakers → Cache in DB |
| Filter by bookmaker | <2s | Query cached data (no scraping) |
| Click refresh | 9-11s | Parallel scrape ALL bookmakers → Update DB |
| TAB (proxy required) | 20-25s | Show "Performance Notice" warning |

**Key Insight**: Scrape time is **bounded by the slowest active tier**, not by bookmaker count. Adding bookmaker #101 does not change duration as long as it is in the same speed tier; proxy/anti-bot tiers will set the ceiling (e.g., 9-11s fast tier, 20-25s proxy tier).

---

## Scalability Architecture

### Current Architecture (Does Not Scale)

- Sequential scraping: one bookmaker at a time, one sport at a time
- Single database write after all scraping completes
- Response returns after 75s
- Problems at scale: 100 bookmakers = 80 minutes; 1,000 users waiting = server timeout; single DB = write contention

### Target Architecture (Scales to 100+ Bookmakers)

- Parallel scraping: ALL bookmakers simultaneously via asyncio.gather
- Each bookmaker scrapes all 6 sports in parallel internally
- Batch database write in single transaction
- Response returns after ~10s
- At scale: 100 bookmakers in parallel = 10-15s total; 1,000 users share cached results; batch writes minimize DB contention

### Queue + Cache-First Data Flow (Critical)

- **Backpressure layer**: All refresh requests enqueue a job (Celery/RQ/SQS) instead of calling scrapers directly. Workers pull with per-bookmaker concurrency caps, jittered retries, and DLQ isolation.
- **Cache-first reads**: API serves from Redis (keyed by `event_id:market:bookmaker`) with per-bookmaker TTLs (fast: 30-60s; proxy/slow: 2-5m). UI filters never trigger scraping; refresh enqueues a job.
- **Partial/streamed UI**: Return cached payload in <1-2s, then stream late bookmakers via SSE/WebSocket or polling deltas. Use `etag/last-modified` to skip re-downloading unchanged results.
- **Rate limits + circuit breakers**: Per-bookmaker timeouts, rate limits, and breaker states so TAB-like sources cannot stall the table; reopen with exponential backoff.
- **Idempotent writes**: `scrape_session_id` + unique constraint on `(bookmaker,event_id,market,selection,timestamp_bucket)` to dedupe retries and keep DB clean.

### Database Architecture for 1,000+ Users

- Load balancer distributes traffic across multiple API instances
- Matcher queries (99%) → Read replicas (horizontal scaling)
- Scraper saves (1%) → Primary (single writer)
- Redis cache → Reduce DB load further

---

## Implementation Phases

### Phase 0: Queue + Cache-First & Backpressure (Critical)

**Goal**: Decouple user traffic from scraping, cap load, and deliver sub-2s initial responses from cache.

#### Task 0.1: Introduce job queue for refreshes
- Add queue (Celery/RQ/SQS) between API refresh and workers
- Per-bookmaker concurrency caps, jittered retries, DLQ for poison tasks
- User refresh enqueues; UI returns immediately with cached data + job id

#### Task 0.2: Cache-first API + partial streaming
- Redis cache keyed by `event_id:market:bookmaker`; per-bookmaker TTL (fast 30-60s, proxy/slow 2-5m)
- ETag/Last-Modified support so clients skip unchanged payloads
- Return cached snapshot in <1-2s, stream late bookmakers via SSE/WebSocket or polling deltas

#### Task 0.3: Rate limits and circuit breakers
- Per-bookmaker rate limits + timeouts; breaker opens after N failures, half-open with backoff
- Slow/anti-bot scrapers run in isolated workers so they cannot stall the table

#### Task 0.4: Idempotent writes and dedupe
- Add `scrape_session_id` and timestamp buckets; unique constraint to dedupe retries
- Upsert/merge semantics for odds snapshots to avoid duplicates on retries or overlapping runs

#### Task 0.5: API payload shaping and auth
- Trim payload: only upcoming events, active markets, compact odds fields, pagination
- Enforce auth and per-user rate limits on refresh endpoints to prevent stampedes/abuse

---

### Phase 1: Parallel Scraping Foundation (Critical)

**Goal**: Scrape time = max(slowest_bookmaker), not sum(all_bookmakers)

This is the **critical latency change** once the queue/cache layer is in place.

| Bookmakers | Sequential (Current) | Parallel (Target) |
|------------|---------------------|-------------------|
| 2 | 96s | **10s** |
| 10 | 480s (8 min) | **12s** |
| 50 | 2,400s (40 min) | **15s** |
| 100 | 4,800s (80 min) | **15-20s** |

#### Task 1.1: Fix Race Condition in Scrapers
**File**: `apps/worker/src/scrapers/ladbrokes_scraper.py`
**Priority**: Critical (Blocks all parallelization)
**Estimated Time**: 2 hours

**Problem**: Shared `self.captured_data` list causes race condition when parallel calls overwrite each other.

**Solution**: Use local `captured_data` per call with closure pattern. Each scrape_sport() call gets isolated data capture.

**Acceptance Criteria**:
- 6 sports can run in parallel without data mixing
- 100 concurrent scrape_sport() calls work correctly
- Unit test verifies isolation

#### Task 1.2: Add Parallel Sports Method
**File**: `apps/worker/src/scrapers/ladbrokes_scraper.py`
**Priority**: Critical
**Estimated Time**: 1 hour

Add `scrape_all_sports_parallel()` method that runs all sports via asyncio.gather, aggregates results, and returns combined ScrapeResult.

**Scalability Impact**: 6 sports × 8s sequential = 48s → 6 sports parallel = ~10s

#### Task 1.3: Same Pattern for Betfair Scraper
**File**: `apps/worker/src/scrapers/betfair_scraper.py`
**Priority**: Critical
**Estimated Time**: 1 hour

Apply same race condition fix and add `scrape_all_sports_parallel()` method.

#### Task 1.4: Parallel Bookmaker Orchestration
**File**: `apps/worker/src/jobs/scrape_service.py`
**Priority**: Critical
**Estimated Time**: 1.5 hours

**Current**: Sequential loops - one bookmaker at a time, one sport at a time.

**Target**: Run ALL bookmakers in parallel via asyncio.gather. Each bookmaker internally parallelizes its sports. Include off-season sport filtering to skip unnecessary work.

---

### Phase 2: Dynamic Wait Optimization

#### Task 2.1: Replace Fixed Waits with Smart Waits
**File**: `apps/worker/src/scrapers/ladbrokes_scraper.py`
**Priority**: High
**Estimated Time**: 30 minutes

**Current**: Fixed 5-second wait regardless of when data arrives.

**Target**: Wait for network idle (no requests for 500ms) with 8s max timeout, fallback to 2s if networkidle doesn't fire.

**Scalability Impact**: Fast APIs (boxing, NBL) complete in 2-3s instead of 8s. Saves 2-4s per sport × 6 sports = 12-24s per bookmaker.

---

### Phase 3: Database Optimization for 1,000+ Users

#### Task 3.1: Database Cleanup Service
**File**: `apps/worker/src/jobs/cleanup_service.py` (NEW)
**Priority**: High
**Estimated Time**: 1 hour

**Why This Matters at Scale**:
- 100 bookmakers × 600 odds = 60,000 odds per scrape
- 12 scrapes/hour × 24h × 30 days = 518 million rows/month
- Without cleanup: queries slow to crawl, storage costs explode

**Design Principle**: Store only current odds plus tiny rolling history for debugging (last 3-5 snapshots or 24h max). Safety guard: never delete future events; only delete past-start events and odds older than retention window.

**Implementation**:
- `cleanup_old_odds(hours=24)`: Bulk delete odds older than N hours
- `cleanup_past_events()`: Delete events that have started (cascades to markets, selections, odds)
- `vacuum_database()`: Reclaim disk space after significant deletions
- Run via cron every 6 hours

**Scalability Impact**:

| Scenario | Without Cleanup | With Cleanup |
|----------|-----------------|--------------|
| Odds rows (1 week) | 5M+ | ~60K (current only) |
| Query time | Degrading | Constant <100ms |
| Storage | Growing | Stable ~100MB |

#### Task 3.2: Database Indexes for Scale
**File**: New Alembic migration
**Priority**: High
**Estimated Time**: 30 minutes

Add/adjust indexes for 1,000 QPS:
- **Hot-path index**: `(event_id, market_type, bookmaker_id, selection_id)` with partial filter `is_current = true`
- **Cleanup index**: `(timestamp)` for TTL queries
- **Upcoming events index**: `(start_time, sport)` with partial filter `start_time > now()`
- **Dedupe constraint**: Unique on `(bookmaker_id, event_id, market_type, selection_id, timestamp_bucket)`

**Why Partial Index**: With `is_current = true` or `start_time > now()` filters, indexes only include hot rows, keeping scans fast and sizes small.

#### Task 3.3: Read Replica for Query Scale (Future)
**Priority**: Medium (implement when reaching 500+ users)

At 1,000+ concurrent users, single database becomes bottleneck. Solution: PostgreSQL streaming replication with separate read/write engines. Matcher queries use replica; scraper saves use primary.

---

### Phase 4: Centralized Normalizations (Maintainability at Scale)

#### Task 4.1: Create NormalizationService
**File**: `apps/api/src/api/services/normalization_service.py` (NEW)
**Priority**: Medium
**Estimated Time**: 1.5 hours

**Why This Matters at 100+ Bookmakers**:

Current state: Team mappings duplicated in 3 files (453 lines total).

At 100 bookmakers, each may have unique team name variations. Without centralization: growing maintenance nightmare.

**Design for Scale**:
- Single source of truth for ALL team/competition mappings
- `normalize_team()`: Handle draw variations, remove prefixes/suffixes, apply mappings, LRU cached (10K entries)
- `normalize_event()`: Split team names, normalize each, sort alphabetically (handles Betfair "Away @ Home" vs Ladbrokes "Home vs Away")
- `normalize_competition()`: Map competition name variations to canonical names
- `normalize_selection()`: Alias for normalize_team

**Scalability Impact**:
- Adding new bookmaker: Update ONE file instead of THREE
- LRU cache: ~10K lookups/second, no repeated computation
- Future-proofing: move mappings to admin-editable DB store so new variants don't require code deploys; log unknown names for triage

---

### Phase 5: Anti-Bot Strategy (For TAB and Premium Bookmakers)

**Priority**: Low for MVP, High for scaling to 100+ bookmakers
**Implement when**: Adding bookmakers with strong anti-bot (TAB, Sportsbet)

#### Task 5.1: Two-Tier Proxy Architecture

**Concept**: Only use expensive rotating proxies for bookmakers that need them.

**Bookmaker Configuration**:
- Fast tier (no proxy): Betfair, Ladbrokes - Playwright scraping, 1-2s rate limits
- Proxy tier: TAB (Akamai), Sportsbet (Cloudflare) - residential rotating proxy, show performance notice

**Cost Projection**:
- ~20% of bookmakers need proxies
- SmartProxy: ~$12.50/GB
- Estimated 10GB/month for 20 bookmakers = $125/month
- Much cheaper than 100% proxy ($500+/month)

---

## Observability, Testing, and SLOs

**Metrics**:
- Scrape latency per bookmaker (p50/p95)
- Success rate per bookmaker
- Cache hit rate
- Stale-read percentage
- Queue depth and age
- DB write latency
- API p95 latency
- UI TTFB/paint time
- Circuit breaker open counts

**SLOs**:
- Scrape p95: 12s fast tier / 25s proxy tier
- Matcher read p95: <150ms
- Initial UI paint: <2s
- Queue age p95: <10s
- Stale data: <5% of reads

**Tests**:
- Load test with synthetic 100 bookmakers × 6 sports
- Chaos test (fail 20% of bookmakers, slow 10%)
- Scraper contract tests to detect DOM/API drift
- Retry/timeout tests for circuit breakers

**Alerting**:
- Cache hit rate drop
- Queue age growth
- Breaker opens
- Scrape failures >X%
- UI paint >2s sustained

---

## Implementation Timeline

### Week 1: Foundation (Decouple + Parallel)

| Day | Tasks | Outcome |
|-----|-------|---------|
| 1 | Tasks 0.1-0.3: Queue, cache-first, rate limits/circuit breakers | Refresh decoupled; UI served from cache in <2s |
| 2 | Tasks 0.4-0.5: Idempotent writes, payload shaping/auth | Dedupe enabled; lean responses; abuse-protected refresh |
| 3-4 | Tasks 1.1-1.4: Parallel scraping | 75s → 10-15s (fast tier) |
| 5 | Task 2.1: Dynamic waits + smoke/perf check | Wins back 2-4s/bookmaker |

### Week 2: Data + Maintainability

| Day | Tasks | Outcome |
|-----|-------|---------|
| 1 | Task 3.1: Cleanup with retention guard | DB stays small; no future deletes |
| 2 | Task 3.2: Database indexes (and configure read/write URLs) | <100ms reads at load |
| 3 | Task 4.1: NormalizationService | -400 lines duplication; easier new bookmakers |
| 4 | Load/chaos/perf + observability wiring | Validated SLOs and alerts |
| 5 | Phase 5 readiness: proxy tier toggles/config | Slow/proxy bookmakers isolated |

### Future: Scale (When Needed)

| Trigger | Action |
|---------|--------|
| 10+ bookmakers | Add more scrapers using base pattern |
| 500+ users | Add read replica |
| Adding TAB | Implement proxy tier |
| 50+ bookmakers | Consider Celery workers |

---

## Success Metrics

### Performance

| Metric | Current | Target | At 100 Bookmakers |
|--------|---------|--------|-------------------|
| Scrape time | 75s | 9-11s (bounded by slowest tier) | 10-15s (fast) / 20-25s (proxy) |
| Filter response | 2-3s | <2s | <2s |
| DB query time | ~50ms | <50ms | <100ms |

### Scalability

| Metric | Current | Target |
|--------|---------|--------|
| Concurrent users | 1 | 1,000+ |
| Bookmakers | 2 | 100+ |
| Database growth | Unbounded | Constant ~100MB |
| Cache hit rate | N/A | >85% |
| Code duplication | 453 lines | 0 lines |

### Match Rate

| Metric | Current | Target |
|--------|---------|--------|
| Opportunities found | 92 | 114+ |
| Match rate vs Outmatched | 73% | 90%+ |

---

## Files to Modify

| File | Changes | Priority |
|------|---------|----------|
| `api refresh endpoint` | Cache-first response, enqueue refresh jobs, ETag/Last-Modified | Critical |
| `queue/worker config` | Add queue, rate limits, retries, DLQ, per-bookmaker caps | Critical |
| `ladbrokes_scraper.py` | Fix race condition, add parallel method, dynamic waits | Critical |
| `betfair_scraper.py` | Add parallel method, dynamic waits | Critical |
| `scrape_service.py` | Parallel bookmaker orchestration | Critical |
| `cleanup_service.py` | NEW - Database cleanup | High |
| `normalization_service.py` | NEW - Centralized mappings | Medium |
| `odds_matcher.py` | Use NormalizationService | Medium |
| `save_odds.py` | Use NormalizationService | Medium |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Queue backlog from refresh storms | Rate limit refresh endpoint, cap queue length, expose queue age alert, drop/merge duplicate refreshes |
| Slow/proxy bookmakers block table | Circuit breakers + isolation workers; surface partial results immediately |
| Parallel scraping corrupts data | Local captured_data per call, comprehensive tests |
| Dynamic waits miss data | Fallback timeout, compare event counts before/after |
| Cleanup deletes active data | Only delete past events, 24h buffer for odds |
| New bookmaker breaks normalizations | Centralized service, easy to add mappings |
| DB bottleneck at 1000 users | Read replica ready, indexes optimized |

---

## Questions to Resolve Before Implementation

1. **Cache TTL per tier**: Fast vs proxy/slow bookmakers; acceptable stale window for UI (30-60s vs 2-5m?).
2. **Refresh/backpressure policy**: Per-user refresh limits, queue length cap, and behavior when queue is full (drop/merge/429?).
3. **Retention**: Exact cleanup retention (hours vs last N snapshots) and any audit/logging requirements.
4. **Error handling**: When to retry vs skip a bookmaker; show partial results thresholds; breaker thresholds.
5. **Proxy/anti-bot budget**: Monthly spend and which bookmakers justify proxy tier first.

---

*Document version: 3.0*
*Last updated: 2025-12-23*
*Focus: Scalability for 100+ bookmakers, 1000+ users*
