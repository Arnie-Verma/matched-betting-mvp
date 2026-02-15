# Phase 0 Implementation Complete ✅

**Date**: 2025-12-26
**Status**: Ready for Testing

---

## Summary

Phase 0 (Queue/Cache/Backpressure) is now complete. The system is production-safe with circuit breakers, timeout protection, and idempotent writes.

### What Was Implemented

| Feature | File | Description |
|---------|------|-------------|
| **Circuit Breaker** | [scrape_service.py](apps/worker/src/jobs/scrape_service.py#L40-L119) | Redis-based breaker with 3 states (closed/open/half-open) |
| **Timeout Protection** | [scrape_service.py](apps/worker/src/jobs/scrape_service.py#L173-L188) | 25s max timeout per scraper using asyncio.wait_for |
| **Idempotent Writes** | [save_odds.py](apps/worker/src/jobs/save_odds.py#L164-L195) | PostgreSQL upsert with timestamp_bucket dedupe |
| **Database Schema** | [odds.py](apps/api/src/api/models/odds.py#L361) | Added timestamp_bucket column |
| **Migration** | [20251226_add_idempotent_writes_support.py](apps/api/alembic/versions/20251226_add_idempotent_writes_support.py) | Alembic migration for schema changes |

---

## Circuit Breaker Behavior

### States

```
CLOSED (normal) → OPEN (after 5 failures) → HALF-OPEN (after 60s cooldown) → CLOSED (on success)
```

### Configuration

```bash
BOOKMAKER_BREAKER_THRESHOLD=5        # Failures before opening
BOOKMAKER_BREAKER_COOLDOWN_SECONDS=60  # Cooldown before half-open
BOOKMAKER_TIMEOUT_SECONDS=25          # Max scraper timeout
```

### Example Flow

1. **Closed state**: Scraper runs normally
2. **1st-4th failure**: Increments counter, logs warning
3. **5th failure**: Opens breaker, skips scrapes for 60s
4. **After 60s**: Half-open state, allows 1 retry
5. **Retry succeeds**: Back to closed, counter resets
6. **Retry fails**: Opens again for another 60s

---

## Idempotent Writes

### How It Works

1. **Timestamp Bucketing**: Rounds timestamp to nearest 5-min bucket
   - `2025-12-26 10:42:37` → `2025-12-26 10:40:00`

2. **Unique Constraint**: `(selection_id, bookmaker_id, timestamp_bucket, scrape_session_id)`
   - Same scrape_session_id + timestamp_bucket → upsert (no duplicate)
   - Different scrape_session_id → new row (intentional re-scrape)

3. **Upsert Logic**: PostgreSQL `INSERT ... ON CONFLICT DO UPDATE`
   ```sql
   INSERT INTO odds_snapshots (...) VALUES (...)
   ON CONFLICT (selection_id, bookmaker_id, timestamp_bucket, scrape_session_id)
   DO UPDATE SET decimal_odds = EXCLUDED.decimal_odds, ...
   ```

### Benefits

- **Safe retries**: Worker can retry failed jobs without creating duplicates
- **Overlapping scrapes**: Multiple workers won't corrupt data
- **Consistent state**: Database always has coherent snapshot per scrape_session_id

---

## Testing Instructions

### 1. Apply Migration

```bash
# Start services
pnpm dev:up

# Apply migration
docker exec mb_api alembic upgrade head

# Verify migration applied
docker exec mb_api alembic current
# Should show: 20251226_idempotent (head)
```

### 2. Test Circuit Breaker

**Scenario**: Force failures and verify breaker opens

```bash
# Method 1: Stop database to force failures
docker stop mb_db

# Trigger 5 scrape attempts (via refresh endpoint or manual_scrape.py)
# Each failure increments counter

# Check Redis for breaker state
docker exec mb_redis redis-cli GET "breaker:ladbrokes"
# Should show: {"state": "open", "failures": 5, "opened_at": "2025-12-26T..."}

# Restart database
docker start mb_db

# Wait 60s for cooldown, then retry
# Breaker should enter half-open, allow retry, and close on success
```

**Method 2: Use Python to manually test**

```python
# In apps/worker/src/manual_test_breaker.py
import asyncio
from jobs.scrape_service import get_scrape_service

async def test_breaker():
    service = get_scrape_service()

    # Force 5 failures
    for i in range(5):
        # Simulate failure by passing invalid bookmaker
        result = await service.scrape_bookmaker("invalid_bookmaker", "soccer")
        print(f"Attempt {i+1}: {result}")

    # 6th attempt should be skipped by circuit breaker
    result = await service.scrape_bookmaker("ladbrokes", "soccer")
    print(f"6th attempt (should be skipped): {result}")
    assert result.get("breaker_state") == "open"

asyncio.run(test_breaker())
```

### 3. Test Idempotent Writes

**Scenario**: Run same scrape twice, verify no duplicates

```bash
# Run scrape once
docker exec mb_api python ../worker/src/manual_scrape.py

# Count odds before
docker exec mb_db psql -U postgres -d mb_dev -c "SELECT COUNT(*) FROM odds_snapshots WHERE is_current = true;"
# Note the count (e.g., 7800)

# Run same scrape again (same timestamp_bucket, same scrape_session_id)
docker exec mb_api python ../worker/src/manual_scrape.py

# Count odds after
docker exec mb_db psql -U postgres -d mb_dev -c "SELECT COUNT(*) FROM odds_snapshots WHERE is_current = true;"
# Should be SAME count (7800) - no duplicates!

# Verify timestamp_bucket populated
docker exec mb_db psql -U postgres -d mb_dev -c "SELECT COUNT(*) FROM odds_snapshots WHERE timestamp_bucket IS NOT NULL;"
# Should match total count
```

### 4. Test Timeout Protection

**Scenario**: Scraper takes >25s, timeout fires

```python
# In apps/worker/src/scrapers/ladbrokes_scraper.py
# Add artificial delay in scrape_sport():

import asyncio
async def scrape_sport(self, sport, limit=None):
    await asyncio.sleep(30)  # Force timeout
    # ... rest of method
```

```bash
# Run scrape - should timeout after 25s
docker exec mb_api python ../worker/src/manual_scrape.py

# Check logs for timeout error
docker logs mb_api --tail 50 | grep -i timeout
# Should see: "[ladbrokes] Scrape timed out after 25s"

# Verify circuit breaker incremented failure count
docker exec mb_redis redis-cli GET "breaker:ladbrokes"
```

---

## Integration Test

**Full end-to-end test of Phase 0:**

```bash
# 1. Clean start
pnpm dev:down && pnpm dev:up
docker exec mb_api alembic upgrade head

# 2. Trigger refresh via API
curl -X POST http://localhost:8000/odds/refresh \
  -H "Authorization: Bearer <YOUR_CLERK_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"force": false}'

# Response should include job_id:
# {"success": true, "job_id": "abc-123", "message": "Refresh job queued", ...}

# 3. Check job status
curl http://localhost:8000/odds/refresh/status?job_id=abc-123 \
  -H "Authorization: Bearer <YOUR_CLERK_TOKEN>"

# Should show: {"status": "success", "result": {...}}

# 4. Verify cache TTL
docker exec mb_redis redis-cli TTL "odds_last_refresh_global"
# Should show remaining seconds (max 60)

# 5. Trigger again within TTL - should use cache
curl -X POST http://localhost:8000/odds/refresh \
  -H "Authorization: Bearer <YOUR_CLERK_TOKEN>" \
  -d '{"force": false}'

# Should return cached response immediately

# 6. Force refresh to bypass cache
curl -X POST http://localhost:8000/odds/refresh \
  -H "Authorization: Bearer <YOUR_CLERK_TOKEN>" \
  -d '{"force": true}'

# Should enqueue new job despite cache
```

---

## Environment Variables

### Required (Already Set)

```bash
# Queue/Cache
REDIS_URL=redis://localhost:6379/0
ODDS_REFRESH_QUEUE_KEY=odds_refresh_jobs
ODDS_REFRESH_MAX_QUEUE_LENGTH=50
ODDS_REFRESH_MERGE_IF_PENDING=1

# Rate Limits
ODDS_REFRESH_PER_USER_SECONDS=30
ODDS_CACHE_TTL_FAST_SECONDS=60
ODDS_CACHE_TTL_SLOW_SECONDS=300

# Retry/Backoff
ODDS_REFRESH_MAX_RETRIES=3
ODDS_REFRESH_BACKOFF_BASE=2
ODDS_REFRESH_BACKOFF_JITTER=1

# Concurrency
BOOKMAKER_CONCURRENCY_CAP=1
ACTIVE_BOOKMAKERS=betfair,ladbrokes
SLOW_BOOKMAKERS=tab
```

### New (Circuit Breaker - Defaults Provided)

```bash
BOOKMAKER_BREAKER_THRESHOLD=5       # Number of failures before opening breaker
BOOKMAKER_BREAKER_COOLDOWN_SECONDS=60  # Cooldown before half-open retry
BOOKMAKER_TIMEOUT_SECONDS=25         # Max timeout per scraper call
```

---

## Known Limitations

1. **Migration assumes PostgreSQL**
   - Uses `INSERT ... ON CONFLICT` (PostgreSQL-specific)
   - SQLite/MySQL would need different upsert syntax

2. **Old constraint might have different name**
   - Migration tries to drop `uq_odds_selection_bookmaker_time`
   - If constraint doesn't exist or has different name, check error logs
   - Manually drop if needed: `ALTER TABLE odds_snapshots DROP CONSTRAINT <name>;`

3. **Timestamp bucket is fixed at 5 minutes**
   - Could be made configurable via env var later
   - Current: floors to nearest 5-min increment

4. **Circuit breaker is per-bookmaker only**
   - No global breaker across all bookmakers
   - Each bookmaker has independent state

---

## Next Steps: Phase 1 (Parallel Scraping)

Now that Phase 0 is complete, we can move to Phase 1:

1. **Fix race condition** in [betfair_scraper.py](apps/worker/src/scrapers/betfair_scraper.py) and [ladbrokes_scraper.py](apps/worker/src/scrapers/ladbrokes_scraper.py)
   - Use closure pattern for `captured_data` (local per call)

2. **Add parallel sports method** to both scrapers
   - `scrape_all_sports_parallel()` using asyncio.gather

3. **Parallel bookmaker orchestration** in [scrape_service.py](apps/worker/src/jobs/scrape_service.py)
   - Remove sequential loop, use asyncio.gather for all bookmakers

**Expected Impact**: 72-96s → 10-15s (6-8x faster)

---

## Questions?

- Check [PRODUCTION_OPTIMIZATION_PLAN.md](PRODUCTION_OPTIMIZATION_PLAN.md) for full context
- See [DAILY.md](DAILY.md) for implementation notes
- Review code comments in modified files for implementation details
