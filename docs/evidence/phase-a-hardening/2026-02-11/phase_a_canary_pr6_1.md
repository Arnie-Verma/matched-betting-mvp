# Phase A Canary Report

- Started: 2026-02-15T07:04:17.734999+00:00
- Ended: 2026-02-15T07:34:33.017239+00:00
- Duration (seconds): 1815.28
- Cycles completed: 14

## Latency Metrics

- Scrape p50: 137.22s
- Scrape p95: 356.44s
- Scrape avg: 128.30s
- Validation p50: 1.06s
- Validation p95: 2.58s
- Cycle p50: 138.01s
- Cycle p95: 357.95s

## Breaker Metrics

- Cycles with open breakers: 0
- Open breaker cycles: []
- Max open breakers in a cycle: 0
- Max half-open breakers in a cycle: 0

## Validation Gate Metrics

- In-scope FAIL cycles: 14
- In-scope FAIL cycle IDs: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
- In-scope FAIL rows: 504

## Gate Result

- Requires min cycles: True
- Requires min duration: True
- Requires in-scope FAIL=0: True
- PASS: False
