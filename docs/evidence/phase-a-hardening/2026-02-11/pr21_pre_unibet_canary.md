# Phase A Canary Report

- Started: 2026-02-22T05:56:04.880900+00:00
- Ended: 2026-02-22T06:26:17.808024+00:00
- Duration (seconds): 1812.93
- Cycles completed: 12

## Latency Metrics

- Scrape p50: 78.24s
- Scrape p95: 242.16s
- Scrape avg: 96.16s
- Validation p50: 1.23s
- Validation p95: 1.74s
- Cycle p50: 79.30s
- Cycle p95: 243.61s

## Breaker Metrics

- Cycles with open breakers: 0
- Open breaker cycles: []
- Max open breakers in a cycle: 0
- Max half-open breakers in a cycle: 0

## Reliability Metrics

- Scrape success rate: 0.9802
- Successful bookmakers: 247
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
| min_duration_seconds | 1800.0000 | 1812.9271 | PASS |
| in_scope_fail_cycle_count | 0 | 0 | PASS |
| min_scrape_success_rate | 0.7500 | 0.9802 | PASS |
| max_open_breaker_cycle_count | 0 | 0 | PASS |
| max_scrape_p95_seconds | 360.0000 | 242.1597 | PASS |
