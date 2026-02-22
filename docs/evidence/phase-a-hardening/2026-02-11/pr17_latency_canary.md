# Phase A Canary Report

- Started: 2026-02-22T02:57:02.568973+00:00
- Ended: 2026-02-22T03:28:15.588711+00:00
- Duration (seconds): 1873.02
- Cycles completed: 12

## Latency Metrics

- Scrape p50: 84.37s
- Scrape p95: 245.20s
- Scrape avg: 101.76s
- Validation p50: 0.61s
- Validation p95: 0.83s
- Cycle p50: 85.07s
- Cycle p95: 246.11s

## Breaker Metrics

- Cycles with open breakers: 0
- Open breaker cycles: []
- Max open breakers in a cycle: 0
- Max half-open breakers in a cycle: 0

## Reliability Metrics

- Scrape success rate: 0.9881
- Successful bookmakers: 249
- Total bookmakers considered: 252
- Cycles considered for success rate: 12

## Validation Gate Metrics

- In-scope FAIL cycles: 0
- In-scope FAIL cycle IDs: []
- In-scope FAIL rows: 0

## Gate Result

- PASS: True

| Criterion | Threshold | Observed | Pass |
|---|---:|---:|:---:|
| min_cycles | 10 | 12 | PASS |
| min_duration_seconds | 1800.0000 | 1873.0197 | PASS |
| in_scope_fail_cycle_count | 0 | 0 | PASS |
| min_scrape_success_rate | 0.7500 | 0.9881 | PASS |
| max_open_breaker_cycle_count | 0 | 0 | PASS |
| max_scrape_p95_seconds | 360.0000 | 245.1969 | PASS |

## Repro Command

```bash
docker exec mb_api sh -lc 'cd /workspace && export PYTHONPATH=/workspace/apps/api/src:/workspace/apps/worker/src && python /workspace/apps/worker/src/scripts/run_phase_a_canary.py --min-duration-seconds 1800 --min-cycles 10 --max-cycles 20 --sleep-seconds 60 --output-prefix pr17_latency_canary'
```

## Runtime Notes

- Repeated scrape errors observed during run:
  - `ERROR:scraper.betfair:Scrape error: No events captured from Betfair for ice_hockey`
  - `ERROR:scraper.betfair:Scrape error: No events captured from Betfair for ice_hockey`
  - `ERROR:scraper.betfair:Scrape error: No events captured from Betfair for ice_hockey`
- Gate remained GO because reliability and breaker thresholds passed, and scrape p95 stayed below threshold.

## Freeze Verification

- `docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'` -> `BOOKMAKER_FREEZE_UNIBET=true`
- `docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'` -> `BOOKMAKER_FREEZE_UNIBET=true`
- `docker exec mb_db psql -U postgres -d mb_dev -c "select code, is_active from bookmakers where code='unibet';"` -> `unibet | f`
