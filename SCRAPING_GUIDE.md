# 🔍 Real Data Scraping Guide

## Goal
Find and use the real API endpoints that TAB and Ladbrokes websites use to get live odds data.

---

## 🎯 Step 1: Discover TAB API Endpoints

### Manual Discovery (Browser DevTools)

1. **Open TAB website in browser**:
   - Go to: https://www.tab.com.au/sports/australian-rules

2. **Open DevTools** (F12 or Right-click → Inspect)

3. **Go to Network tab**:
   - Filter by: `Fetch/XHR`
   - Clear existing requests (🚫 icon)

4. **Navigate or refresh the page**

5. **Look for API calls** containing:
   - `/sports/` or `/api/`
   - JSON responses
   - Event names, odds, markets

6. **Click on promising requests**:
   - Check the **Request URL**
   - Check the **Response** (should have events and odds in JSON)
   - Check **Headers** (might need specific headers)

### Common TAB API Patterns

Based on previous research, TAB likely uses:

```
Base: https://api.beta.tab.com.au

Possible endpoints:
- /v1/tab-info-service/sports/Australian%20Rules/featured-competitions
- /v1/tab-info-service/sports/events
- /v1/tab-info-service/racing/dates/today
```

### Test Script

```bash
# Test if TAB API is accessible
curl "https://api.beta.tab.com.au/v1/tab-info-service/sports/Australian%20Rules/featured-competitions?jurisdiction=NSW" | python -m json.tool

# Or use the discovery script
cd apps/worker
python src/discover_apis.py tab
```

---

## 🎯 Step 2: Discover Ladbrokes API Endpoints

### Manual Discovery

1. **Open Ladbrokes**:
   - Go to: https://www.ladbrokes.com.au/sports/australian-rules

2. **DevTools Network tab** (same process as TAB)

3. **Look for**:
   - GraphQL endpoint (common for Ladbrokes)
   - REST API calls
   - WebSocket connections (for live odds)

### Common Ladbrokes Patterns

```
Possible endpoints:
- GraphQL: POST to /graphql
- REST: /api/v2/sports/...
- Could be using Entain platform (same as Neds)
```

### Test GraphQL

If Ladbrokes uses GraphQL, you'll see:
- POST requests to `/graphql`
- Request body with `query` and `variables`
- Response with `data` object

Example test:
```bash
curl -X POST https://www.ladbrokes.com.au/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ sports { id name } }"}'
```

---

## 🎯 Step 3: Update Scrapers with Real Endpoints

Once you find the endpoints, we'll update:

### For TAB (`apps/worker/src/scrapers/tab_scraper.py`)

Find this section:
```python
# Placeholder: TAB API structure varies by sport
url = f"{self.api_base}/v1/tab-info-service/sports/{tab_sport_code}/meetings"
```

Replace with the real endpoint you discovered.

### For Ladbrokes (`apps/worker/src/scrapers/ladbrokes_scraper.py`)

Find this section:
```python
# Ladbrokes API structure varies - this is a placeholder
url = f"{self.api_base}/v2/sports/{ladbrokes_sport}/events"
```

Replace with real endpoint.

---

## 🎯 Step 4: Test Scrapers

### Test TAB Scraper

```bash
cd apps/api
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Test in Python
python << 'EOF'
import asyncio
import sys
sys.path.insert(0, "src")

from scrapers.tab_scraper import TABScraper

async def test():
    scraper = TABScraper()
    result = await scraper.scrape_sport('afl', limit=5)

    print(f"Status: {result.status}")
    print(f"Events: {result.events_scraped}")
    print(f"Odds: {result.odds_scraped}")
    print(f"Errors: {result.errors}")

    if result.events:
        print(f"\nFirst event: {result.events[0].name}")
        print(f"Odds count: {len(result.events[0].odds)}")

asyncio.run(test())
EOF
```

### Test Ladbrokes Scraper

Same process, replace `TABScraper` with `LadbrokesScraper`.

---

## 🎯 Step 5: Save Scraped Data to Database

Once scrapers work, create a function to save odds:

```python
# apps/worker/src/jobs/save_odds.py
from api.models import Event, Market, Selection, OddsSnapshot, Bookmaker
from api.core.database import SessionLocal

def save_scrape_result(result: ScrapeResult):
    """Save scraped odds to database"""
    db = SessionLocal()

    try:
        for scraped_event in result.events:
            # Find or create event
            event = find_or_create_event(db, scraped_event)

            # Save odds
            for scraped_odds in scraped_event.odds:
                save_odds_snapshot(db, scraped_odds, event)

        db.commit()
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
```

---

## 🎯 Step 6: Create Scraping Job

### Option A: Simple Python Script

```python
# apps/worker/src/jobs/scrape_all.py
import asyncio
from scrapers.tab_scraper import TABScraper
from scrapers.ladbrokes_scraper import LadbrokesScraper
from jobs.save_odds import save_scrape_result

async def scrape_all_bookmakers():
    """Scrape all bookmakers for all sports"""
    sports = ['afl', 'nrl']
    scrapers = [
        TABScraper(),
        LadbrokesScraper(),
    ]

    for sport in sports:
        for scraper in scrapers:
            print(f"Scraping {scraper.bookmaker_code} for {sport}...")
            result = await scraper.scrape_sport(sport, limit=20)

            if result.status != "failed":
                save_scrape_result(result)
                print(f"✅ Saved {result.odds_scraped} odds")
            else:
                print(f"❌ Failed: {result.errors}")

if __name__ == "__main__":
    asyncio.run(scrape_all_bookmakers())
```

Run it:
```bash
cd apps/worker
python src/jobs/scrape_all.py
```

### Option B: Scheduled Job (Celery)

For production, set up Celery to run every 5-10 minutes.

---

## 🎯 Step 7: Switch UI to Real Data

Once database has real odds:

1. **Update frontend** to use real endpoint:
   ```typescript
   // Change this line in OddsMatcherClient.tsx:
   const response = await fetch(`/api/proxy/odds/matcher?${params.toString()}`)
   // FROM: /api/proxy/odds/matcher-mock
   ```

2. **Delete mock files**:
   ```bash
   rm apps/api/src/api/routers/odds_matcher_mock.py
   rm apps/web/src/app/api/proxy/odds/matcher-mock/route.ts
   ```

3. **Update API main.py**:
   Remove the mock router import

---

## 📋 **Quick Checklist**

- [ ] Find TAB API endpoint (DevTools)
- [ ] Find Ladbrokes API endpoint (DevTools)
- [ ] Update `tab_scraper.py` with real URL
- [ ] Update `ladbrokes_scraper.py` with real URL
- [ ] Test TAB scraper (get real data)
- [ ] Test Ladbrokes scraper (get real data)
- [ ] Create `save_odds.py` function
- [ ] Create `scrape_all.py` job
- [ ] Run scraping job manually
- [ ] Verify odds in database
- [ ] Switch UI to real endpoint
- [ ] Test end-to-end flow
- [ ] Set up scheduled scraping (optional)

---

## 🚀 **Let's Start!**

Want me to help you discover the real endpoints? We can:

1. **I can guide you** through using browser DevTools
2. **You share the API URLs** you find
3. **I'll update the scrapers** with real endpoints
4. **We test together** and get real odds flowing!

Ready to start with TAB? Open https://www.tab.com.au/sports/australian-rules in your browser and let's find those endpoints! 🔍
