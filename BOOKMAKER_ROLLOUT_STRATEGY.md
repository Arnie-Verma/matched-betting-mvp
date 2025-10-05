# 🎯 Bookmaker & League Rollout Strategy

## Scale
- **100+ Australian bookmakers**
- **14 major sports leagues**
- **Tiered access** (Free: 2, Premium: 10, Diamond: 100+)

---

## 🚀 Phase 1: MVP (Free Tier) - **START HERE**

### Target: Launch in 2 weeks

**Bookmakers (2):**
- ✅ TAB
- ✅ Ladbrokes
- ✅ Betfair (for lay odds)

**Leagues (3 active now - October 2025):**
- ⚽ **EPL** (English Premier League) - Most liquid, active now
- 🏀 **NBA** - Just started, very popular
- ⚽ **UEFA Champions League** - Midweek matches

**Why these?**
- TAB & Ladbrokes: Largest Australian bookmakers, easiest to scrape
- EPL: Most popular, high Betfair liquidity, active RIGHT NOW
- NBA: Just started season, different sport type
- UEFA: Midweek opportunities, same scraping as EPL

**Deliverable:**
- Free users get TAB vs Ladbrokes odds matched with Betfair
- 3 active leagues
- Proven concept

---

## 📈 Phase 2: Premium Tier (1 month out)

**Add 8 more bookmakers (total: 10):**
Priority order based on **market share + scraping difficulty**:

1. **Sportsbet** (Largest AU bookmaker)
2. **Neds** (Entain platform, same as Ladbrokes)
3. **Pointsbet** (Big player, good API)
4. **Unibet** (Entain platform)
5. **Betr** (Growing fast)
6. **BlueBet** (ASX listed, reliable)
7. **Palmerbet** (Popular regional)
8. **TopSport** (Good odds)

**Add 4 more leagues:**
- 🏈 **NFL** (Massive for matched betting)
- 🏏 **Cricket** (Big Bash, internationals)
- 🏀 **NBL** (Australian, starting soon)
- 🏉 **NRL** (when season returns March 2026)

**Deliverable:**
- Premium users: 10 bookmakers
- 7 leagues total
- Better odds comparison

---

## 💎 Phase 3: Diamond Tier (2-3 months out)

**Add remaining 90+ bookmakers in batches:**

### Batch 1: Major Players (10 bookmakers)
- BetDeluxe, PlayUp, BoomBet, Dabble, Picklebet
- BetNation, MyBet, EliteBet, BlueBet, GoldBet

### Batch 2: Mid-tier (20 bookmakers)
Focus on those with APIs or easy scraping

### Batch 3: Long-tail (70+ bookmakers)
Many small bookmakers, lower priority

**Add remaining leagues:**
- ⚽ Spanish La Liga, French Ligue 1, German Bundesliga, Italian Serie A
- 🏒 NHL
- ⚽ A-League (Australian)
- 🥊 Boxing
- ⚽ MLS (Major League Soccer)

**Deliverable:**
- Diamond users: 100+ bookmakers
- All 14 leagues
- Comprehensive coverage

---

## 🏗️ Technical Architecture for Scale

### 1. Bookmaker Categorization

```python
# Database: bookmakers table
class Bookmaker(Base):
    code: str  # "sportsbet"
    platform: str  # "proprietary", "entain", "kambi", "openbet"
    scraping_difficulty: str  # "easy", "medium", "hard"
    requires_auth: bool
    tier_availability: str  # "free", "premium", "diamond"
    api_type: str  # "rest", "graphql", "scrape"
```

**Platform Grouping** (reduces scraping work):
- **Entain**: Ladbrokes, Neds, Unibet (same codebase)
- **Kambi**: Many white-labels share this platform
- **Proprietary**: TAB, Sportsbet, Pointsbet (unique)

### 2. Scraper Factory Pattern

```python
# apps/worker/src/scrapers/factory.py
class ScraperFactory:
    """Create scrapers based on platform"""

    @staticmethod
    def create_scraper(bookmaker: Bookmaker):
        if bookmaker.platform == "entain":
            return EntainScraper(bookmaker.code)
        elif bookmaker.platform == "kambi":
            return KambiScraper(bookmaker.code)
        else:
            return ProprietaryScraper(bookmaker)
```

**Benefit:** One scraper handles multiple bookmakers on same platform

### 3. League/Competition Mapping

```python
# Database: competitions table
class Competition(Base):
    name: str  # "English Premier League"
    sport_id: int
    external_mappings: JSON  # {"tab": "EPL", "sportsbet": "premier-league"}
    is_active: bool
    priority: int  # Higher = scrape more frequently
```

### 4. Intelligent Scraping Schedule

```python
# apps/worker/src/jobs/scheduler.py
class ScrapingScheduler:
    """Smart scheduling based on league activity"""

    def get_scrape_frequency(self, league: str, time: datetime) -> int:
        # EPL match day: every 2 minutes
        # EPL off-day: every 15 minutes
        # Low-tier league: every 30 minutes
        pass
```

---

## 📋 Phase 1 Implementation Checklist

### Week 1: Core Scrapers
- [ ] TAB scraper (EPL, NBA, UEFA)
- [ ] Ladbrokes scraper (EPL, NBA, UEFA)
- [ ] Betfair API (EPL, NBA, UEFA)
- [ ] Test all 3 bookmakers
- [ ] Save to database

### Week 2: Polish & Launch
- [ ] Match normalization (team name matching)
- [ ] Odds comparison engine
- [ ] UI shows real data
- [ ] Error handling
- [ ] Monitoring/alerts
- [ ] Launch to beta users!

---

## 🎯 Immediate Next Steps (Today)

### Priority 1: Get EPL Working
1. **Discover TAB EPL endpoint** (DevTools)
2. **Discover Ladbrokes EPL endpoint** (DevTools)
3. **Update scrapers** with real endpoints
4. **Test scraping** EPL matches
5. **Save to database**
6. **Show in UI**

### Priority 2: Add NBA (if time)
Same process for NBA (season just started)

---

## 📊 Bookmaker Database Seed

I'll create a comprehensive seed file with all 100+ bookmakers, but mark them:
- `tier: 'free'` - TAB, Ladbrokes (active now)
- `tier: 'premium'` - Sportsbet, Neds, etc. (coming soon)
- `tier: 'diamond'` - All others (future)

This way:
- Database is ready for scale
- UI can show upgrade prompts
- Easy to enable bookmakers as scrapers are built

---

## 🚀 Let's Start: EPL Today

**Right now, let's focus on:**
1. ⚽ **EPL** (active, popular, liquid)
2. 🏀 **TAB + Ladbrokes** (free tier)
3. 💱 **Betfair** (lay odds)

Once these 3 work end-to-end, scaling to 100+ bookmakers is just:
- Copy scraper pattern
- Add to database
- Enable in UI

**Ready to discover TAB's EPL endpoint?**

Open: https://www.tab.com.au/sports/soccer
Press F12, find the API call, paste it here!

Or should I create the full bookmaker seed file first so the database is ready?
