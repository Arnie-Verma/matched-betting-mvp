# ADR-0002: Dynamic Scraper Registry by Bookmaker Config

- Status: Accepted
- Date: 2026-02-10
- Owners: Platform

## Context
Target scale is 100+ bookmakers.
A one-scraper-per-bookmaker model creates excessive duplication and high maintenance cost.

## Decision
Use a dynamic scraper registry:
- `bookmakers.scraping_config.scraper_class` selects adapter class.
- `SCRAPER_CLASSES` maps class names to platform adapters.
- Bookmaker-specific differences live in DB config and narrow transforms.

## Consequences
Benefits:
- faster onboarding for same-platform skins
- less duplicated scraper code
- clearer platform-level ownership

Tradeoffs:
- requires strong config hygiene and validation
- misconfigured `scraper_class` or `base_url` fails at runtime

## Alternatives Considered
1. Hardcoded static scraper map only:
- rejected; does not scale operationally.

2. Full plugin system now:
- deferred; current registry model is simpler and sufficient.

## Follow-ups
- Add code-enforced lifecycle/activation gates before enabling new bookmakers.
- Add onboarding report artifact generation to reduce config mistakes.

