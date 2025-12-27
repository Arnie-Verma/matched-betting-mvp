# Production Deployment Notes

Configuration changes and considerations for deploying to production.

---

## Environment Variables

### Scraping Performance

| Variable | Dev Value | Production Value | Notes |
|----------|-----------|------------------|-------|
| `SCRAPER_BATCH_SIZE` | `1` | `6` | Parallel sports per bookmaker. Docker can't handle >1, cloud servers can. |
| `BOOKMAKER_TIMEOUT_SECONDS` | `25` | `15-20` | Can reduce with faster cloud network |
| `BOOKMAKER_BREAKER_THRESHOLD` | `5` | `3` | Fail faster in production |
| `BOOKMAKER_BREAKER_COOLDOWN_SECONDS` | `60` | `120` | Longer cooldown to avoid hammering failing services |

### Proxy Configuration (Required for TAB)

```bash
# Rotating residential proxy for anti-bot bookmakers
RESIDENTIAL_PROXY_URL=http://user:pass@proxy.smartproxy.com:port

# Proxy-required bookmakers (add as implemented)
PROXY_BOOKMAKERS=tab,sportsbet,pointsbet
```

**Recommended providers** (~$30/mo for matched betting scale):
- SmartProxy (residential)
- Bright Data (residential)
- Oxylabs (residential)

### Database

| Variable | Dev Value | Production Value |
|----------|-----------|------------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@db:5432/mb_dev` | Use managed PostgreSQL (Supabase, RDS, etc.) |
| `REDIS_URL` | `redis://redis:6379/0` | Use managed Redis (Upstash, ElastiCache, etc.) |

### Security

```bash
# Generate new secrets for production
CLERK_SECRET_KEY=sk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Restrict CORS
CORS_ORIGINS=https://yourdomain.com
```

---

## Scraper-Specific Notes

### Currently Implemented

| Scraper | Proxy Needed | Status | Notes |
|---------|--------------|--------|-------|
| Betfair | No | Ready | Exchange API is scrape-friendly |
| Ladbrokes | No | Ready | API works without proxy currently |
| TAB | **Yes** | Disabled | Akamai blocks after 3-4 requests from same IP |

### Future Bookmakers

| Bookmaker | Likely Proxy Needed | Tier |
|-----------|---------------------|------|
| Neds | No (same as Ladbrokes) | FREE |
| Sportsbet | Probably | PREMIUM |
| Pointsbet | Probably | PREMIUM |
| Unibet | Probably | PREMIUM |
| bet365 | Yes (aggressive anti-bot) | PREMIUM |

**Test protocol**: 5 sequential requests + 10 burst requests. If any 403 → needs proxy.

---

## Infrastructure

### Recommended Stack

| Component | Dev | Production |
|-----------|-----|------------|
| Web hosting | Docker local | Vercel (Next.js) |
| API hosting | Docker local | Railway / Render / Fly.io |
| Database | Docker PostgreSQL | Supabase / PlanetScale |
| Redis | Docker Redis | Upstash (serverless) |
| Scraper workers | Same container | Dedicated container with more RAM |

### Resource Requirements

**Scraper container**:
- Minimum: 2GB RAM, 2 vCPU (for parallel Playwright browsers)
- Recommended: 4GB RAM, 4 vCPU (handles batch_size=6 comfortably)

**API container**:
- Minimum: 512MB RAM, 1 vCPU
- Scales horizontally as needed

---

## Performance Tuning

### Current Dev Performance
- Total scrape: ~92s (2 bookmakers × 6 sports, batch_size=1)
- Ladbrokes: ~43s solo
- Betfair: ~89s solo

### Expected Production Performance (batch_size=6)
- Total scrape: ~15-20s (parallel sports + parallel bookmakers)
- Each bookmaker: ~10-15s (all 6 sports truly parallel)

### Caching Strategy

| Cache | TTL | Purpose |
|-------|-----|---------|
| Odds data | 5 min | Prevent redundant scrapes |
| ETag/Last-Modified | Per response | Client-side cache validation |
| Rate limit keys | 60s | Per-user rate limiting |
| Circuit breaker | 120s | Bookmaker health tracking |

---

## Monitoring & Alerting

### Recommended Setup

1. **Sentry** - Error tracking
   - Capture scraper failures
   - Track circuit breaker opens
   - Monitor timeout rates

2. **Uptime monitoring** - Pingdom/UptimeRobot
   - `/health` endpoint on API
   - Alert on downtime

3. **Log aggregation** - Datadog/LogTail
   - Scraper timing logs (already structured)
   - Error patterns by bookmaker

### Key Metrics to Track

```
# Scraper health
scrape_duration_seconds{bookmaker}
scrape_events_count{bookmaker, sport}
scrape_errors_total{bookmaker, error_type}
circuit_breaker_state{bookmaker}

# API health
request_duration_seconds{endpoint}
active_users_count
odds_freshness_seconds
```

---

## Security Checklist

- [ ] Rotate all secrets (Clerk, Stripe, DB passwords)
- [ ] Enable HTTPS only
- [ ] Restrict CORS to production domain
- [ ] Set up rate limiting at API gateway level
- [ ] Configure WAF rules (Cloudflare/AWS WAF)
- [ ] Enable database SSL
- [ ] Set up backup schedule for PostgreSQL
- [ ] Review Clerk webhook signature verification

---

## Database Migrations

Run before first production deploy:

```bash
# Inside API container
alembic upgrade head

# Seed bookmakers
python -m api.scripts.seed_all_bookmakers
python -m api.scripts.seed_plans
```

---

## Launch Checklist

### Pre-launch
- [ ] All environment variables set
- [ ] Database migrated and seeded
- [ ] Stripe webhooks configured for production
- [ ] Clerk production instance configured
- [ ] Domain DNS configured
- [ ] SSL certificates active

### Post-launch
- [ ] Run manual scrape to populate initial odds
- [ ] Verify frontend loads odds correctly
- [ ] Test signup/login flow
- [ ] Test subscription purchase flow
- [ ] Monitor first 24h for errors

---

## Cost Estimates

| Service | Monthly Cost | Notes |
|---------|--------------|-------|
| Vercel (web) | $0-20 | Free tier usually sufficient |
| Railway (API) | $5-20 | Based on usage |
| Supabase (DB) | $0-25 | Free tier has 500MB |
| Upstash (Redis) | $0-10 | Pay per request |
| Rotating proxy | $30-50 | Only needed for TAB/anti-bot sites |
| **Total** | **~$35-125/mo** | Scales with traffic |

---

## Rollback Plan

If issues occur after deployment:

1. **API issues**: Railway/Render have instant rollback
2. **Database issues**: Restore from backup, run `alembic downgrade -1`
3. **Scraper issues**: Can disable individual bookmakers via env var without redeploy

```bash
# Disable problematic bookmaker
DISABLED_BOOKMAKERS=tab,sportsbet
```

---

## Future Improvements (Post-Launch)

1. **Dynamic waits** - Replace fixed 5s waits with networkidle detection
2. **Scraper scheduling** - Cron-based background scraping (every 5 min)
3. **WebSocket updates** - Push new odds to connected clients
4. **Multi-region** - Deploy scrapers in AU region for lower latency
5. **Horizontal scaling** - Multiple scraper workers for more bookmakers
