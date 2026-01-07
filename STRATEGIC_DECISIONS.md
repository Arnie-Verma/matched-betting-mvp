# Strategic Decisions Required (Before Starting Phase 1)

**Purpose**: Clarify dependencies before beginning implementation roadmap
**Created**: 2026-01-07

---

## DECISION #1: Proxy Investment Strategy

**Context**: TAB needs proxy ($50-100/mo). Likely Entain/others do too at scale.

### Question
Should you:
- **A) Test first, then decide** (Run Phase 1A scale test with Punterstech, then commit to proxy)
  - Timeline: +1-2 days discovery
  - Outcome: Data-driven decision (maybe you don't need proxy!)
  - Risk: Delayed proxy launch if needed

- **B) Buy proxy now** (Assume needed, implement immediately)
  - Timeline: No delay
  - Outcome: Future-proof regardless
  - Risk: $50-100/mo upfront cost (may not need it)

### Recommendation
**Choose A** — The 1-2 day investment in Phase 1A will give you:
1. **If Punterstech blocks at scale**: "We need proxy for all anti-bot sites" → proceed with Phase 3
2. **If Punterstech doesn't block**: "We can go direct" → save $50-100/mo, skip proxy phase

**Action item**: Before Phase 1B, run load test on cloud server with 1000 concurrent users

---

## DECISION #2: Execution Order (Week 1-2)

**Context**: You need to cover 82 missing bookmakers. Multiple paths possible.

### Question
Should you run discovery/implementation:
- **Serial**: 1B → Done (3-4d) → 1C → Done (2-3d) → BetCloud (1-2d) = 6-8 days total
  - Pros: One person can do all
  - Cons: Slower time-to-bookmakers, cascading delays

- **Parallel**: 1B (you: 3-4d) + 1C (manual discovery: 2-3d) + BetCloud (1-2d, concurrent)
  - Pros: 3-4 days to 33+22 bookmakers (55 total!)
  - Cons: Requires 2 people or split focus

### Recommendation
**Choose Parallel** — Attack with full force:
- **You**: Build BetMakersScraper (3-4 days work)
  - Start with RealBookie, CrossBet, TerryBet
  - Implement DOM parsing for events/markets/odds
  - Add to registry, enable all 33, test end-to-end

- **Parallel (manual work, minimal code)**:
  - EliteBet browser inspection for Generation Web odds endpoint (2-3 days)
  - BetCloud sports API completion testing (1-2 days)

- **Outcome by end of Week 2**:
  - 33 BetMakers live (just coded)
  - 22 Generation Web ready to code (endpoint found or DOM approach confirmed)
  - 26 BetCloud ready to code (sports API documented)

**Action item**: Decide if you have 2nd person or can handle both Phase 1B + manual discovery

---

## DECISION #3: BetMakers Risk Mitigation

**Context**: BetMakers uses DOM parsing, which may break if selectors change.

### Question
If BetMakers CSS selectors fail, do you:
- **A) Accept fragility** - Use selectors, update as needed
  - Pros: 80% uptime, rarely breaks
  - Cons: Requires manual fixes when site changes

- **B) Build fallback** - HTML regex parsing (slower but always works)
  - Pros: 99% uptime, never breaks
  - Cons: +1 day extra work, slightly slower scrapes

- **C) Hybrid** - Selectors + fallback logic
  - Pros: Best of both (fast + reliable)
  - Cons: +1-2 days extra work initially

### Recommendation
**Choose C (Hybrid)** for production reliability:
```python
try:
    odds = extract_with_selectors(html)  # Fast
except:
    odds = extract_with_regex(html)  # Fallback
```
- Extra 1 day work now saves 10+ days firefighting later
- By Phase 1B completion: You have 33 bulletproof bookmakers

**Action item**: When building BetMakersScraper, add regex fallback alongside selectors

---

## DECISION #4: Database Connection Pool

**Context**: Default pool size = 5 connections. At 1000+ concurrent users, this is bottleneck.

### Question
Should you:
- **Now**: Change default 5 → 20 connections in `database.py`
  - Effort: 1 line change
  - Risk: Zero (backward compatible)
  - Benefit: Immediate improvement

- **Phase 4**: Tune based on load test results
  - Benefit: Data-driven sizing
  - Risk: Suboptimal until Phase 4

### Recommendation
**Choose Now** — Do it today, no downside:
```python
# apps/api/src/api/core/database.py
pool_size = 20  # was 5
max_overflow = 10
```

This gives you headroom for Phase 4 load tests.

**Action item**: Change `pool_size` in database.py before Phase 1A

---

## DECISION #5: TAB Multi-Competition

**Context**: TAB EPL-only is limiting. Multi-competition needs proxy.

### Question
For public launch, is TAB multi-competition:
- **MVP-critical**: "We MUST have it by launch" (adds TAB + rotating proxy to Phase 3)
- **Nice-to-have**: "Phase 2 enhancement is OK" (defer proxy, launch with others)

### Recommendation
**Choose "Nice-to-have"** — Launch without TAB multi-competition:
- Rationale: 99 other bookmakers are more important than TAB's additional competitions
- Strategy: Market as "TAB: English Premier League only" in free tier
- Post-launch: Add proxy + multi-competition as premium feature

**By default**:
- Launch with: Ladbrokes + Neds + Betfair (free), 16+ others (premium)
- TAB available at launch but single-competition only
- Phase 3 (post-launch): Add proxy, unlock TAB all-competitions

**Action item**: Don't block launch on TAB multi-competition

---

## DECISION #6: Monetization Tier Details

**Context**: Pricing matters for positioning vs Outmatched ($15/$45).

### Question
What tier structure?
- **A) Match Outmatched** ($15 Premium, $45 Diamond)
- **B) Undercut** ($10 Premium, $30 Diamond)
- **C) Premium positioning** ($25 Premium, $75 Diamond)
- **D) Freemium heavy** (more free, smaller premium gap)

### Recommendation
**Choose A (Match Outmatched initially)** — Then iterate:
- Rationale: Validates PMF without wild pricing swings
- Strategy: Get 100 early users at Outmatched prices, measure ARPU, retention
- Post-launch: Adjust based on data (Paddle analytics, Stripe metrics)

**Suggested tiers**:
- **Free**: Ladbrokes + Neds + Betfair (3 bookmakers)
- **Premium** ($15/mo): Free + Punterstech (18) = 21 total
- **Diamond** ($45/mo): All 103 bookmakers

By launch (Phase 7), you'll have data to optimize.

**Action item**: Confirm with product/finance team, not engineering blocker

---

## DECISION #7: Launch Timing vs Bookmakers

**Context**: 60+ bookmakers is MVp minimum. You can reach that mid-Phase 2.

### Question
Do you:
- **Phase 2 midpoint launch** (Week 3-4): 60 bookmakers live, gather users early
  - Pros: Earlier feedback, get to PMF validation faster
  - Cons: Missing 40 bookmakers

- **Phase 2 end launch** (Week 4): 99 bookmakers live, compete with Outmatched feature-wise
  - Pros: Feature-complete from day 1, no "coming soon" messaging
  - Cons: Delayed user acquisition

### Recommendation
**Choose "Phase 2 midpoint launch"** — Get to market early:
- Launch at Week 3 with ~60 bookmakers (Punterstech + BetMakers + partial Gen Web)
- Marketing: "More bookmakers coming soon" (sets expectation, buys time)
- Phase 2 completion: "60→99 bookmakers" launch announcement (early user milestone)
- Phase 4+: "Approaching 103" positioning

**Advantage**: You learn from real users while finishing other platforms.

**Action item**: Plan marketing/beta cohort selection for Week 3 target

---

## SUMMARY: What You Need to Decide TODAY

| Decision | Options | Recommendation | Blocker |
|----------|---------|-----------------|---------|
| **Proxy strategy** | Test (1A) vs Buy Now | Test First (1A) | None — do test Week 1 |
| **Execution order** | Serial vs Parallel | Parallel (1B + 1C + BetCloud) | Need 2nd person? |
| **BetMakers fallback** | Selectors vs Hybrid | Hybrid (fallback built-in) | +1 day extra |
| **DB pool size** | Now vs Phase 4 | Now (1 line change) | None |
| **TAB multi-comp** | MVP vs Post-launch | Post-launch | None |
| **Pricing model** | Match vs Undercut vs Premium | Match Outmatched ($15/$45) | Product decision |
| **Launch timing** | Week 3 (60) vs Week 4 (99) | Week 3 (get feedback early) | Marketing plan |

---

## NEXT IMMEDIATE ACTIONS (Next 48 Hours)

1. **Decide on proxy test** (Phase 1A)
   - Yes: Confirm AWS t3.medium provisioning capacity
   - No: Commit to proxy purchase + SmartProxy/Bright Data account

2. **Decide on parallel execution**
   - Yes: Identify 2nd person for manual discovery (Generation Web + BetCloud)
   - No: Plan serial schedule (BetMakers → Gen Web → BetCloud)

3. **Decide on BetMakers approach**
   - Confirm hybrid (selectors + regex fallback) is OK (+1 day extra)
   - Or accept selectors-only fragility

4. **Change database pool size** (5 minutes)
   ```python
   # apps/api/src/api/core/database.py
   pool_size = 20
   max_overflow = 10
   ```

5. **Create JIRA/tickets** for Phase 1A, 1B, 1C with clear acceptance criteria

---

## APPENDIX: Decision Dependencies

```
Phase 1A (Proxy test) UNLOCKS Phase 3 (Proxy infrastructure)
         ↓
    Decide: Proxy needed? → Budget implications

Phase 1B (BetMakers) + 1C (Gen Web discovery) CAN RUN PARALLEL
         ↓
    Finish 3-4 days with 33+22 bookmakers ready to code

Phase 2 (Code Gen Web + BetCloud) depends on 1C results
         ↓
    Need odds endpoint found OR DOM approach confirmed

Phase 4+ (Scale testing) depends on Phase 1A results
         ↓
    Test with or without proxy based on Phase 1A data
```

---

**Once you answer these 7 questions, the roadmap becomes fully executable with no unknowns.**
