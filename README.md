# matched-betting-mvp

Outmatched-style matched betting platform for Australia.

## Monorepo Layout
- `apps/web` - Next.js web app (odds matcher UI)
- `apps/api` - FastAPI backend (matcher API, metadata, auth hooks)
- `apps/worker` - scraper and refresh workers
- `packages/shared` - shared types/utilities
- `infra` - docker compose and infrastructure helpers

## Quick Start (Docker)
1. Start services:
```bash
docker compose -f infra/dev/docker-compose.yml up -d
```
2. Run migrations:
```bash
docker exec mb_api alembic upgrade head
```
3. Seed plans/bookmakers:
```bash
docker exec mb_api python -m api.scripts.seed_plans
docker exec mb_api python -m api.scripts.seed_all_bookmakers
```
4. Trigger scrape:
```bash
docker exec mb_api python ../worker/src/manual_scrape.py
```

## Primary Docs
- `CLAUDE.md` - repo working rules and conventions
- `DAILY.md` - active progress log
- `ARCHITECTURE.md` - implemented architecture and runtime flows
- `BOOKMAKER_OPERATING_SYSTEM.md` - scaling lifecycle and guardrails
- `SCRAPER_HARDENING_PLAN.md` - current hardening sequence before new onboarding
- `DISCOVERY_SUMMARY.md` - current discovery status by platform
- `BOOKMAKER_IMPLEMENTATION_GUIDE.md` - scraper implementation playbook
- `VALIDATION_FRAMEWORK.md` - validation model and thresholds
- `Unibet.md` - bookmaker-specific runbook example
- `docs/adr/README.md` - architecture decision records index
- `PRODUCTION_NOTES.md` - deployment/runtime notes
- `ROADMAP.md` - current product roadmap

## Archive
Historical planning and superseded docs are in `docs/archive`.
