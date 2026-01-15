# Scraper Validation Framework

**Created**: 2026-01-15
**Status**: IMPLEMENTED (Phase A Complete)
**Goal**: Automated QA layer for 100+ bookmakers × 14 leagues without manual checking

---

## Executive Summary

Server-side validation after each scrape detects broken scrapers, mapping bugs, and bad odds before data reaches users. Surfaces only anomalies for human review.

**Key Principles**:
1. Validate structure first (catches 70-80% of issues)
2. Use implied probability for odds comparison (not raw %)
3. Ladbrokes = bootstrap reference, consensus = long-term truth
4. Never block user requests on validation failures
5. Alert + quarantine, don't crash

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      VALIDATION PIPELINE                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SCRAPE                                                              │
│    ↓                                                                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ PHASE 1: Structural & Coverage Validation                     │   │
│  │ ├─ Event count sanity (vs expected horizon)                   │   │
│  │ ├─ Event matching rate (normalized teams + start time)        │   │
│  │ ├─ Market presence (moneyline has 2-3 outcomes)               │   │
│  │ ├─ Odds bounds (1.01 ≤ odds ≤ 1001)                          │   │
│  │ └─ Timestamp freshness (not stale)                            │   │
│  │ → Catches: dead scrapers, wrong pages, parsing failures       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│    ↓                                                                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ PHASE 2: Odds Sanity via Implied Probability                  │   │
│  │ ├─ Convert odds → implied probability: p = 1/odds             │   │
│  │ ├─ Compare to Ladbrokes reference (bootstrap)                 │   │
│  │ ├─ Compare to consensus median (once enough books)            │   │
│  │ └─ Flag if gap > threshold (market-type aware)                │   │
│  │ → Catches: mis-parsed odds, swapped runners, stale data       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│    ↓                                                                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ PHASE 3: Golden Fixtures (Regression Safety)                  │   │
│  │ ├─ 5-10 curated fixtures per league                           │   │
│  │ ├─ Always scrape, always validate                             │   │
│  │ └─ Structure + odds band validation                           │   │
│  │ → Catches: regressions after code changes                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│    ↓                                                                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ PHASE 4: Scoring & Anomaly Output                             │   │
│  │ ├─ Per bookmaker × league: PASS / WARN / FAIL                 │   │
│  │ ├─ Coverage %, anomaly count, top N outliers                  │   │
│  │ └─ Human review = "check top anomalies" only                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│    ↓                                                                 │
│  SAVE TO DB (with validation metadata)                               │
│    ↓                                                                 │
│  ALERT IF FAIL (Sentry/Slack, non-blocking)                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Structural & Coverage Validation

### Checks Performed

| Check | Rule | Failure Indicates |
|-------|------|-------------------|
| **Event Count** | 3 ≤ events ≤ expected_max (per league) | Dead scraper, wrong page |
| **Event Matching** | ≥70% events match reference | Normalization bug |
| **Market Presence** | Moneyline has 2 outcomes (tennis) or 3 (soccer) | Parsing failure |
| **Odds Bounds** | 1.01 ≤ odds ≤ 1001 | Mis-parsed value |
| **Selection Coverage** | All expected selections present (home/away/draw) | Missing data |
| **Timestamp Freshness** | scraped_at within last 15 min | Stale cache |

### Expected Event Counts (Configurable)

```python
EXPECTED_EVENTS = {
    "epl": {"min": 3, "max": 20, "typical": 10},      # 10 matches/week
    "laliga": {"min": 3, "max": 20, "typical": 10},
    "bundesliga": {"min": 3, "max": 18, "typical": 9},
    "seriea": {"min": 3, "max": 20, "typical": 10},
    "ligue1": {"min": 3, "max": 20, "typical": 10},
    "aleague": {"min": 3, "max": 12, "typical": 6},
    "ucl": {"min": 2, "max": 16, "typical": 8},       # Matchday dependent
    "nba": {"min": 5, "max": 30, "typical": 15},      # Daily games
    "nbl": {"min": 2, "max": 10, "typical": 4},
    "nhl": {"min": 5, "max": 30, "typical": 15},
    "afl": {"min": 0, "max": 18, "typical": 9},       # Seasonal (off Oct-Mar)
    "nrl": {"min": 0, "max": 16, "typical": 8},       # Seasonal
}
```

### Implementation

```python
@dataclass
class StructuralValidation:
    """Phase 1 validation results"""
    event_count: int
    event_count_valid: bool
    matching_rate: Decimal  # % of events matched to reference
    markets_valid: int      # Count of markets with correct structure
    odds_in_bounds: int     # Count of odds within 1.01-1001
    odds_out_of_bounds: List[str]  # Details of invalid odds
    is_fresh: bool          # scraped_at recent enough

    @property
    def passed(self) -> bool:
        return (
            self.event_count_valid and
            self.matching_rate >= Decimal("70") and
            len(self.odds_out_of_bounds) == 0 and
            self.is_fresh
        )

def validate_structure(result: ScrapeResult, competition: str) -> StructuralValidation:
    """Run Phase 1 structural validation"""
    expected = EXPECTED_EVENTS.get(competition, {"min": 1, "max": 50})

    event_count = result.events_scraped
    event_count_valid = expected["min"] <= event_count <= expected["max"]

    # Check odds bounds
    out_of_bounds = []
    for event in result.events:
        for odds in event.odds:
            if not (Decimal("1.01") <= odds.decimal_odds <= Decimal("1001")):
                out_of_bounds.append(
                    f"{event.name}: {odds.selection_name} = {odds.decimal_odds}"
                )

    # Check freshness
    is_fresh = (datetime.now(timezone.utc) - result.completed_at).total_seconds() < 900

    return StructuralValidation(
        event_count=event_count,
        event_count_valid=event_count_valid,
        matching_rate=Decimal("0"),  # Calculated in Phase 2
        markets_valid=0,  # TODO
        odds_in_bounds=result.odds_scraped - len(out_of_bounds),
        odds_out_of_bounds=out_of_bounds,
        is_fresh=is_fresh
    )
```

---

## Phase 2: Odds Sanity via Implied Probability

### Core Logic

```python
def odds_to_implied_probability(odds: Decimal) -> Decimal:
    """Convert decimal odds to implied probability (0-100)"""
    return (Decimal("1") / odds * Decimal("100")).quantize(Decimal("0.01"))

def probability_gap(odds1: Decimal, odds2: Decimal) -> Decimal:
    """Calculate gap in percentage points between two odds"""
    p1 = odds_to_implied_probability(odds1)
    p2 = odds_to_implied_probability(odds2)
    return abs(p1 - p2)
```

### Threshold Strategy (Market-Type Aware)

| Market Type | Warn Threshold | Fail Threshold | Rationale |
|-------------|----------------|----------------|-----------|
| **Moneyline (favorites)** | 3pp | 6pp | High-liquidity, tight spreads |
| **Moneyline (longshots)** | 5pp | 10pp | Less efficient, wider acceptable range |
| **Draw** | 4pp | 8pp | Less liquid than win markets |
| **Handicap/Spread** | 3pp | 6pp | Similar to moneyline |
| **Totals** | 4pp | 8pp | Moderate liquidity |
| **Betfair (Exchange)** | N/A | N/A | Structure only - not odds comparison |

### Longshot Detection

```python
def get_threshold(odds: Decimal, market_type: str) -> tuple[Decimal, Decimal]:
    """Get warn/fail thresholds based on odds level and market type"""

    # Betfair = structure only
    if market_type == "exchange":
        return (Decimal("999"), Decimal("999"))

    # Longshot adjustment (odds > 5.0 = implied prob < 20%)
    is_longshot = odds > Decimal("5.0")

    if market_type in ("match_winner", "moneyline"):
        if is_longshot:
            return (Decimal("5"), Decimal("10"))
        else:
            return (Decimal("3"), Decimal("6"))
    elif market_type == "draw":
        return (Decimal("4"), Decimal("8"))
    else:
        return (Decimal("4"), Decimal("8"))
```

### Reference Strategy

**Bootstrap (Phase 1-2 of project)**:
- Use Ladbrokes as primary reference
- Ladbrokes is stable, comprehensive, Entain platform well-understood

**Long-term (Phase 3+)**:
- Calculate consensus median from "trusted" bookmakers
- Trusted = scrapers that have passed validation consistently
- Consensus more robust than single reference

```python
def get_reference_probability(
    event_key: str,
    selection_key: str,
    ladbrokes_odds: Dict[str, Dict[str, Decimal]],
    all_bookmaker_odds: Dict[str, Dict[str, Dict[str, Decimal]]],
    use_consensus: bool = False
) -> Decimal:
    """
    Get reference implied probability for comparison.

    Bootstrap: Use Ladbrokes
    Long-term: Use consensus median from trusted books
    """
    if not use_consensus:
        # Bootstrap: Ladbrokes only
        if event_key in ladbrokes_odds and selection_key in ladbrokes_odds[event_key]:
            return odds_to_implied_probability(ladbrokes_odds[event_key][selection_key])
        return Decimal("0")

    # Consensus: median of all trusted bookmakers
    probs = []
    for bookmaker, events in all_bookmaker_odds.items():
        if event_key in events and selection_key in events[event_key]:
            probs.append(odds_to_implied_probability(events[event_key][selection_key]))

    if not probs:
        return Decimal("0")

    probs.sort()
    mid = len(probs) // 2
    if len(probs) % 2 == 0:
        return (probs[mid-1] + probs[mid]) / 2
    return probs[mid]
```

---

## Phase 3: Golden Fixtures

### Concept

Curated fixtures per league that ALWAYS get validated. Provides fast regression detection without full validation.

### Implementation

```python
# Golden fixtures - updated manually as matches approach
# Format: (home_team_normalized, away_team_normalized, expected_selections)
GOLDEN_FIXTURES = {
    "epl": [
        ("arsenal", "chelsea", ["home", "away", "draw"]),
        ("manutd", "liverpool", ["home", "away", "draw"]),
        ("mancity", "tottenham", ["home", "away", "draw"]),
    ],
    "laliga": [
        ("realmadrid", "barcelona", ["home", "away", "draw"]),
        ("atletico", "sevilla", ["home", "away", "draw"]),
    ],
    "nba": [
        ("lakers", "celtics", ["home", "away"]),
        ("warriors", "bucks", ["home", "away"]),
    ],
    # Add more per league...
}

def validate_golden_fixtures(
    result: ScrapeResult,
    competition: str
) -> List[GoldenFixtureResult]:
    """Validate golden fixtures are present and correctly structured"""
    golden = GOLDEN_FIXTURES.get(competition, [])
    results = []

    for home, away, expected_selections in golden:
        # Find matching event
        event_key = f"{away}v{home}" if away < home else f"{home}v{away}"

        matching_event = None
        for event in result.events:
            if normalize_event_key(event) == event_key:
                matching_event = event
                break

        if not matching_event:
            results.append(GoldenFixtureResult(
                fixture=f"{home} v {away}",
                found=False,
                selections_valid=False,
                odds_in_band=False
            ))
            continue

        # Validate selections present
        found_selections = {o.selection_key for o in matching_event.odds}
        selections_valid = set(expected_selections).issubset(found_selections)

        # Validate odds in reasonable band (1.01 - 100)
        odds_valid = all(
            Decimal("1.01") <= o.decimal_odds <= Decimal("100")
            for o in matching_event.odds
        )

        results.append(GoldenFixtureResult(
            fixture=f"{home} v {away}",
            found=True,
            selections_valid=selections_valid,
            odds_in_band=odds_valid
        ))

    return results
```

---

## Phase 4: Scoring & Anomaly Output

### Validation Score

```python
@dataclass
class ValidationScore:
    """Final validation score for bookmaker × league"""
    bookmaker_code: str
    competition: str
    status: Literal["PASS", "WARN", "FAIL"]

    # Phase 1 metrics
    event_count: int
    structural_issues: int

    # Phase 2 metrics
    coverage_percent: Decimal
    anomaly_count: int
    worst_anomalies: List[OddsAnomaly]  # Top 5 by probability gap

    # Phase 3 metrics
    golden_fixtures_found: int
    golden_fixtures_total: int

    # Metadata
    validated_at: datetime
    scrape_duration_seconds: float

def calculate_final_status(
    structural: StructuralValidation,
    probability_anomalies: List[OddsAnomaly],
    golden_results: List[GoldenFixtureResult]
) -> Literal["PASS", "WARN", "FAIL"]:
    """Determine final validation status"""

    # FAIL conditions
    if not structural.passed:
        return "FAIL"

    critical_anomalies = [a for a in probability_anomalies if a.severity == "critical"]
    if len(critical_anomalies) > 2:
        return "FAIL"

    golden_failures = [g for g in golden_results if not g.found or not g.selections_valid]
    if len(golden_failures) > len(golden_results) // 2:
        return "FAIL"

    # WARN conditions
    if len(probability_anomalies) > 5:
        return "WARN"

    if structural.matching_rate < Decimal("85"):
        return "WARN"

    if any(not g.found for g in golden_results):
        return "WARN"

    return "PASS"
```

### Report Format

```
╔═══════════════════════════════════════════════════════════════════════╗
║                    SCRAPER VALIDATION REPORT                           ║
║                    2026-01-15 10:30:45 UTC                             ║
╠═══════════════════════════════════════════════════════════════════════╣

REFERENCE: Ladbrokes (Entain) - 10 EPL events indexed

═══════════════════════════════════════════════════════════════════════
LA LIGA (10 events reference)
═══════════════════════════════════════════════════════════════════════

✅ LADBROKES (reference)     10 events | 30 odds | PASS
✅ BETFAIR (structure only)  10 events | 30 odds | PASS (exchange)
✅ MINTBET                   10 events | 30 odds | 100% coverage | PASS
✅ XBET                       9 events | 27 odds |  90% coverage | PASS
✅ TRADIEBET                 10 events | 30 odds | 100% coverage | PASS
⚠️ BETVISTA                   8 events | 24 odds |  80% coverage | WARN
   └─ Missing: Elche v Sevilla, Mallorca v Athletic
❌ BROKENBOOKIE               4 events | 12 odds |  40% coverage | FAIL
   └─ Anomaly: Real Madrid home = 1.02 (ref: 1.13, 11.2pp gap)
   └─ Anomaly: Barcelona away = 8.50 (ref: 2.40, 29.8pp gap)
   └─ Missing: 6 events

GOLDEN FIXTURES:
✅ Real Madrid v Barcelona: Found in 19/21 bookmakers
✅ Atletico v Sevilla: Found in 18/21 bookmakers

═══════════════════════════════════════════════════════════════════════
SUMMARY
═══════════════════════════════════════════════════════════════════════
Bookmakers: 18 PASS | 2 WARN | 1 FAIL
Coverage: 95% average across all bookmakers
Action Required: Review BROKENBOOKIE anomalies (possible parsing bug)

═══════════════════════════════════════════════════════════════════════
```

---

## File Structure

```
apps/worker/src/
├── validation/
│   ├── __init__.py
│   ├── structural_validator.py    # Phase 1: Structure checks
│   ├── probability_validator.py   # Phase 2: Implied probability comparison
│   ├── golden_fixtures.py         # Phase 3: Curated fixture validation
│   ├── score_calculator.py        # Phase 4: Final scoring
│   ├── report_generator.py        # Terminal/JSON output
│   └── config.py                  # Thresholds, expected counts, golden fixtures
│
├── jobs/
│   ├── scrape_service.py          # Modified: Add validation hook
│   └── save_odds.py               # Modified: Add validation metadata
│
└── scripts/
    └── validate_scrapers.py       # CLI entry point
```

---

## Integration Points

### 1. Scrape Service Hook

```python
# In scrape_service.py

async def scrape_all_active_bookmakers(self, ...):
    # ... existing scrape logic ...

    # Run validation (non-blocking)
    if self.validation_enabled:
        try:
            validation_result = await self._run_validation(results)

            # Alert on failures (non-blocking)
            if validation_result.has_failures:
                self._send_validation_alert(validation_result)
        except Exception as e:
            logger.error(f"Validation failed (non-blocking): {e}")

    return {
        # ... existing return ...
        "validation": validation_result.to_dict() if validation_result else None
    }
```

### 2. Alert Integration

```python
def _send_validation_alert(self, result: ValidationResult):
    """Send alert for validation failures (non-blocking)"""

    # Sentry
    if SENTRY_AVAILABLE:
        capture_message(
            f"Scraper validation failed: {result.failed_bookmakers}",
            level="warning",
            extras=result.to_dict()
        )

    # Future: Slack/Discord webhook
    # webhook_url = os.getenv("VALIDATION_ALERT_WEBHOOK")
    # if webhook_url:
    #     requests.post(webhook_url, json=result.to_summary())
```

### 3. Quarantine Feed (Future)

```python
# When validation fails, mark odds as "quarantined" instead of blocking
# Users see quarantined odds with warning indicator

class OddsSnapshot:
    # ... existing fields ...
    validation_status: Literal["valid", "quarantined", "unchecked"] = "unchecked"
    validation_notes: Optional[str] = None
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Non-blocking validation** | User requests never wait on validation |
| **Implied probability (not raw odds %)** | Mathematically correct comparison metric |
| **Ladbrokes as bootstrap, consensus as goal** | Single reference is fragile; consensus is robust |
| **Market-type aware thresholds** | Favorites vs longshots have different spreads |
| **Betfair = structure only** | Exchange odds diverge from bookmaker odds by design |
| **Golden fixtures per league** | Fast regression detection, minimal config |
| **Quarantine not block** | Users see data with warning, not empty page |

---

## Scalability

| Factor | Design | Complexity |
|--------|--------|------------|
| 100+ bookmakers | Compare each to reference once | O(n) |
| 14 leagues | Run validation per league | O(14) per bookmaker |
| New bookmaker | Auto-validated against consensus | Zero config |
| 1000+ users | Server-side only, no per-user work | O(1) per user |
| Code regression | Golden fixtures catch immediately | O(1) per deploy |

---

## Implementation Phases

### Phase A: MVP (COMPLETE)
- [x] Structural validator (Phase 1)
- [x] Basic probability comparison (Phase 2 - Ladbrokes only)
- [x] Terminal report generator
- [x] CLI script
- [x] Golden fixtures config
- [x] Sentry alert integration
- [x] Add to scrape pipeline (non-blocking)

### Phase B: Production (Future)
- [ ] Consensus median calculation
- [ ] Test with live scraping

### Phase C: Polish (Future)
- [ ] Quarantine feed implementation
- [ ] Historical validation tracking
- [ ] Slack/Discord webhooks
- [ ] Dashboard metrics

---

## Commands

```bash
# Run validation manually
docker exec mb_api python -m worker.src.scripts.validate_scrapers

# Validate specific league
docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition laliga

# Validate specific bookmaker
docker exec mb_api python -m worker.src.scripts.validate_scrapers --bookmaker mintbet

# Output JSON (for CI/CD)
docker exec mb_api python -m worker.src.scripts.validate_scrapers --format json
```

---

## How to Interpret Results

### Status Meanings

| Status | Meaning | Action Required |
|--------|---------|-----------------|
| **PASS** | All checks within thresholds | None - scraper working correctly |
| **WARN** | Minor issues detected | Review when convenient, not urgent |
| **FAIL** | Critical issues detected | Investigate immediately - likely bug |

### What Each Metric Means

#### Event Count
- **What it shows**: Number of matches scraped
- **Good range**: Within expected min/max for that league (e.g., EPL: 3-20)
- **Too low**: Scraper may be broken, wrong page, or API changed
- **Too high**: Unusual, but may indicate duplicate scraping

#### Coverage Percent
- **What it shows**: % of bookmaker's odds that could be compared to reference
- **85%+**: Normal - some events may not be on all bookmakers
- **70-85%**: Warning - check if missing events are expected
- **<70%**: Fail - likely scraper issue or wrong competition mapping

#### Anomaly Count
- **What it shows**: Number of odds that differ significantly from reference
- **0-5**: Normal - minor differences are expected
- **5-10**: Warning - investigate top anomalies
- **10+**: Likely parsing bug or swapped data

#### Probability Gap (pp)
- **What it shows**: Difference in implied probability between bookmaker and reference
- **Example**: Odds 2.00 = 50% prob, Odds 2.20 = 45.45% prob, Gap = 4.55pp
- **Normal range**: 0-3pp for favorites, 0-5pp for longshots
- **Warning**: 3-6pp (favorites) or 5-10pp (longshots)
- **Critical**: >6pp (favorites) or >10pp (longshots)

### Common Issues and What They Mean

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| **0 events** | Scraper dead, API changed, wrong URL | Check scraper logs, test API manually |
| **All odds out of bounds** | Parsing bug, HTML structure changed | Review scraper parsing code |
| **Low coverage but events match** | Missing markets (only getting some selections) | Check market/selection parsing |
| **High anomaly count, same pattern** | Swapped home/away, wrong team mapping | Review normalization service |
| **One selection always off** | Draw/home/away key swapped | Check selection_key assignment |
| **Golden fixture missing** | Event name normalization issue | Add team alias to normalization |

### Reading the Terminal Report

```
===========================================================================
                    SCRAPER VALIDATION REPORT
                    2026-01-15 12:00:00 UTC
===========================================================================

REFERENCE: LADBROKES - 10 events indexed
           ^^^^^^^^^ Reference bookmaker used for comparison
                     ^^ Number of events in reference (your baseline)

===========================================================================
LALIGA (10 events reference)
===========================================================================

  OK  LADBROKES             10 events | PASS (reference)
  ^^  ^^^^^^^^^             ^^^^^^^^^   ^^^^  ^^^^^^^^^
  |   Bookmaker name        Event count Status Note (reference = used for comparison)

  OK  BETFAIR                8 events | PASS (structure only) (exchange)
                                        ^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^
                                        Betfair only gets structure check (no odds comparison)

  OK  MINTBET               10 events | PASS | 95% coverage
                                              ^^^^^^^^^^^
                                              95% of odds could be compared to reference

  !   TRADIEBETT             8 events | WARN | 80% coverage
  ^   Below threshold (85%) - investigate missing events

     -> Real Madrid v Levante: Home = 1.05 (ref: 1.12, 6.2pp gap)
        ^^^^^^^^^^^^^^^^^^^^  ^^^^   ^^^^   ^^^^  ^^^^^^^^^^^^^^^
        Event name            Sel.   Odds   Ref   Probability gap (too high!)

  X   BROKENBOOKIE           4 events | FAIL
  ^   Critical failure - investigate immediately

GOLDEN FIXTURES:
  OK  Real Madrid v Barcelona: Found in 19/21 bookmakers
      ^^^^^^^^^^^^^^^^^^^^^^^^ High-profile fixture checked across all bookmakers
```

### When to Take Action

**Immediate (FAIL status)**:
1. Check scraper logs: `docker logs mb_api | grep -i [bookmaker]`
2. Test API manually: Use curl/browser to hit the API endpoint
3. Review recent code changes
4. Check if website structure changed

**Soon (WARN status)**:
1. Review anomalies - are they real or false positives?
2. Check if missing events are genuinely not available
3. Consider adding team aliases if normalization fails

**Never panic about**:
- Betfair showing different odds (exchanges always differ from bookmakers)
- 1-2pp gaps (normal market variation)
- Missing 1-2 events (bookmakers have different coverage)

### Thresholds Summary

| Check | PASS | WARN | FAIL |
|-------|------|------|------|
| Event count | Within min-max | - | Outside min-max |
| Coverage | ≥85% | 70-85% | <70% |
| Anomalies | ≤5 | 5-10 | - |
| Critical anomalies | ≤2 | - | >2 |
| Golden fixtures | All found | Some missing | >50% missing |
| Probability gap (favorite) | <3pp | 3-6pp | >6pp |
| Probability gap (longshot) | <5pp | 5-10pp | >10pp |

### Probability Gap Examples

| Bookmaker Odds | Reference Odds | Gap | Severity |
|----------------|----------------|-----|----------|
| 1.50 (66.7%) | 1.55 (64.5%) | 2.2pp | OK |
| 2.00 (50.0%) | 2.20 (45.5%) | 4.5pp | WARN |
| 1.80 (55.6%) | 2.40 (41.7%) | 13.9pp | CRITICAL |
| 8.00 (12.5%) | 10.00 (10.0%) | 2.5pp | OK (longshot) |
| 8.00 (12.5%) | 15.00 (6.7%) | 5.8pp | WARN (longshot) |

---

## Quick Reference Commands

```bash
# Validate La Liga
docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition laliga

# Validate EPL
docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition epl

# Validate specific bookmaker
docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition laliga --bookmaker mintbet

# List all competitions
docker exec mb_api python -m worker.src.scripts.validate_scrapers --list-competitions

# JSON output (for scripts/CI)
docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition laliga --format json

# Run scrape then validate
docker exec mb_api python ../worker/src/manual_scrape.py
docker exec mb_api python -m worker.src.scripts.validate_scrapers --competition laliga
```

---

*Document version: 2.0*
*Created: 2026-01-15*
*Updated: 2026-01-15 (added interpretation guide)*
*Author: Claude + Human collaboration*
