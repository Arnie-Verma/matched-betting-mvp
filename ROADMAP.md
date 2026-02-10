# Product Roadmap

## Current Snapshot (2026-02-06)

| Area | Status | Notes |
|------|--------|-------|
| Odds matcher | Working | Refresh + filtering + calculator in place |
| Scraper architecture | Working baseline | Platform-based approach active (Entain, Betfair, Punterstech, Kindred) |
| Validation | Implemented | Non-blocking post-scrape validation integrated |
| Queue/refresh flow | Implemented | Async refresh with status polling |
| Scale operating model | Defined | See `BOOKMAKER_OPERATING_SYSTEM.md` |
| Remaining expansion | In progress | BetCloud, BetMakers, Generation Web, standalone premium books |

## Roadmap Phases

### Phase 1: Hardening (Now)
- Standardize scraper constructor and interface contract across all scraper classes.
- Make per-bookmaker runtime policy config-driven (timeouts/retries/proxy).
- Optimize matcher read path toward current-state/read-model queries.
- Add per-bookmaker SLO dashboards and alert thresholds.

### Phase 2: Platform Expansion
- Implement BetCloud platform adapter.
- Implement BetMakers platform adapter.
- Complete Generation Web odds endpoint discovery and adapter.
- Promote bookmaker onboarding to config + validation wherever possible.

### Phase 3: Proxy Tier And Slow Books
- Isolate proxy-required bookmakers into dedicated queue/class.
- Add explicit slow-book UX notices and partial-result behavior.
- Roll out proxy spend only where direct traffic is not viable.

### Phase 4: Scale Operations
- Canary and ramp controls for bookmaker activation.
- Capacity testing for higher bookmaker counts and concurrent users.
- Auto-degrade and recovery workflow based on breaker/validation signals.

## Working Doc Map
- Strategy and lifecycle: `BOOKMAKER_OPERATING_SYSTEM.md`
- Discovery status: `DISCOVERY_SUMMARY.md`
- Implementation playbook: `BOOKMAKER_IMPLEMENTATION_GUIDE.md`
- Validation model: `VALIDATION_FRAMEWORK.md`
- Deployment/runtime: `PRODUCTION_NOTES.md`
- Active progress log: `DAILY.md`

## Archived Plans
Historical phase plans and decision docs moved to `docs/archive`.
