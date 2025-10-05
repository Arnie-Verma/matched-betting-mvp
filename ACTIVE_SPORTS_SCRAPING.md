# 🏆 Active Sports Scraping Guide (October 2025)

## Currently Active Sports (October)

### ⚽ **Soccer (Football)** - BEST OPTION NOW
- **English Premier League (EPL)** - Active, lots of matches
- **UEFA Champions League** - Midweek matches
- **La Liga, Serie A, Bundesliga** - All active
- **A-League** (Australia) - Season starts October

### 🏀 **Basketball**
- **NBA** - Season just started (October)
- **NBL** (Australia) - Active

### 🏏 **Cricket**
- **ODI/T20 Internationals** - Various series
- **Domestic leagues** - Some active

### 🏈 **American Football**
- **NFL** - Active, popular for matched betting

### ⚾ **Baseball**
- **MLB Playoffs** - October

### 🎾 **Tennis**
- **ATP/WTA Tours** - Year-round

---

## 🎯 Recommended: Start with EPL (Soccer)

EPL is perfect because:
- ✅ Active RIGHT NOW (October is peak season)
- ✅ Matches every weekend + midweek
- ✅ High liquidity on Betfair
- ✅ All bookmakers cover it heavily
- ✅ Easy to find odds

---

## 🔍 Discovery Steps for EPL

### 1. Find TAB Soccer API

**Browser Steps:**
1. Go to: https://www.tab.com.au/sports/soccer
2. F12 → Network → Fetch/XHR
3. Refresh page
4. Look for API calls with EPL/Premier League data

**Expected URL patterns:**
```
https://api.beta.tab.com.au/v1/tab-info-service/sports/Soccer/...
https://api.beta.tab.com.au/v1/tab-info-service/sports/Football/...
```

**What to look for in response:**
- Event names like "Manchester United vs Liverpool"
- Market types: "Head To Head", "Over/Under 2.5"
- Decimal odds (e.g., 2.50, 1.85)

### 2. Find Ladbrokes Soccer API

**Browser Steps:**
1. Go to: https://www.ladbrokes.com.au/sports/soccer/english-premier-league
2. F12 → Network → Fetch/XHR
3. Refresh page
4. Look for GraphQL or REST API calls

**Expected patterns:**
- GraphQL: POST to /graphql
- REST: /api/sports/soccer or /api/football
- Response with matches and odds

### 3. Betfair Soccer (Official API)

Betfair has documented API:
```
Event Type ID for Soccer: 1
Market Types: MATCH_ODDS, OVER_UNDER_25, etc.
```

---

## 🧪 Quick Test: Find Active Matches

Let me test if there are active soccer events available:

```bash
# Test TAB for soccer
curl "https://api.beta.tab.com.au/v1/tab-info-service/sports/Soccer/featured-competitions?jurisdiction=NSW"

# Alternative URLs to try:
curl "https://api.beta.tab.com.au/v1/tab-info-service/sports/Football/..."
```

---

## 📝 Update Scraper Sport Mappings

Once we find endpoints, update sport codes:

### TAB Scraper
```python
self.sport_mapping = {
    "soccer": "soccer",  # or "football" - depends on TAB's naming
    "basketball": "basketball",
    "cricket": "cricket",
    "tennis": "tennis",
    # AFL/NRL inactive, comment out for now
}
```

### Ladbrokes Scraper
```python
self.sport_mapping = {
    "soccer": "football",  # Ladbrokes might use "football"
    "basketball": "basketball",
    "tennis": "tennis",
}
```

### Betfair API
```python
def get_betfair_event_type_id(self, sport: str) -> Optional[str]:
    mapping = {
        "soccer": "1",      # Soccer
        "tennis": "2",      # Tennis
        "basketball": "7522", # Basketball
        "cricket": "4",     # Cricket
        # NFL, MLB, etc. also available
    }
    return mapping.get(sport)
```

---

## 🎯 Simplified Testing Plan

### Step 1: Browser Discovery (5 min)

Open these URLs and use DevTools:
1. TAB Soccer: https://www.tab.com.au/sports/soccer
2. Ladbrokes EPL: https://www.ladbrokes.com.au/sports/soccer/english-premier-league

Find the API endpoints and share them with me.

### Step 2: Update Scrapers (I'll do this)

Once you share the endpoints:
- I'll update `tab_scraper.py`
- I'll update `ladbrokes_scraper.py`
- I'll fix the response parsing

### Step 3: Test Scraping

```bash
cd apps/worker
python << 'EOF'
import asyncio
import sys
sys.path.insert(0, "src")
sys.path.insert(0, "../api/src")

from scrapers.tab_scraper import TABScraper

async def test():
    scraper = TABScraper()
    result = await scraper.scrape_sport('soccer', limit=5)

    print(f"✅ Events: {result.events_scraped}")
    print(f"✅ Odds: {result.odds_scraped}")

    if result.events:
        event = result.events[0]
        print(f"\nFirst match: {event.name}")
        print(f"Start time: {event.start_time}")
        print(f"Odds count: {len(event.odds)}")

asyncio.run(test())
EOF
```

### Step 4: Save to Database

Once scraping works:
```bash
# Run database seed
cd apps/api
python -m api.scripts.seed_bookmakers

# Create save function and run scraper
# (I'll create this once scraping works)
```

### Step 5: Test UI with Real Data

Switch from mock to real endpoint and see live EPL odds!

---

## 🚀 Action Items

**You do:**
1. Open TAB soccer page
2. Open DevTools (F12)
3. Find API endpoint
4. Copy the URL or cURL command
5. Share it here

**I'll do:**
1. Update scrapers with real endpoints
2. Parse the response structure
3. Test scraping
4. Create save-to-database function
5. Get real odds flowing!

---

## 💡 Alternative: Start with Just Betfair

If TAB/Ladbrokes prove tricky, we could start with just Betfair:

**Pros:**
- Official, documented API
- No scraping needed
- Always reliable
- Has lay odds (the important part!)

**Cons:**
- Need API key (free to register)
- Need SSL certificate for auth
- More setup initially

We can show Betfair lay odds and add TAB/Ladbrokes back odds later.

---

## 🎯 Next Step

**Open TAB Soccer page right now:**
https://www.tab.com.au/sports/soccer

Use F12 DevTools, find the API call, and paste the URL here!

Or, would you prefer I help set up Betfair API first (guaranteed to work)?
