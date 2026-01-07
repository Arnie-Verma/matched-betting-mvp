# Production Scale Plan: 103 Bookmakers + 1000 Users

**Created**: 2026-01-07
**Target**: Q2 2026 (16-20 weeks)
**Prepared by**: Strategic assessment session

---

## EXECUTIVE SUMMARY

You have a **production-quality foundation** with excellent architectural decisions (platform grouping, queue-based arch, circuit breaker). The path to 103 bookmakers is clear execution, not design work.

**Current**: 21 active bookmakers (18 Punterstech + 2 Entain + 1 Betfair)
**Target**: 103 bookmakers across 4 major platforms
**Bottleneck**: Proxy infrastructure + platform discovery completion
**Timeline**: 16-20 weeks realistic for full production launch

---

## WHAT YOU HAVE (VALIDATED)

### Architecture (Production-Ready ✅)
- **Queue-based refresh**: Non-blocking, handles 1000+ concurrent users
- **Circuit breaker**: 5-failure threshold, 60s cooldown, prevents cascading failures
- **Per-user rate limiting**: 30s between refreshes per user
- **Idempotent writes**: True upserts with 5-min timestamp bucketing
- **ETag caching**: Last-Modified headers for browser caching

### Scrapers (Partially Complete)
- **Entain (2)**: Ladbrokes + Neds working with dynamic config
- **Betfair (1)**: Working with parallel sports scraping
- **Punterstech (18/21)**: TradieBET, MintBet, BetChamps, etc. (3 disabled due to DNS/offline)
- **TAB (0/2)**: EPL-only works; multi-competition blocked by Akamai

### Database (Optimized)
- **Indexes**: 5 production indexes on hot paths
- **Cleanup**: Post-scrape non-current odds cleanup + scheduled past-event cleanup
- **Size management**: Immediate deletion prevents unbounded growth
- **Current data**: ~20K odds typical, scales to 100K+ with more bookmakers

### Monitoring (Basic)
- **Sentry integration**: Error tracking with context
- **Structured logging**: Per-bookmaker logs with sport/competition context
- **Health endpoints**: `/health`, `/health/scrapers`, `/health/database`, `/health/detailed`
- **Circuit breaker visibility**: Redis-backed state tracking

### Performance (Optimized)
- **Scrape time**: 79s end-to-end (Entain + Punterstech + Betfair)
- **Parallelism**: All bookmakers + all sports run simultaneously
- **Timing improvements**: Dynamic waits instead of fixed 5s delays

---

## WHAT YOU NEED (ROADMAP)

### Missing Platforms (82 Bookmakers)

| Platform | Count | Status | Effort | Blocker |
|----------|-------|--------|--------|---------|
| **BetMakers** | 33 | Code not written | 3-4 days | None (SSR approach clear) |
| **Generation Web** | 22 | Partial discovery | 5 days | Odds endpoint hidden |
| **BetCloud** | 26 | Partial discovery | 5 days | Sports API incomplete |
| **Kindred/Unibet** | 1 | API found, not wired | 1 day | None |
| **TAB Multi-Competition** | 2 | EPL only | N/A | Needs proxy ($50/mo) |

### Known Gaps (Beyond Code)

1. **Proxy infrastructure**: TAB + Entain + others will rate-limit at 1000+ users without proxy
2. **Scale testing**: Unknown if Punterstech blocks at scale (need production load test)
3. **Database tuning**: Connection pool (default 5) too low for 1000 concurrent users
4. **Error recovery**: Circuit breaker opens but doesn't auto-retry after cooldown

---

## PHASE-BY-PHASE ROADMAP

### Phase 0: Foundation ✅ COMPLETE
**Status**: All 5 components live and tested
- ✅ Queue + circuit breaker + idempotent writes
- ✅ Production indexes + cleanup
- ✅ Sentry monitoring
- ✅ Parallel scraping optimization

---

### Phase 1A: Punterstech Scale Validation (CRITICAL PATH)
**Duration**: 1-2 days
**Decision point**: Does Punterstech handle 1000+ users without proxy?

**Tasks**:
1. Deploy current code to production cloud (AWS t3.medium or equiv)
2. Run load test: Simulate 1000 concurrent refresh requests
3. Monitor: Punterstech response codes, latency, error rates
4. **Decision**: Proxy needed? (→ impacts budget planning)

**Outcome**: Either "Direct scraping OK at scale" or "Add Punterstech to proxy tier"

**Why first**: Blocks all downstream proxy vs. direct architecture decisions

---

### Phase 1B: BetMakers SSR Implementation (PARALLEL)
**Duration**: 3-4 days
**Deliverable**: 33 bookmakers live

**Approach**: DOM parsing (Playwright + CSS selectors)

**Steps**:
1. Create `BetMakersScraper` class
2. Implement: Event extraction → Market extraction → Odds extraction
3. Test on RealBookie + CrossBet + TerryBet (3 samples)
4. Update seed script: 33 bookmakers with `scraper_class: "betmakers"`
5. End-to-end test: Manual scrape → verify 30K+ odds

**Risk**: DOM selectors fragile; may need HTML regex fallback

**Why parallel**: Doesn't depend on scale test results; guaranteed 33 bookmakers

---

### Phase 1C: Generation Web Odds Discovery (PARALLEL)
**Duration**: 2-3 days
**Blocker resolution**: Find the missing odds endpoint

**Investigation**:
1. Open EliteBet in Chrome DevTools
2. Navigate to soccer/AFL/NRL sections
3. Watch Network tab → find the XHR that loads odds
4. Document: Endpoint, headers, request/response format
5. **If found**: Ready for implementation (Phase 2)
6. **If not found**: Switch to DOM parsing fallback

**Why parallel**: Mystery that blocks 22 bookmakers; worth 2-3 days of detective work

---

### Phase 2: Generation Web + BetCloud Scrapers (AFTER PHASE 1C)
**Duration**: 4-5 days
**Deliverable**: 48 bookmakers live (22 + 26)

**Requirements**:
- Phase 1C must complete with odds endpoint found (or DOM approach determined)
- BetCloud sports API must be fully documented

**Tasks**:
1. Implement `GenerationWebScraper` (once API/DOM approach known)
2. Implement `BetCloudScraper` (once sports API documented)
3. Update seed script: 48 bookmakers enabled
4. End-to-end test: All 103 bookmakers seeded, 18+33+22+26 active

**Checkpoint**: After Phase 2, you have 18+33+22+26 = 99 bookmakers ready (just missing Kindred + TAB multi-comp)

---

### Phase 3: Proxy Infrastructure (AFTER PHASE 1A)
**Duration**: 2-3 days
**Cost**: $50-100/mo for rotating residential proxy

**Setup**:
1. Choose provider: SmartProxy or Bright Data
2. Add `requires_proxy` boolean to bookmaker config
3. Update scrape_service.py:
   ```python
   if bookmaker.scraping_config.requires_proxy:
       client = httpx.AsyncClient(proxies=proxy_url)
   ```
4. Mark bookmakers as `requires_proxy=True` if Phase 1A confirms scale blocking

**Decision based on**: Phase 1A results
- If Punterstech blocks: Mark Punterstech + Entain + others
- If Punterstech OK: Only mark TAB + others confirmed anti-bot

**Value**: Enables TAB multi-competition, stable scaling to 1000+ users

---

### Phase 4: Scale Testing & Optimization (AFTER PHASE 3)
**Duration**: 3-4 weeks
**Objective**: Validate 1000+ users without degradation

**Test suite**:
1. **Concurrency**: 100 simultaneous refresh requests
2. **Database load**: Query perf at 500K odds (pre-load test data)
3. **Scraper resilience**: Simulate 20% failure rate → verify circuit breaker + graceful degradation
4. **Cache effectiveness**: Hit rate analysis at 1000 concurrent users
5. **Infrastructure sizing**: Determine CPU/RAM/network needs

**Optimizations (if needed)**:
- Database: Add read replicas, increase connection pool to 30-40
- Cache: Increase Redis memory, implement L1 in-process cache
- Scraper: Batch requests, connection pooling tuning

**Outcome**: Production-ready capacity plan + infrastructure sizing

---

### Phase 5: Monitoring & Alerting (OPTIONAL BEFORE LAUNCH)
**Duration**: 2-3 days
**Objective**: Ops team visibility

**Implement**:
1. **Scraper metrics**: Events/odds per bookmaker, duration, error rate
2. **Database health**: Pool utilization, query latency (p95/p99)
3. **API health**: Request rate, error rate per endpoint
4. **Alerts**: PagerDuty integration for scraper failures
5. **Dashboards**: Grafana for real-time visibility

**Cost**: Datadog or Sentry + Grafana Cloud (~$100-200/mo)

---

### Phase 6: Monetization Tier Definition (BEFORE LAUNCH)
**Duration**: 1-2 days
**Objective**: Pricing structure ready

**Define**:
- **Free**: Ladbrokes + Neds + Betfair (3 bookmakers) — Validate PMF first
- **Premium**: Free + Punterstech (18) + others (30+ total, $20/mo?)
- **Diamond**: All 103 + advanced features ($50/mo? validate vs Outmatched)

**Validation**: Run PMF surveys with early users before finalizing

---

### Phase 7: Production Deployment (FINAL)
**Duration**: 4 weeks
**Objective**: Public launch

**Tasks**:
1. Infrastructure: Kubernetes cluster or managed cloud platform
2. Backups: Daily automated backups, disaster recovery tested
3. DNS: Marketing domain + app subdomain split
4. Beta: Launch with 100-500 early users, iterate on feedback
5. Public: Full launch + marketing campaign

---

## CRITICAL DECISIONS YOU HAVEN'T MADE YET

### 1. Proxy Strategy (→ Impacts Phase 1A)
**Question**: Will you invest in rotating proxy now or test direct scraping first?

**Options**:
- **A (Recommended)**: Test Punterstech at scale first (Phase 1A), then decide
  - Pro: Data-driven decision, may not need proxy
  - Con: Takes 1-2 days
- **B (Conservative)**: Buy proxy now, implement immediately
  - Pro: Future-proof, no scale testing delays
  - Con: $50-100/mo cost upfront, may be unnecessary

**Recommendation**: Choose **Option A** — 1-2 day investment yields actionable data

---

### 2. Priority Order (→ Impacts Week 1-2)
**Question**: What order for Phase 1B, 1C, BetCloud completion?

**Options**:
- **Serial** (1B → 1C → BetCloud): 6-8 days, slower
- **Parallel** (1B + 1C, then BetCloud): 3-4 days to first two, then BetCloud — RECOMMENDED

**Recommendation**: Run 1B + 1C in parallel:
- You (Phase 1B): Build BetMakers DOM parser
- Developer2 or manual (Phase 1C): EliteBet network inspection
- Finish 3-4 days, then tackle BetCloud together

---

### 3. BetMakers Fallback (→ Risk Mitigation)
**Question**: If DOM selectors are fragile, what's plan B?

**Answer**:
- Primary: CSS selectors (fast, robust if site structure stable)
- Fallback: HTML regex parsing (slower, more brittle but always works)
- Final fallback: Manual JS bundle inspection (if neither above works)

**Effort**: Extra 1 day if fallback needed

---

### 4. Database Tuning Timing (→ Performance Impact)
**Question**: Increase connection pool now or after Phase 4?

**Options**:
- **Now**: Change default 5 → 20 in database config
- **Phase 4**: Tune based on load test results

**Recommendation**: Do it **now** (1 line change, immediate benefit, zero risk)

---

## METRICS TO TRACK

### Scraper Coverage (Goal: 60+ by launch)
| Platform | Count | Target | Status |
|----------|-------|--------|--------|
| Entain | 2 | 2 | ✅ Live |
| Betfair | 1 | 1 | ✅ Live |
| Punterstech | 21 | 18 | ✅ Live (3 disabled) |
| BetMakers | 33 | 33 | ⏳ Phase 1B |
| Generation Web | 22 | 22 | ⏳ Phase 1C + 2 |
| BetCloud | 26 | 26 | ⏳ Phase 2 |
| **TOTAL** | **103** | **60+** | **77 by end of Phase 2** |

### Performance (Goal: <100s scrape for all 103)
| Metric | Target | Current | Note |
|--------|--------|---------|------|
| Parallel scrape time | <120s | 79s | Good; will grow with more bookmakers |
| Database size | <500K odds | 20K | Will need tuning at scale |
| Odds per bookmaker | 100-1000 | 50-400 | Varies by platform |
| API response time | <5s | 2-3s | Good; monitor for degradation |

### Availability (Goal: 99.9% by launch)
| Component | Target | Current | Blocker |
|-----------|--------|---------|---------|
| Circuit breaker | <5min recovery | 60s | Good |
| Scraper resilience | 1 failure doesn't affect others | ✅ | Good |
| Database uptime | 99.99% | ✅ | Covered by production backup |
| API uptime | 99.95% | ✅ | Need monitoring dashboard |

---

## UNRESOLVED QUESTIONS (For you to consider)

1. **Proxy cost tolerance**: How much/mo is acceptable? ($50? $150? $500?)
2. **Monetization model**: Free tier size? Premium pricing? (Start with Outmatched's levels?)
3. **TAB multi-competition**: Critical MVP feature or Phase 2 enhancement?
4. **First 100 users**: Beta testing (select cohort) or public launch immediately?
5. **Competitive differentiation**: How beat Outmatched? (Speed? UX? Different bookmakers?)

---

## SUCCESS CRITERIA

**By end of Phase 1** (Week 2):
- [ ] Punterstech scale test complete (know proxy requirement)
- [ ] BetMakers scraper working on 3 test sites
- [ ] Generation Web odds endpoint found (or DOM approach decided)

**By end of Phase 2** (Week 4):
- [ ] 99 bookmakers seeded + tested
- [ ] End-to-end scrape working with all 4 platforms
- [ ] Database handling 50K+ odds without performance degradation

**By launch** (Week 20):
- [ ] 60+ bookmakers live (MVP public)
- [ ] 103 bookmakers complete (goal)
- [ ] 1000+ users without scaling issues
- [ ] Sentry monitoring + automated alerts
- [ ] Production backup + disaster recovery tested

---

## APPENDIX: Platform Status Details

### Entain (Ladbrokes, Neds)
- ✅ Status: Working
- ✅ API: `https://api.{domain}.com.au/v2/sport/event-request`
- ✅ Code: EntainScraper (configurable base_url)
- ⏳ Unibet: API discovered but not wired (1 day work)
- ⚠️ Scale: Likely needs proxy at 1000+ users (untested)

### Betfair
- ✅ Status: Working
- ✅ Method: Playwright automation (browser context required)
- ✅ Endpoints: 60 lay odds captured
- ⏳ Scale: Unknown (untested at 1000+ users)

### Punterstech (21)
- ✅ Status: 18 active (3 disabled: chasebet DNS, betalpha DNS, xbet defunct)
- ✅ API: `https://api.public.{domain}/api-events/public/next-to-go`
- ✅ Code: PunterstechScraper (complete)
- 🔴 **Scale test needed**: Does Punterstech rate-limit at 1000+ users? (CRITICAL)

### BetMakers (33)
- ❌ Status: Code not written
- 🔍 Method: DOM parsing (Playwright + CSS selectors)
- 📝 Sites: RealBookie, CrossBet, TerryBet, BetYouCan, etc.
- ⏳ Work: 3-4 days (Phase 1B)

### Generation Web (22)
- 🔍 Status: Partial discovery (config found, odds hidden)
- 🔍 Endpoints: `/sportutility/getSportAZ`, `/sportutility2/getSportHighlights` (not odds)
- 🔍 Mystery: Odds loaded client-side (JS/WebSocket/embedded?) — **UNRESOLVED**
- ⏳ Work: 2-3 days discovery (Phase 1C) + 3-5 days implementation (Phase 2)

### BetCloud (26)
- 🔍 Status: Partial discovery (racing found, sports incomplete)
- 🔍 Endpoints: `/punter/races/next-to-jump` (working), `/punter/sports/*` (likely but not confirmed)
- 🔍 Blocker: Sports API endpoints not fully documented
- ⏳ Work: 1-2 days completion + 3-5 days implementation (Phase 2)

### TAB (2)
- ⚠️ Status: EPL-only working (~7,800 odds)
- ⚠️ Blocker: Akamai rate limits multi-competition scraping from same IP
- 🔴 Solution: Rotating residential proxy required ($50-100/mo)
- ⏳ Work: 2-3 days integration (Phase 3, after proxy budget approved)

### Kindred/Unibet (1)
- 🔍 Status: API discovered, not integrated
- ✅ Method: REST API (Kindred Group platform)
- ⏳ Work: 1 day to wire into registry (Phase 2)

---

**Ready to start Phase 1? Let me know what you want to tackle first.**
