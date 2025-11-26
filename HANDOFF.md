# Matched Betting SaaS - Technical Handoff

## Project Overview

**Product**: Outmatched.com-style matched betting platform (Australian market)
**Stack**: Next.js 14 + FastAPI + PostgreSQL + Redis + Docker
**Business Model**: Freemium SaaS (Free: 2 bookmakers, Premium: 16, Diamond: 103)

Matched betting exploits bookmaker promotions by placing back bets (traditional bookmaker) and lay bets (Betfair exchange) to guarantee profit/minimize loss regardless of outcome.

---

## Quick Start

```bash
# Start services
pnpm dev:up

# Run migrations & seed
docker exec mb_api alembic upgrade head
docker exec mb_api python -m api.scripts.seed_all_bookmakers
docker exec mb_api python -m api.scripts.seed_plans

# Manual scrape (TAB + Betfair)
docker exec mb_api python ../worker/src/manual_scrape.py

# Access
# Frontend: http://localhost:3000
# API: http://localhost:8000/docs
```

---

## Current Status

### ✅ Working
- Authentication (Clerk) + Billing (Stripe)
- TAB scraper: ~7,800 odds per scrape
- Betfair scraper: 60 lay odds per scrape (with liquidity)
- Odds matcher UI with auto-load + filters
- Matching engine (6% commission)
- Event grouping (fuzzy matching)

### 🚧 Todo
- Ladbrokes scraper (complete free tier)
- Premium bookmakers (14 more for Premium tier)
- Refresh button integration
- Remove debug logging

---

## Architecture

### Services
- **mb_api** (8000): FastAPI + PostgreSQL + JWT auth
- **mb_web** (3000): Next.js 14 + Clerk + Tailwind
- **mb_db** (5432): PostgreSQL 16
- **mb_redis** (6379): Redis (future caching)

### Key Files
```
apps/
├── api/src/api/
│   ├── routers/odds_matcher.py      # Main matching endpoint
│   ├── services/matching_engine.py  # PnL calculations
│   └── models/                      # SQLAlchemy models
├── web/src/
│   ├── app/dashboard/odds-matcher/  # Main UI
│   └── components/odds-matcher/     # UI components
└── worker/src/
    ├── scrapers/tab_scraper.py      # TAB scraper
    ├── scrapers/betfair_scraper.py  # Betfair scraper (Playwright)
    └── jobs/save_odds.py            # DB persistence
```

---

## Database Schema (Key Tables)

- **events**: Matches (home_team, away_team, start_time, competition_id)
- **markets**: Betting markets within events (market_type: match_winner, handicap, etc.)
- **selections**: Outcomes within markets (home, away, draw)
- **odds_snapshots**: Time-series odds (decimal_odds, available_amount, is_current, bookmaker_id)
- **bookmakers**: Bookmaker metadata (103 seeded, tier: FREE/PREMIUM/PLATINUM)
- **subscriptions**: User plans (Free: 2, Premium: 16, Diamond: 103 bookmakers)

---

## Scrapers

### TAB Scraper
- **API**: `https://api.beta.tab.com.au/v1/tab-info-service/sports/{Sport}/competitions/{Competition}/matches`
- **Sport codes**: "Soccer" (EPL), "Australian Rules" (AFL), "Rugby League" (NRL)
- **Performance**: ~6s for 20 events, 7,800+ odds
- **Markets**: Scrapes ALL markets (Result, HTResult, H2Result, etc.)

### Betfair Scraper
- **Method**: Playwright browser automation (intercepts network API calls)
- **URL**: `https://www.betfair.com.au/exchange/plus/football/competition/10932509` (EPL)
- **Key fix (Nov 2025)**: Increased wait from 3s to 5s + 1s async delay for response handlers
- **Performance**: ~9s for 20 events, 60 lay odds (3 per event: home/away/draw)
- **Data captured**: `navigation-aggregator` (fixtures) + `bymarket` (odds + liquidity)

**Important**: Betfair responses arrive asynchronously. Must wait 5s + 1s async delay before parsing.

---

## Odds Matcher Logic

### Flow
1. Query events (next 14 days, filtered by sport/bookmaker/search)
2. Filter markets: Only `Result`/`Match Odds`/`H2H` (exclude HTResult, H2Result, combined markets)
3. Group events by normalized name (handles "Man Utd" vs "Man United")
4. Group selections by normalized name
5. Find best back odds (highest) + lay odds (Betfair)
6. Calculate matched bet (commission: 6%)
7. Sort by PnL% (best first: -7% > -10%)

### Market Filter
```python
# Include: Result, Match Winner, Match Odds, H2H
# Exclude: HTResult, H2Result, Result-BothTmScr, Result-OU
Market.name.ilike('%result')
  AND NOT ('%htresult%' OR '%h2result%' OR '%both%' OR '%rou%')
```

### Team Name Normalization
```python
# Handles variations like:
'man united' → 'manutd'
'brighton hovealb' → 'brighton'
'nottinghm forest' → 'nottm forest'
```

---

## API Endpoints

### `GET /odds/matcher`
Main odds matching endpoint.

**Query params**:
- `stake` (default: 100): Back bet amount
- `bet_type` ("normal" | "bonus"): Bet type
- `bookmaker_codes`: Filter by bookmakers (comma-separated)
- `sport_codes`: Filter by sports
- `search`: Event name search

**Returns**: Array of `OddsMatchResponse` with:
- Event details (name, start_time, sport, competition)
- Back bet (bookmaker, odds, stake)
- Lay bet (odds, stake, liability, commission, liquidity)
- PnL (qualifying_loss, pnl_percentage, rating)

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mb_dev

# Clerk Auth
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...

# Stripe
STRIPE_SECRET_KEY=sk_test_...

# API URLs
NEXT_PUBLIC_API_URL=http://localhost:8000      # Browser → API
INTERNAL_API_URL=http://api:8000               # Container → Container
```

---

## Common Commands

```bash
# Docker
pnpm dev:up                 # Start all
pnpm dev:down               # Stop all
pnpm dev:logs               # View logs
docker restart mb_web       # Restart web

# Database
docker exec mb_api alembic upgrade head
docker exec mb_api alembic revision --autogenerate -m "msg"
docker exec -it mb_db psql -U postgres -d mb_dev

# Scraping
docker exec mb_api python ../worker/src/manual_scrape.py
docker exec mb_api python test_tab_scraper.py

# Linting
docker exec mb_web pnpm lint
docker exec mb_web pnpm type-check
```

---

## Recent Changes

### Nov 26, 2025 - Betfair Scraper Fix
**Issue**: Betfair `bymarket` responses arriving after parsing started
**Fix**: Increased wait from 3s to 5s + added 1s async delay
**Files**: `betfair_scraper.py:214, 232`
**Result**: 20 events, 60 odds captured successfully

### Oct 26, 2025 - Selection Matching Fix
**Issue**: "Brighton HoveAlb" not matching "Brighton"
**Fix**: Added team name normalization in selection matching
**Files**: `odds_matcher.py:438-442`

---

## Next Steps

1. **Refresh button**: Connect UI refresh to scraper trigger
2. **Ladbrokes scraper**: Complete free tier (2 bookmakers)
3. **Remove debug logs**: Clean up Betfair debug logging (line 247-248)
4. **Add timestamp**: Show "Last updated: X ago" in UI
5. **Premium bookmakers**: Add Sportsbet, Neds, Pointsbet (16 total)

---

## Troubleshooting

### No odds showing
```bash
# Check if data exists
docker exec mb_db psql -U postgres -d mb_dev -c "SELECT COUNT(*) FROM odds_snapshots WHERE is_current = true;"

# Run fresh scrape
docker exec mb_api python ../worker/src/manual_scrape.py
```

### Betfair scraper fails
- Increase wait time if seeing "No bymarket data found"
- Check logs: `docker logs mb_api | grep -i betfair`
- Common issue: Network responses arrive after timeout

### Web container not starting
```bash
docker logs mb_web --tail 50
docker restart mb_web
# If port conflict: netstat -ano | findstr :3000
```

---

## Notes

- **Seasonality**: AFL out of season (Oct-Mar), focus on EPL which is active
- **Database cleanup**: Old odds deleted immediately to prevent growth (see `save_odds.py:317`)
- **Betfair liquidity**: Stored in `odds_snapshots.available_amount`
- **Commission**: 6% for Australian Betfair users
- **Mock data**: Currently using real scrapers, no mock endpoint needed
