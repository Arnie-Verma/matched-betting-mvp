# Phase A Canary Report

- Started: 2026-02-21T08:30:39.477291+00:00
- Ended: 2026-02-21T09:35:26.210823+00:00
- Duration (seconds): 3886.73
- Cycles completed: 21

## Latency Metrics

- Scrape p50: 129.34s
- Scrape p95: 262.98s
- Scrape avg: 110.72s
- Validation p50: 0.89s
- Validation p95: 1.41s
- Cycle p50: 130.05s
- Cycle p95: 265.30s

## Breaker Metrics

- Cycles with open breakers: 0
- Open breaker cycles: []
- Max open breakers in a cycle: 0
- Max half-open breakers in a cycle: 0

## Reliability Metrics

- Scrape success rate: 0.9841
- Successful bookmakers: 434
- Total bookmakers considered: 441
- Cycles considered for success rate: 21

## Validation Gate Metrics

- In-scope FAIL cycles: 21
- In-scope FAIL cycle IDs: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
- In-scope FAIL rows: 21

## Gate Result

- PASS: False

| Criterion | Threshold | Observed | Pass |
|---|---:|---:|:---:|
| min_cycles | 10 | 21 | PASS |
| min_duration_seconds | 3600.0000 | 3886.7335 | PASS |
| in_scope_fail_cycle_count | 0 | 21 | FAIL |
| min_scrape_success_rate | 0.7500 | 0.9841 | PASS |
| max_open_breaker_cycle_count | 0 | 0 | PASS |
| max_scrape_p95_seconds | 360.0000 | 262.9802 | PASS |

### Failure Reasons
- in_scope_fail_cycle_count failed: expected == 0, observed 21
