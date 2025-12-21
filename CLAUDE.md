# CLAUDE.md

Instructions for Claude Code when working in this repository. Be extremely concise. Sacrifice grammar for conciseness.

## Progress Tracking

**REQUIRED**: Update DAILY.md at start and end of each session.

**At session start**:
1. Read DAILY.md to understand current state
2. Add new date section if first session of day
3. Reference previous blockers/next steps

**During session**:
- Add completed tasks under `### Completed`
- Document blockers under `### Blockers`
- Note decisions made (architecture, technical approach, tool choices)

**At session end**:
- Summarize progress
- List next steps for future sessions
- Update blockers if resolved

**Weekly** (Sunday): Compress old entries to keep file focused on current work.

**Format**:
```markdown
## YYYY-MM-DD (Day)

### Completed
- Task with outcome

### Blockers
- Current issues preventing progress

### Next Steps
- Priority tasks for next session
```

---

## Project Overview

Matched betting SaaS platform (Outmatched.com-style) for Australian market.
**Stack**: Next.js 14 + FastAPI + PostgreSQL + Redis + Docker
**Business**: Freemium (Free: 2 bookmakers, Premium: 16, Diamond: 103)

Scrapes odds from bookmakers (TAB) and exchange (Betfair) to find guaranteed profit opportunities by placing back + lay bets.

---

## Architecture

### Services
- **mb_web** (3000): Next.js + Clerk auth + Tailwind
- **mb_api** (8000): FastAPI + PostgreSQL + JWT
- **mb_db** (5432): PostgreSQL 16 + Alembic
- **mb_redis** (6379): Redis cache/queue

### Monorepo Structure
```
apps/
├── web/         # Next.js frontend
├── api/         # FastAPI backend
└── worker/      # Scrapers + background jobs
packages/shared/ # Shared types/utils
infra/dev/       # Docker Compose
```

---

## Quick Start

```bash
# Start services
pnpm dev:up

# Migrations + seed
docker exec mb_api alembic upgrade head
docker exec mb_api python -m api.scripts.seed_all_bookmakers
docker exec mb_api python -m api.scripts.seed_plans

# Manual scrape
docker exec mb_api python ../worker/src/manual_scrape.py

# Access
# http://localhost:3000 - Frontend
# http://localhost:8000/docs - API
```

---

## Common Commands

```bash
# Docker
pnpm dev:down               # Stop all
pnpm dev:logs               # View logs
docker restart mb_web       # Restart service

# Database
docker exec mb_api alembic revision --autogenerate -m "msg"
docker exec -it mb_db psql -U postgres -d mb_dev

# Linting
docker exec mb_web pnpm lint
docker exec mb_web pnpm type-check
```

---

## Database Schema

**odds.py** (main schema):
- `Sport`, `Competition`, `Event` (matches)
- `Market`, `Selection`, `OddsSnapshot` (time-series odds)
- `Bookmaker` (103 seeded with tier: FREE/PREMIUM/PLATINUM)

**subscription.py**: `Plan`, `Subscription` (Stripe integration)
**user.py**: User management (Clerk)

### Tier Structure
Bookmakers stored in `bookmakers.scraping_config` JSON:
- FREE (2): TAB, Ladbrokes
- PREMIUM (14): Sportsbet, Neds, Betfair, Pointsbet, etc.
- PLATINUM (87): All remaining

Premium = Free + Premium (16 total). Diamond = all 103.

---

## Production Engineering

### Monitoring & Error Handling
**Critical for 1000+ users**: Each scraper must enable quick identification and resolution of failures.

**Requirements**:
1. **Structured logging**: `logger.error(f"[{bookmaker_code}] Failed: {sport}/{competition} - {error}")` with bookmaker/sport/competition context
2. **Error isolation**: One bookmaker failure doesn't crash entire scrape
3. **Status tracking**: `ScrapeResult.status` (SUCCESS/PARTIAL/FAILED) + `errors[]` list
4. **Metric logging**: Events scraped, odds count, duration per bookmaker
5. **Alerting-ready**: Log format parseable for monitoring tools (Sentry/Datadog)

**Example log output**:
```
[TAB] Starting scrape: soccer
[TAB] English Premier League: 20 events, 7800 odds (6.2s)
[TAB] ERROR: A-League failed - 403 Forbidden
[TAB] Completed: 20 events, 7800 odds (PARTIAL)
```

### Architecture Principles
**Simplicity for scale**:
1. **Server-side only**: All scraping from single cloud server (not per-user)
2. **Global cache**: 5-15 min TTL shared across all users
3. **Two-tier scraping**: Proxy for anti-bot sites (TAB), direct for easy sites (Betfair)
4. **Graceful degradation**: Missing bookmaker = skip silently, continue others
5. **Idempotent operations**: Re-running scrape safe (upserts, not inserts)

---

## Scrapers

### Base Framework (base.py)
All inherit from `BaseScraper`. Must implement:
- `scrape_sport(sport, limit)` - Main entry
- `parse_event(event_data)` - Parse event
- `parse_odds(odds_data, event)` - Extract odds

Returns: `ScrapeResult` with `ScrapedEvent[]` + `ScrapedOdds[]`

**Production logging pattern**:
```python
self.logger.info(f"[{self.bookmaker_code}] Starting: {sport}")
self.logger.info(f"[{self.bookmaker_code}] {comp}: {len(events)} events")
self.logger.error(f"[{self.bookmaker_code}] Failed {comp}: {error}")
```

### TAB Scraper (tab_scraper.py)
**Status**: EPL-only works (~7,800 odds, ~6s). Multi-competition blocked by Akamai without proxy.

**API**: `https://api.beta.tab.com.au/v1/tab-info-service/sports/{Sport}/competitions/{Competition}/matches?jurisdiction=VIC`

**Discover competition names**:
```bash
curl "https://api.beta.tab.com.au/v1/tab-info-service/sports/{Sport}/competitions?jurisdiction=VIC"
# Example: sports/Soccer/competitions
```

**Sport codes**: "Soccer", "Australian Rules", "Rugby League", "Basketball", "Ice Hockey"

**Competition names** (exact match):
- Soccer: "English Premier League", "A League Men", "Italian Serie A", "Spanish Primera Division", "German Bundesliga", "French Ligue 1", "UEFA Champions League", "Major League Soccer"
- AFL: "AFL"
- NRL: "NRL"
- Basketball: "NBA"
- Hockey: "NHL"

**HATEOAS pattern**: Matches endpoint returns `_links.markets` URLs. Must fetch markets separately (N+1).

### Betfair Scraper (betfair_scraper.py)
**Status**: Working (60 lay odds, ~9s)

**Method**: Playwright browser automation. Intercepts network calls to capture:
- `navigation-aggregator` (fixtures)
- `bymarket` (odds + liquidity)

**URL pattern**: `https://www.betfair.com.au/exchange/plus/{sport-category}/competition/{COMP_ID}`

**Competition IDs** (verified from URLs):
| Competition | ID | Sport Category |
|-------------|-----|----------------|
| EPL | 10932509 | football |
| A-League | 12117172 | football |
| La Liga | 117 | football |
| Bundesliga | 59 | football |
| Serie A | 81 | football |
| Ligue 1 | 55 | football |
| Champions League | 228 | football |
| MLS | 141 | football |
| AFL | 11897406 | australian-rules |
| NRL | 10564377 | rugby-league |
| NBA | 10547864 | basketball |
| NBL | 10533436 | basketball |
| NHL | 12550521 | ice-hockey |
| Boxing | 10817625 | boxing |

**Critical timing**: Wait 5s after page load + 1s async delay for response handlers. Responses arrive asynchronously.

---

## CRITICAL: TAB Scraping Constraints

**Production scale**: 1000+ users sharing same cached odds. Scraper IP/proxy reputation is shared resource.

### Golden Rules
1. **1-3 sec delays** between requests to same domain
2. **Cache 5-15 min TTL** minimum
3. **Sequential requests only** without proxy - never parallel to same bookmaker
4. **Test conservatively** - failed tests burn IP reputation
5. **Rate limit globally** - all users share cache

### What Fails for TAB
**Without proxy**:
- ❌ Sequential multi-competition → Blocked after 3-4 requests (Akamai detects scanning pattern)
- ❌ Parallel requests → First 3-4 work, rest 403 (same detection)
- ❌ Repeated use from same IP → IP blocked after hours/days of use

**Always fails** (even with proxy):
- ❌ Playwright → TRIGGERS Akamai immediately (worse than direct httpx)
- ❌ Cloudflare Workers → Edge IP ranges blocked by TAB

**With rotating proxy**:
- ✅ Parallel OK → Different IP per request prevents pattern detection
- ✅ Sequential OK → Can scrape all competitions reliably

**Root cause**: Akamai detects "bot scanning multiple endpoints from same IP" pattern.

### Outmatched.com Owner (Patrick) - Direct Quotes

**Context**: Reached out to Outmatched.com owner to understand their production architecture.

**On scraping approach**:
> "currently scraping the data myself"

**On cloud infrastructure**:
> "I'm not using my own personal home IP address of course, I'm using a server in the cloud. But even still if you use the same IP they can ban you."

**On rotating proxies for TAB**:
> "So for the websites with more anti bot prevention I have to use a proxy. That's basically somewhere I can send my request and they send it to TAB instead of my IP sending it. That way the IP address appears different to them every time and they can't ban me."

**Confirmed architecture**:
1. Cloud server (not personal IP) - Likely VPS/cloud instance
2. **Rotating residential proxy** for anti-bot sites (TAB, etc.)
3. Direct scraping for easy bookmakers (Betfair)
4. Shows "Performance Notice: TAB may have slower loading times" (acknowledges proxy latency)
5. Legal stance: Scraping generally legal, bookies have "bigger fish to fry"

**Key insight**: Two-tier approach minimizes cost (proxy only for ~20% of bookmakers).

### Recommended Solution
**Option A** (Production): Cloud server + rotating proxy ($15-30/mo)
- SmartProxy/Bright Data for TAB
- Direct requests for Betfair/easy bookmakers
- Two-tier approach minimizes cost

**Option B** (MVP): EPL-only, accept blocking risk, rotate cloud providers

**Option C** (Free): Betfair-only until revenue justifies proxy

### Proxy Decision Framework
**NEEDS PROXY** (403/429 after 3-5 requests):
- TAB (confirmed), Ladbrokes, Sportsbet (likely)

**NO PROXY** (consistent 200 OK):
- Betfair (designed for API access)

Test protocol: 5 sequential requests → 10 burst requests. If any 403 → needs proxy.

**Cost optimization**: 20% bookmakers need proxy (~$30/mo), 80% direct (free) vs 100% proxy ($144/mo).

---

## API Architecture

### Key Routers (apps/api/src/api/routers/)
- `odds_matcher.py` - Main matching endpoint
- `billing.py` - Stripe checkout
- `auth.py` - Clerk webhooks
- `odds_matcher_mock.py` - DELETE when scraping works

### Matching Engine (matching_engine.py)
1. Query events (next 14 days, filtered)
2. Filter markets: Only Result/Match Odds/H2H (exclude HTResult, H2Result, combined)
3. Group events by normalized name ("Man Utd" → "manutd")
4. Find best back (highest) + lay odds (Betfair)
5. Calculate PnL (6% commission)
6. Sort by PnL% (best first: -7% > -10%)

**Market filter**:
```python
Market.name.ilike('%result')
  AND NOT ('%htresult%' OR '%h2result%' OR '%both%' OR '%rou%')
```

### Subscription Service (subscription_service.py)
`get_allowed_bookmakers(user_id)` - Returns bookmakers based on user plan.

---

## Frontend Architecture

### Structure (apps/web/src/)
```
app/
├── dashboard/odds-matcher/   # Main UI
├── billing/                  # Pricing plans
└── api/proxy/               # Backend proxying

components/
├── odds-matcher/
│   ├── OddsMatcherClient.tsx     # Main table + filters
│   └── BetCalculatorModal.tsx    # PnL calculator
└── billing/PricingPlans.tsx
```

### API Proxying
Next.js routes proxy to FastAPI:
```typescript
// Browser → API
NEXT_PUBLIC_API_URL=http://localhost:8000

// Container → Container
INTERNAL_API_URL=http://api:8000
```

---

## Authentication

### Clerk Integration
- Frontend: `@clerk/nextjs` with middleware
- Backend: JWT via `verify_clerk_jwt()`
- Env: `CLERK_SECRET_KEY`, `CLERK_ISSUER`, `MB_AUTH_JWKS_URL`, `MB_AUTH_AUDIENCE`

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mb_dev
REDIS_URL=redis://localhost:6379

# Clerk
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# API URLs
NEXT_PUBLIC_API_URL=http://localhost:8000
INTERNAL_API_URL=http://api:8000

# Future: Proxy (when scaling multi-competition)
# RESIDENTIAL_PROXY_URL=http://user:pass@proxy:port
```

---

## Current Status

### ✅ Working
- TAB scraper: EPL-only, ~7,800 odds
- Betfair scraper: ~60 lay odds with liquidity
- Odds matcher UI + auto-load + filters
- Matching engine (6% commission)
- Auth (Clerk) + Billing (Stripe)

### 🚧 Next
- Rotating proxy for TAB multi-competition scaling
- Ladbrokes scraper (complete free tier)
- Premium bookmakers (14 more)
- Refresh button integration

---

## Important Notes

### Seasonality
- AFL out of season (Oct-Mar)
- Focus on EPL/soccer (currently active)
- All AU bookmakers heavily cover EPL

### Database Cleanup
Old odds deleted immediately to prevent growth (`save_odds.py:317`).

### Scraper Testing
Always test inside Docker containers where dependencies exist.

Database name: `mb_dev` (not `matched_betting`)

---

## Troubleshooting

**No odds showing**:
```bash
docker exec mb_db psql -U postgres -d mb_dev -c "SELECT COUNT(*) FROM odds_snapshots WHERE is_current = true;"
docker exec mb_api python ../worker/src/manual_scrape.py
```

**Betfair fails**: Increase wait time if "No bymarket data found". Check logs: `docker logs mb_api | grep -i betfair`

**Web not starting**: `docker logs mb_web --tail 50 && docker restart mb_web`

---

## Plans

At plan end, list unresolved questions. Extremely concise. Sacrifice grammar for concision.
