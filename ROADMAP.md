# Production Roadmap

## Current State Summary

| Category | Status | Details |
|----------|--------|---------|
| **Odds Matcher** | Working | Real-time opportunities, filtering, calculator |
| **Scrapers** | 2/103 | Ladbrokes + Betfair (need Neds to complete free tier) |
| **Academy** | Built | 6 modules, ~60 lessons, needs content review |
| **Billing** | Working | Stripe integration, 3 tiers |
| **Auth** | Working | Clerk integration |
| **Dashboard** | Partial | Coming Soon placeholders for tracking features |
| **IP Protection** | Planned | Cloud hosting + rotating proxy for anti-bot sites |

---

## Infrastructure & Hosting Overview

### Architecture (Production)
```
Your Laptop (dev only)
    ↓ pushes code to GitHub
    ↓
Cloud Hosting (Railway/Render) ← All scraping happens here
    ├── Direct → Betfair, Ladbrokes, Neds (no proxy needed)
    └── Rotating Proxy → TAB, Sportsbet, anti-bot sites ($30/mo)
```

### Monthly Costs by Stage

| Stage | Services | Cost |
|-------|----------|------|
| **MVP Launch** | Vercel (free) + Railway ($5) + Supabase (free) + Upstash (free) + Domain ($1) | ~$6/mo |
| **Premium Tier** | + Rotating proxy for TAB | ~$40/mo |
| **Scale (1000 users)** | + More compute + monitoring | ~$100-150/mo |

### Accounts to Create (All Free to Start)
- [ ] **Vercel** - Next.js frontend hosting
- [ ] **Railway** or **Render** - FastAPI backend hosting
- [ ] **Supabase** - Managed PostgreSQL
- [ ] **Upstash** - Managed Redis
- [ ] **Domain registrar** - Namecheap/Cloudflare (~$12/year)
- [ ] **SmartProxy** (later) - Rotating residential proxy for anti-bot sites

---

## Phase 1: MVP Launch (Complete Free Tier)

**Goal**: Launch with Free tier fully functional - users can find opportunities with Ladbrokes + Betfair

### 1.1 Complete Neds Scraper
- [ ] Neds uses same Entain platform as Ladbrokes
- [ ] Refactor `LadbrokesScraper` → `EntainScraper(base_url)`
- [ ] Test with Neds base URL
- [ ] Update seed script if needed

### 1.2 Content Review
- [ ] Review Academy content - ensure tutorials are accurate
- [ ] Review "How It Works" page calculations
- [ ] Update pricing page descriptions to match actual features
- [ ] Remove/hide "Coming Soon" features from plan descriptions if not launching

### 1.3 Billing Flow Testing
- [ ] Test Stripe checkout flow end-to-end (test mode)
- [ ] Verify webhook creates subscription in DB
- [ ] Test upgrade/downgrade between plans
- [ ] Test cancellation flow
- [ ] Verify bookmaker access changes with subscription tier

### 1.4 Polish & Bug Fixes
- [ ] Mobile responsiveness check on all pages
- [ ] Fix any console errors/warnings
- [ ] Loading states for all async operations
- [ ] Error handling for failed scrapes (graceful degradation)
- [ ] Empty state messaging when no opportunities found

### 1.5 Production Deployment
- [ ] Buy domain (~$12/year)
- [ ] Create accounts: Vercel, Railway, Supabase, Upstash (free)
- [ ] Deploy API to Railway (add env vars, auto-deploys from GitHub)
- [ ] Deploy web to Vercel (add env vars, connect domain)
- [ ] Set up Supabase PostgreSQL, get connection string
- [ ] Set up Upstash Redis, get connection string
- [ ] Configure production Clerk instance
- [ ] Configure production Stripe (live keys + webhooks)
- [ ] Run database migrations & seeds
- [ ] DNS configuration (point domain to Vercel)
- [ ] SSL verification (automatic via Vercel)
- [ ] Run first production scrape
- [ ] Smoke test all user flows

---

## Phase 2: Premium Tier (Expand Bookmakers)

**Goal**: Add 14 more bookmakers to justify Premium subscription

### 2.1 Platform Scrapers (2-3 weeks)
Build scrapers by platform (not individual bookmaker):

| Platform | Bookmakers | Priority | Complexity |
|----------|------------|----------|------------|
| Entain | Ladbrokes, Neds, Bookmaker | Done/Easy | Low |
| BetMakers | 33 bookmakers | High | Medium |
| Punterstech | 21 bookmakers | High | Medium |
| Generation Web | 22 bookmakers | Medium | Medium |
| TAB | TAB, UBET | High | High (needs proxy) |

Order of implementation:
1. **Entain** (Neds) - same as Ladbrokes, easy win
2. **TAB** - already built, needs proxy setup ($30/mo)
3. **BetMakers** - covers Sportsbet, Unibet, and many others
4. **Punterstech** - covers Palmerbet, TopSport, etc.

### 2.2 Proxy Infrastructure (1 day)
- [ ] Sign up for SmartProxy/Bright Data (~$30/mo)
- [ ] Add `RESIDENTIAL_PROXY_URL` env var
- [ ] Implement proxy router in scrape service
- [ ] Test TAB scraper with proxy
- [ ] Document which bookmakers need proxy

### 2.3 Scraper Reliability (ongoing)
- [ ] Circuit breaker for failing bookmakers
- [ ] Structured logging for monitoring
- [ ] Sentry integration for error tracking
- [ ] Scraper health dashboard (internal)

---

## Phase 3: User Features

**Goal**: Add features that increase retention and justify subscription

### 3.1 Bet Tracker (1 week)
- [ ] Database schema for bets (event, stake, odds, outcome)
- [ ] API endpoints: create, list, update bet
- [ ] UI: Bet history table with filters
- [ ] UI: Add bet from calculator modal
- [ ] Profit/loss summary dashboard
- [ ] Export to CSV

### 3.2 Bookmaker Balance Tracker (0.5 week)
- [ ] Database schema for balances
- [ ] Manual entry UI (no auto-sync)
- [ ] Balance history chart
- [ ] Low balance warnings

### 3.3 Profit Alerts (0.5 week)
- [ ] Email notification when high-profit opportunity appears
- [ ] Configurable thresholds (e.g., >5% profit)
- [ ] Rate limiting to avoid spam
- [ ] Unsubscribe option

---

## Phase 4: Growth & Optimization

### 4.1 Performance
- [ ] Move scrapers to dedicated worker container
- [ ] Enable `SCRAPER_BATCH_SIZE=6` in production
- [ ] WebSocket for real-time odds updates
- [ ] CDN for static assets

### 4.2 SEO & Marketing
- [ ] Blog post pages (individual routes)
- [ ] Meta tags for all pages
- [ ] Sitemap.xml
- [ ] robots.txt
- [ ] Google Analytics / Plausible

### 4.3 Platinum Tier Features
- [ ] API access for power users
- [ ] Bulk bet export
- [ ] Advanced filters (min liquidity, max stake)
- [ ] Priority support channel

---

## Phase 5: Scale (100+ Bookmakers)

### 5.1 Complete Platform Coverage
- [ ] BetCloud platform (26 bookmakers)
- [ ] Remaining standalone bookmakers (~15)
- [ ] Total: 103 bookmakers

### 5.2 Infrastructure Scale
- [ ] Multiple scraper workers
- [ ] Horizontal API scaling
- [ ] Database read replicas
- [ ] Multi-region deployment (AU-first)

---

## Suggested Next Steps (Prioritized)

### Step 1: Neds Scraper (Completes Free Tier)
**Why first**: Easiest win - same platform as Ladbrokes, just different base URL
```
Effort: 1 day | Impact: Free tier complete with 3 bookmakers
```

### Step 2: Test Billing Flow Locally
**Why**: Must verify payments work before asking real users for money
```
Effort: 0.5 day | Impact: Confidence in revenue flow
- Test Stripe checkout (test mode)
- Verify webhook creates subscription
- Confirm bookmaker access changes with tier
```

### Step 3: Create Hosting Accounts
**Why**: Free, takes 30 min, removes mental blocker
```
Effort: 30 min | Impact: Ready to deploy when code is ready
- Sign up: Vercel, Railway, Supabase, Upstash
- No configuration yet, just accounts
```

### Step 4: Buy Domain
**Why**: Cheap ($12), secures your brand name
```
Effort: 10 min | Impact: Professional presence, required for Stripe live mode
- Namecheap or Cloudflare
- Pick: yourbrand.com or yourbrand.com.au
```

### Step 5: Content Review Pass
**Why**: Academy accuracy matters for user trust
```
Effort: 1 day | Impact: Users can learn matched betting correctly
- Skim Academy modules for obvious errors
- Verify calculator math examples
```

### Step 6: Deploy to Production
**Why**: Get it live, iterate from there
```
Effort: 2-3 hours | Impact: LIVE PRODUCT
- Connect GitHub repos to Vercel/Railway
- Add environment variables
- Run migrations & seeds
- Configure domain DNS
```

### Step 7: Smoke Test & Launch
**Why**: Verify everything works in production
```
Effort: 1-2 hours | Impact: Confidence to share with users
- Sign up flow
- Odds matcher loads
- Calculator works
- Billing flow (live Stripe test)
```

---

## After Launch (Revenue Phase)

### Step 8: Add Rotating Proxy + TAB
```
Cost: $30/mo | Impact: Premium tier viable
- Sign up SmartProxy
- Add RESIDENTIAL_PROXY_URL env var
- Enable TAB scraper
```

### Step 9: BetMakers Platform Scraper
```
Effort: 3-5 days | Impact: +33 bookmakers (Sportsbet, Unibet, etc.)
```

### Step 10: Bet Tracker Feature
```
Effort: 1 week | Impact: User retention, stickiness
```

---

## Timeline Summary

| Step | What | When |
|------|------|------|
| 1-2 | Neds + Billing test | Day 1-2 |
| 3-4 | Accounts + Domain | Day 2 (30 min) |
| 5 | Content review | Day 3 |
| 6-7 | Deploy + Launch | Day 4-5 |
| 8-10 | Premium features | Week 2+ |

**You could be live in 5 days.**

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Scraper blocked | Proxy fallback, multiple platforms for redundancy |
| Stripe issues | Test mode validation, webhook retry logic |
| Scale issues | Start with Free tier only, gate Premium access |
| Content accuracy | Mark Academy as "Beta", iterate based on feedback |

---

## Quick Reference: What's Done vs Not Done

### Done
- Odds matcher UI + matching engine
- Bet calculator modal
- Ladbrokes + Betfair scrapers
- Academy structure (6 modules)
- Billing integration (Stripe)
- Auth integration (Clerk)
- How It Works page
- Blog index

### Not Done (MVP)
- Neds scraper (easy)
- Production deployment
- Billing flow testing
- Content accuracy review

### Not Done (Post-MVP)
- Bet tracking
- Balance tracking
- Profit alerts
- 100+ bookmakers
- Mobile app
- API access

---

## Files Reference

| Purpose | File |
|---------|------|
| Scraper strategy | [SCRAPER_STRATEGY.md](SCRAPER_STRATEGY.md) |
| Production config | [PRODUCTION_NOTES.md](PRODUCTION_NOTES.md) |
| Daily progress | [DAILY.md](DAILY.md) |
| Codebase guide | [CLAUDE.md](CLAUDE.md) |
| This roadmap | [ROADMAP.md](ROADMAP.md) |
