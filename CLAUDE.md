# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Monorepo for an Outmatched.com-style matched betting SaaS platform targeting Australian sports betting markets. The platform scrapes odds from 100+ Australian bookmakers, matches back/lay opportunities, and provides calculators for matched betting strategies.

## Architecture

### Monorepo Structure
- **apps/web** - Next.js 14 + Tailwind + shadcn UI components + Clerk auth
- **apps/api** - FastAPI (Python) REST API with JWT authentication
- **apps/worker** - Python workers for bookmaker scraping and background jobs
- **packages/shared** - Shared types/schemas/utils (currently minimal)
- **infra/dev** - Docker Compose for local development

### Key Services
- **mb_web** (port 3000) - Next.js frontend with Server Components + API routes for proxying
- **mb_api** (port 8000) - FastAPI backend with PostgreSQL + Redis
- **mb_db** (port 5432) - PostgreSQL 16 with Alembic migrations
- **mb_redis** (port 6379) - Redis for caching and queue management

## Development Commands

### Docker Operations
```bash
# Start all services (from repo root)
pnpm dev:up

# Stop and remove volumes
pnpm dev:down

# View logs for api + web
pnpm dev:logs

# Check running containers
pnpm dev:ps
```

### Database Migrations
```bash
# Run migrations (inside mb_api container)
docker exec mb_api alembic upgrade head

# Create new migration
docker exec mb_api alembic revision --autogenerate -m "description"

# Seed database
docker exec mb_api python -m api.scripts.seed_all_bookmakers
docker exec mb_api python -m api.scripts.seed_plans
```

### Testing Scrapers
```bash
# Test TAB scraper (inside container where dependencies exist)
docker exec mb_api python test_tab_scraper.py

# Or run inside container
docker exec -it mb_api bash
python test_tab_scraper.py
```

### Web Development
```bash
# Linting (from apps/web)
pnpm lint

# Type checking
pnpm type-check

# These can also be run via Docker:
docker exec mb_web pnpm lint
docker exec mb_web pnpm type-check
```

## Database Schema

### Core Models (apps/api/src/api/models/)

**odds.py** - Primary odds and betting schema:
- `Sport` - Sports taxonomy (AFL, NRL, Soccer, etc.)
- `Competition` - Leagues/tournaments within sports (EPL, NBA, etc.)
- `Event` - Individual matches/games with team/venue data
- `Market` - Betting markets (match_winner, handicap, total_points)
- `Selection` - Outcomes within markets (home/away/draw)
- `OddsSnapshot` - Time-series odds data from bookmakers
- `Bookmaker` - Bookmaker metadata with tier structure

**subscription.py** - Billing and plans:
- `Plan` - Pricing tiers (Free: 2 bookmakers, Premium: 16, Diamond: 103)
- `Subscription` - User subscription status with Stripe integration

**user.py** - User management with Clerk integration

### Tier Structure
Bookmakers are organized in cumulative tiers stored in `bookmakers.scraping_config` JSON field:
- **FREE** (2 active): TAB, Ladbrokes
- **PREMIUM** (14 inactive): Sportsbet, Neds, Betfair, Pointsbet, UniBet, etc.
- **PLATINUM** (87 inactive): All remaining bookmakers

Premium users get Free + Premium bookmakers (16 total). Diamond users get all 103.

## Scraping Architecture

### Base Framework (apps/worker/src/scrapers/base.py)

All scrapers inherit from `BaseScraper` and return standardized data structures:
- `ScrapedEvent` - Event with home/away teams, start time, sport, competition
- `ScrapedOdds` - Individual odds with market type, selection, decimal odds
- `ScrapeResult` - Complete scrape result with status, errors, event count

### Scraper Implementation Pattern

Each scraper must implement:
1. `scrape_sport(sport: str, limit: Optional[int])` - Main entry point
2. `parse_event(event_data: Dict)` - Parse event from API/HTML
3. `parse_odds(odds_data)` - Extract odds from bookmaker format

### Anti-Bot Handling (TAB Example)

TAB uses extensive anti-bot protection requiring:
- Browser-like headers (User-Agent, Origin, Referer, sec-ch-ua, sec-fetch-*)
- Session cookies (_tgpc, bm_sz, _abck, ak_bmsc)
- Jurisdiction parameter (VIC, NSW, QLD)

Reference: Outmatched.com.au successfully scrapes TAB with banner "Performance Notice: TAB may have slower loading times due to strong anti-bot measures."

For TAB and similar bookmakers, use Playwright/browser automation to handle cookies automatically.

### TAB API Structure

- Base: `https://api.beta.tab.com.au`
- Endpoint: `/v1/tab-info-service/sports/{Sport}/competitions/{Competition}/matches?jurisdiction=VIC`
- Sports use capitalized names: "Soccer", "Australian Rules", "Rugby League"
- Response has `matches[]` with `contestants[]` (HOME/AWAY), `markets[]`, `propositions[]`
- Odds field: `returnWin` (decimal format)

## Authentication

### Clerk Integration
- Frontend: `@clerk/nextjs` with middleware protection
- Backend: JWT validation via `api.core.auth.verify_clerk_jwt()`
- Environment variables: `CLERK_SECRET_KEY`, `CLERK_ISSUER`, `MB_AUTH_JWKS_URL`, `MB_AUTH_AUDIENCE`

### Protected Routes
API routes use `verify_clerk_jwt()` dependency to extract user ID from JWT.

## API Architecture

### Router Organization (apps/api/src/api/routers/)
- `auth.py` - Clerk webhook handlers
- `billing.py` - Stripe checkout, plans, subscriptions
- `stripe_webhooks.py` - Stripe webhook handlers
- `odds_matcher.py` - Real odds matching endpoint
- `odds_matcher_mock.py` - Mock data (DELETE when scraping works)
- `plan_demo.py` - Plan enforcement demo

### Subscription Service (apps/api/src/api/services/subscription_service.py)
- `get_allowed_bookmakers(user_id)` - Returns cumulative bookmaker list based on plan
- Plan enforcement at API level for odds filtering

### Matching Engine (apps/api/src/api/services/matching_engine.py)
Calculates matched betting opportunities:
- Filters by minimum profit, stake range, bet type
- Calculates commission-adjusted lay stakes
- Returns sorted opportunities by profit percentage

## Frontend Architecture

### Next.js App Router Structure (apps/web/src/app/)
- `dashboard/` - Protected dashboard pages
- `dashboard/odds-matcher/` - Main odds matching UI
- `billing/` - Pricing plans and subscription management
- `api/proxy/` - API route handlers for backend proxying

### Key Components (apps/web/src/components/)
- `odds-matcher/OddsMatcherClient.tsx` - Main odds table with filters
- `odds-matcher/BetCalculatorModal.tsx` - Interactive bet calculator
- `billing/PricingPlans.tsx` - Clean pricing cards matching Outmatched style
- `navigation/PostLoginHeader.tsx` - Dashboard navigation

### API Proxying Pattern
Frontend uses Next.js API routes to proxy to FastAPI:
```typescript
// apps/web/src/app/api/proxy/odds/matcher/route.ts
const response = await fetch(`${INTERNAL_API_URL}/odds/matcher`, {
  headers: { Authorization: `Bearer ${token}` }
});
```

Uses `INTERNAL_API_URL=http://api:8000` for container-to-container communication.

## Current Development Status

### Completed
- Database schema with 103 bookmakers + 3 pricing plans seeded
- Billing UI with Stripe integration
- Odds Matcher UI with mock data
- Worker scraping framework with BaseScraper
- TAB scraper updated with real API structure

### In Progress
- TAB scraper anti-bot handling (needs Playwright or similar)
- Real odds data integration (currently using mock endpoint)

### Pending
- Ladbrokes scraper API discovery
- Betfair API setup (requires SSL cert authentication)
- Database integration (save_odds.py to persist scraped data)
- Switch UI from /matcher-mock to /matcher endpoint
- Activate additional bookmakers for Premium/Diamond tiers

## Important Notes

### Seasonality
- AFL is out of season (October) - focus on EPL/Soccer which is currently active
- All Australian bookmakers heavily cover EPL with high Betfair liquidity

### Mock Data
The Odds Matcher currently uses `/api/proxy/odds/matcher-mock` endpoint. When real scraping works:
1. Update `apps/web/src/components/odds-matcher/OddsMatcherClient.tsx` to use `/matcher`
2. Delete `apps/api/src/api/routers/odds_matcher_mock.py`
3. Remove router from `apps/api/src/api/main.py`

### Scraper Testing
Always test scrapers inside Docker containers where dependencies (httpx, playwright, tenacity) are installed. Don't run locally unless you've installed all dependencies.

### Database Naming
The database is named `mb_dev`, not `matched_betting`. Use:
```bash
docker exec -it mb_db psql -U postgres -d mb_dev
```

## Environment Variables

Required in `.env` file (repo root):
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `CLERK_SECRET_KEY` - Clerk authentication
- `CLERK_ISSUER` - Clerk JWT issuer
- `MB_AUTH_JWKS_URL` - Clerk JWKS endpoint
- `MB_AUTH_AUDIENCE` - Clerk audience
- `STRIPE_SECRET_KEY` - Stripe API key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signing
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` - Clerk frontend key
- `NEXT_PUBLIC_API_URL` - Frontend to API URL (http://localhost:8000)
- `INTERNAL_API_URL` - Container-to-container URL (http://api:8000)
