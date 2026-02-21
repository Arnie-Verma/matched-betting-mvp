# Phase A Canary Report

- Started: 2026-02-21T09:54:13.768619+00:00
- Ended: 2026-02-21T10:30:11.600399+00:00
- Duration (seconds): 2157.83
- Cycles completed: 10

## Latency Metrics

- Scrape p50: 133.03s
- Scrape p95: 388.59s
- Scrape avg: 161.28s
- Validation p50: 0.72s
- Validation p95: 1.06s
- Cycle p50: 133.74s
- Cycle p95: 389.47s

## Breaker Metrics

- Cycles with open breakers: 0
- Open breaker cycles: []
- Max open breakers in a cycle: 0
- Max half-open breakers in a cycle: 0

## Reliability Metrics

- Scrape success rate: 0.9857
- Successful bookmakers: 207
- Total bookmakers considered: 210
- Cycles considered for success rate: 10

## Validation Gate Metrics

- In-scope FAIL cycles: 0
- In-scope FAIL cycle IDs: []
- In-scope FAIL rows: 0

## Gate Result

- PASS: False

| Criterion | Threshold | Observed | Pass |
|---|---:|---:|:---:|
| min_cycles | 10 | 10 | PASS |
| min_duration_seconds | 1800.0000 | 2157.8318 | PASS |
| in_scope_fail_cycle_count | 0 | 0 | PASS |
| min_scrape_success_rate | 0.7500 | 0.9857 | PASS |
| max_open_breaker_cycle_count | 0 | 0 | PASS |
| max_scrape_p95_seconds | 360.0000 | 388.5932 | FAIL |

### Failure Reasons
- max_scrape_p95_seconds failed: expected <= 360.0, observed 388.5931831479072

## Repro Command

```bash
docker exec mb_api sh -lc 'cd /workspace && export PYTHONPATH=/workspace/apps/api/src:/workspace/apps/worker/src && python /workspace/apps/worker/src/scripts/run_phase_a_canary.py --min-duration-seconds 1800 --min-cycles 10 --max-cycles 20 --sleep-seconds 60 --output-prefix pr16_scope_gate_canary'
```

## Freeze Verification

- `docker exec mb_api env | rg "^BOOKMAKER_FREEZE_UNIBET="` -> `BOOKMAKER_FREEZE_UNIBET=true`
- `docker exec mb_worker env | rg "^BOOKMAKER_FREEZE_UNIBET="` -> `BOOKMAKER_FREEZE_UNIBET=true`
- `docker exec mb_db psql -U postgres -d mb_dev -c "SELECT code, is_active FROM bookmakers WHERE code='unibet';"` -> `unibet | f`
