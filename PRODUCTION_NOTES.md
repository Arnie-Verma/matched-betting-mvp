# Production Deployment Notes

## Purpose
Runtime and deployment defaults for production environments.

## Environment Profiles

### Local/Dev (Docker constrained)
- `SCRAPER_BATCH_SIZE=1`
- Conservative parallelism to avoid local resource contention.

### Staging
- Production-like behavior with reduced concurrency caps.
- Validate breaker behavior, refresh latency, and degraded states.

### Production
- Increase concurrency per platform based on observed latency/error rates.
- Keep per-platform limits and rollback thresholds explicit.

## Key Environment Variables

| Variable | Dev | Production Guidance |
|----------|-----|---------------------|
| `SCRAPER_BATCH_SIZE` | `1` | Tune by platform and hardware capacity |
| `BOOKMAKER_TIMEOUT_SECONDS` | `25` | Usually `15-25` by platform class |
| `BOOKMAKER_BREAKER_THRESHOLD` | `5` | Usually stricter than dev |
| `BOOKMAKER_BREAKER_COOLDOWN_SECONDS` | `60` | Usually longer than dev |
| `BOOKMAKER_FREEZE_UNIBET` | `true` | Keep `true` until Phase A GO; set `false` only with explicit gate approval |
| `DATABASE_URL` | local postgres | managed postgres |
| `REDIS_URL` | local redis | managed redis |

## Proxy Configuration
Use proxy only for books that need it.

```bash
RESIDENTIAL_PROXY_URL=http://user:pass@proxy.example:port
PROXY_BOOKMAKERS=tab,sportsbet
```

## Current Platform Notes

| Platform/Book | Proxy Needed | Status |
|---------------|--------------|--------|
| Entain (Ladbrokes/Neds) | No | Active |
| Betfair | No | Active |
| Punterstech | No | Active |
| Kindred (Unibet) | No | Active |
| TAB | Yes | Slower / anti-bot constrained |

## Monitoring Requirements
Track per bookmaker:
- Success rate (1h/24h)
- P50/P95 scrape duration
- Last successful scrape timestamp
- Validation score trend
- Circuit breaker state

## Deployment Checklist
1. Set production secrets and CORS origins.
2. Run migrations: `alembic upgrade head`.
3. Seed config: `seed_plans`, `seed_all_bookmakers`.
4. Run a manual scrape and validate health endpoints.
5. Confirm refresh, partial results, and degraded-bookmaker behavior.

## Related Docs
- `BOOKMAKER_OPERATING_SYSTEM.md`
- `VALIDATION_FRAMEWORK.md`
- `ROADMAP.md`
