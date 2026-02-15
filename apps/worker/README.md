# Worker

Background scraper and refresh execution service.

## Responsibilities
- Run platform/bookmaker scrapes
- Apply validation pipeline after scrape
- Persist normalized odds snapshots
- Execute queued refresh jobs with per-bookmaker isolation

## Common Commands
```bash
# Manual scrape run
docker exec mb_api python ../worker/src/manual_scrape.py

# Validate scraper output
docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition epl
```

## Key Paths
- `src/scrapers` - scraper implementations by platform
- `src/jobs` - orchestration, persistence, refresh worker
- `src/validation` - structural/probability/golden validation
