# API

FastAPI service for odds matcher read APIs and refresh orchestration.

## Responsibilities
- Serve matcher endpoints (`/odds/matcher`, refresh endpoints)
- Serve bookmaker/sport metadata endpoints
- Enforce subscription-driven bookmaker access
- Expose health endpoints for API/database/scraper freshness

## Common Commands
```bash
# Run tests (from repo root)
pytest apps/api/tests

# Seed plans/bookmakers
docker exec mb_api python -m api.scripts.seed_plans
docker exec mb_api python -m api.scripts.seed_all_bookmakers
```

## Key Paths
- `src/api/routers` - API routes
- `src/api/services` - matching/refresh/subscription logic
- `src/api/models` - SQLAlchemy models
- `src/api/scripts` - seed/maintenance scripts
