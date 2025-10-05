# Testing Guide - Phase 4 Odds Matcher

## 🎯 Quick Start Testing (No Real Data Needed)

### Option 1: Test with Mock Data (Fastest)

I'll create a mock data endpoint that returns sample opportunities so you can test the UI immediately.

### Option 2: Test Calculation Engine Only

Test the matching engine calculations directly without needing real odds.

### Option 3: Full Integration Test

Set up database, seed data, and test end-to-end.

---

## 🚀 Option 1: Test UI with Mock Data (Recommended First)

### Step 1: Create Mock Data Endpoint

I'll create a test endpoint that returns fake opportunities.

### Step 2: Start Development Server

```bash
# Terminal 1 - API
cd apps/api
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Web
cd apps/web
pnpm dev
```

### Step 3: Test the UI

1. Go to http://localhost:3000
2. Sign in (if not already)
3. Click "Tools" → "Odds Matcher"
4. You should see the filters and table
5. Click "Search Opportunities" or "REFRESH ODDS"
6. Click "OPEN" on any opportunity to see the calculator modal
7. Edit the odds and stake - watch calculations update in real-time

---

## 🧮 Option 2: Test Calculation Engine Directly

### Test the matching engine in Python:

```bash
cd apps/api
python3 << 'EOF'
from decimal import Decimal
from api.services.matching_engine import MatchingEngine, BackBet, LayBet, BetType

# Create engine
engine = MatchingEngine()

# Test Normal Bet
print("=" * 60)
print("TEST 1: Normal Bet (Qualifying)")
print("=" * 60)

back_bet = BackBet(
    bookmaker_code="tab",
    bookmaker_name="TAB",
    back_odds=Decimal("2.00"),
    stake=Decimal("100")
)

lay_bet = LayBet(
    lay_odds=Decimal("2.02"),
    commission=Decimal("0.02")
)

result = engine.calculate_matched_bet(back_bet, lay_bet, BetType.NORMAL)

print(f"Back Stake: ${result.back_stake}")
print(f"Lay Stake: ${result.lay_stake}")
print(f"Lay Liability: ${result.lay_liability}")
print(f"\nOutcome 1 - Selection Wins:")
print(f"  Profit: ${result.profit_if_back_wins}")
print(f"\nOutcome 2 - Selection Loses:")
print(f"  Profit: ${result.profit_if_lay_wins}")
print(f"\nQualifying Loss: ${result.qualifying_loss}")
print(f"PnL %: {engine.calculate_pnl_percentage(result)}%")
print(f"Rating: {result.rating}/100")

# Test Bonus Bet
print("\n" + "=" * 60)
print("TEST 2: Bonus Bet (Profit)")
print("=" * 60)

back_bet_bonus = BackBet(
    bookmaker_code="ladbrokes",
    bookmaker_name="Ladbrokes",
    back_odds=Decimal("4.00"),
    stake=Decimal("50")
)

lay_bet_bonus = LayBet(
    lay_odds=Decimal("4.10"),
    commission=Decimal("0.02")
)

result_bonus = engine.calculate_matched_bet(back_bet_bonus, lay_bet_bonus, BetType.BONUS)

print(f"Bonus Stake: ${result_bonus.back_stake}")
print(f"Lay Stake: ${result_bonus.lay_stake}")
print(f"Lay Liability: ${result_bonus.lay_liability}")
print(f"\nOutcome 1 - Selection Wins:")
print(f"  Profit: ${result_bonus.profit_if_back_wins}")
print(f"\nOutcome 2 - Selection Loses:")
print(f"  Profit: ${result_bonus.profit_if_lay_wins}")
print(f"\nAverage Profit: ${result_bonus.qualifying_loss}")
print(f"PnL %: {engine.calculate_pnl_percentage(result_bonus)}%")
print(f"Rating: {result_bonus.rating}/100")
EOF
```

Expected output:
```
============================================================
TEST 1: Normal Bet (Qualifying)
============================================================
Back Stake: $100
Lay Stake: $99.01
Lay Liability: $100.99

Outcome 1 - Selection Wins:
  Profit: $-0.99

Outcome 2 - Selection Loses:
  Profit: $-2.97

Qualifying Loss: $-1.98
PnL %: -1.98%
Rating: 60.4/100

============================================================
TEST 2: Bonus Bet (Profit)
============================================================
Bonus Stake: $50
Lay Stake: $36.59
Lay Liability: $113.41

Outcome 1 - Selection Wins:
  Profit: $36.59

Outcome 2 - Selection Loses:
  Profit: $35.86

Average Profit: $36.23
PnL %: +72.45%
Rating: 72.5/100
```

---

## 🗄️ Option 3: Full Integration Test

### Step 1: Ensure Database is Running

```bash
# Check if containers are running
docker ps

# If not running, start them
pnpm dev:up
```

### Step 2: Run Migrations and Seed Data

```bash
cd apps/api

# Run migrations (if not already done)
alembic upgrade head

# Seed bookmakers and sports
python -m api.scripts.seed_bookmakers
```

Expected output:
```
INFO:seed_bookmakers:Seeding sports...
INFO:seed_bookmakers:Created sport: AFL
INFO:seed_bookmakers:Created sport: NRL
...
INFO:seed_bookmakers:Seeding bookmakers...
INFO:seed_bookmakers:Created bookmaker: TAB
INFO:seed_bookmakers:Created bookmaker: Ladbrokes
INFO:seed_bookmakers:Created bookmaker: Betfair
...
INFO:seed_bookmakers:Database seeding completed successfully!
```

### Step 3: Verify Seed Data

```bash
# Connect to database
docker exec -it mb_db psql -U postgres -d mb_dev

# Check sports
SELECT code, display_name FROM sports;

# Check bookmakers
SELECT code, display_name, is_active FROM bookmakers;

# Exit
\q
```

### Step 4: Test API Endpoints Directly

```bash
# Get auth token first
# Sign in to http://localhost:3000 and copy your session token from browser DevTools
# Application > Cookies > __session

# Test with curl (replace YOUR_TOKEN)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/odds/matcher?stake=100&bet_type=normal&limit=10"
```

---

## 📊 Testing Checklist

### Backend Tests

- [ ] Matching engine calculates normal bets correctly
- [ ] Matching engine calculates bonus bets correctly
- [ ] Lay stake auto-calculated correctly
- [ ] PnL percentage accurate
- [ ] Rating system working (0-100)
- [ ] API returns 401 without auth
- [ ] API returns empty array when no odds
- [ ] Plan enforcement works (free tier = TAB + Ladbrokes only)

### Frontend Tests

- [ ] Odds matcher page loads
- [ ] Filters display correctly
- [ ] Stake input accepts numbers
- [ ] Bet type toggle works (Normal ↔ Bonus)
- [ ] Search input present
- [ ] Advanced filters expand/collapse
- [ ] Bookmaker pills toggle selection
- [ ] Sport pills toggle selection
- [ ] "Search Opportunities" button calls API
- [ ] "REFRESH ODDS" button works
- [ ] Loading state shows spinner
- [ ] Empty state shows helpful message
- [ ] Table displays on desktop
- [ ] Cards display on mobile (< 1024px)
- [ ] "OPEN" button opens modal
- [ ] Modal shows event details
- [ ] Modal allows editing odds
- [ ] Modal allows editing stake
- [ ] Lay stake auto-updates when inputs change
- [ ] Outcome matrix shows both scenarios
- [ ] Summary shows qualifying loss/profit
- [ ] Close button works
- [ ] Mobile responsive (test on phone/tablet)

### Navigation Tests

- [ ] "Tools" dropdown shows "Odds Matcher"
- [ ] Clicking "Odds Matcher" goes to /dashboard/odds-matcher
- [ ] Works on desktop
- [ ] Works on mobile menu

---

## 🐛 Common Issues & Solutions

### Issue: API returns 403 "Your plan does not allow..."

**Solution**: This is correct! Free tier only allows TAB and Ladbrokes. Either:
1. Don't filter bookmakers (uses your allowed ones automatically)
2. Only select TAB/Ladbrokes in filters
3. Or upgrade plan in database:

```sql
docker exec -it mb_db psql -U postgres -d mb_dev -c \
  "UPDATE users SET current_plan = 'premium' WHERE email = 'your@email.com';"
```

### Issue: API returns empty array []

**Solution**: No odds in database yet. This is expected! You have 2 options:
1. Use the mock data endpoint I'll create
2. Wait until we hook up real scrapers

### Issue: Modal calculations seem wrong

**Solution**: Check:
- Commission should be 0.02 (2%)
- Lay odds should be slightly higher than back odds
- For normal bets, expect small loss (1-5%)
- For bonus bets, expect profit (70-95%)

### Issue: Page shows "Loading..." forever

**Solution**:
- Check API is running on port 8000
- Check `/api/proxy/odds/matcher` route exists
- Check browser console for errors (F12)

---

## 🎨 Visual Testing

### Desktop (1920x1080)
- [ ] Table has 9 columns, all visible
- [ ] Filters in one row
- [ ] Advanced filters expand smoothly
- [ ] Modal is centered, max-width 1024px

### Tablet (768x1024)
- [ ] Table still shows (might need horizontal scroll)
- [ ] Filters stack nicely
- [ ] Modal is responsive

### Mobile (375x667)
- [ ] Cards replace table
- [ ] Filters stack vertically
- [ ] Bet type toggle still usable
- [ ] Modal scrolls if needed
- [ ] "OPEN" button easy to tap

---

## 🚀 Next: Add Mock Data

Want me to create a mock data endpoint so you can test the UI immediately without real odds?

I can create:
- `/odds/matcher-mock` endpoint with 20 fake opportunities
- Realistic AFL/NRL events
- Mix of normal and bonus bets
- Various ratings (50-95)
- Random TAB/Ladbrokes odds

This way you can test the entire UI flow right now!

Let me know if you want me to add the mock endpoint, or if you want to test something specific first.
