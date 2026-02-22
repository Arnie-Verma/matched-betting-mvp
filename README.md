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
- `apps/worker/src/scripts/run_phase_a_canary.py` - local canary gate script (validation + reliability thresholds)
- `docs/adr/README.md` - architecture decision records index
- `PRODUCTION_NOTES.md` - deployment/runtime notes
- `ROADMAP.md` - current product roadmap

## Phase A Hardening Snapshot (2026-02-22)
Implemented now:
- Bounded scrape scheduler in worker (`global` + `per-platform` concurrency caps) with scheduler metrics.
- Runtime active bookmaker derivation from DB + freeze policy (no static active bookmaker control path).
- Odds matcher hot path refactor to set-based preloading (events, markets, selections, odds) with no response schema changes.
- Matcher read-model foundation + guarded serving mode with:
  - dedicated `matcher_read_model_builds` and `matcher_read_model_rows` persistence
  - idempotent bounded builder (`event_limit`, `event_batch_size`, `row_batch_size`)
  - optional shadow parity mode to compare read-model rows with runtime matcher output
  - feature-flagged read-model serving path for `/odds/matcher` with automatic runtime fallback on stale/missing/unhealthy read-model state
  - serving telemetry fields: `serving_source=runtime|read_model|runtime_fallback` and deterministic `fallback_reason_code`
  - builder command: `python -m api.scripts.build_matcher_read_model --shadow-parity`
- Lifecycle persistence + transition guard enforcement in code:
  - persistent bookmaker lifecycle states
  - audited lifecycle transition history
  - admin/internal guarded transition control surface
  - evidence-gated live promotions (`validation_passed -> canary_active`, `canary_active -> active`)
  - canonical activation evidence registry (`validation|canary` records with artifact hash/path provenance)
- Rollout control-plane baseline in code:
  - platform-level and bookmaker-level rollout policies (`full|canary|disabled`)
  - platform and bookmaker kill switches with immediate runnable-set exclusion
  - canary cohort controls (`sport`, `competition`, `bookmaker`) for runtime selection
  - admin/internal rollout policy and status endpoints
- Security controls:
  - `GET /odds/refresh/status` restricted by durable DB-backed owner/shared ACL (Redis payload fallback only for pre-migration jobs).
  - refresh ACL decisions are durably audited (`job create`, `share/unshare`, `status access allow/deny`).
  - refresh ACL/audit retention cleanup utility with dry-run default, atomic lock release, and lock/cap guardrails:
    - `python -m api.scripts.cleanup_refresh_acl_retention --audit-retention-days 30 --terminal-job-retention-days 14`
  - cap-breach override is explicit per-run intent only (`--allow-cap-breach`); env/config cannot force-enable it.
  - scheduled automation runner (single-run lock enforced):
    - `python -m api.scripts.run_refresh_acl_retention_automation --max-runs 1 --interval-seconds 0`
  - `/health/scrapers`, `/health/detailed`, and `/health/telemetry` require ops-role or internal-token access; telemetry defaults to aggregate-only response output.
- Unibet remains frozen by baseline policy (`BOOKMAKER_FREEZE_UNIBET=true`, `unibet.is_active=false`).

Still open:
- Matcher API default remains runtime-first; read-model serving is opt-in behind feature flag and not default-on yet.
- Health/audit surfacing remains endpoint-based and needs deeper operational tooling.

## Archive
Historical planning and superseded docs are in `docs/archive`.
