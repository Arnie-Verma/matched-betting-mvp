# PR-R3 Matcher Hot Path Contract

Date: 2026-02-21  
Slice: PR-R3 (Matcher Hot Path Refactor)

## Scope
- Removed debug `print()` calls from `/odds/matcher` request path.
- Replaced per-event/per-market/per-selection query fan-out with a set-based preload strategy.
- Preserved response contract (`OddsMatchResponse` fields unchanged).
- Added matcher hot-path regression/perf tests.

## Query Strategy Change
- Before:
  - Query events
  - For each event-group: query markets
  - For each market: query selections
  - For each selection-group: query back odds + lay odds
  - Result: N+1 query growth with event/market cardinality
- After:
  - Query events once
  - Query all active matcher markets for all candidate events once
  - Query all selections for those markets once
  - Query all current odds for those selections/bookmakers once
  - Group + rank entirely in memory

## Evidence Metrics
- JSON metrics: `docs/evidence/phase-a-hardening/2026-02-11/pr11_matcher_perf_metrics.json`
- Synthetic representative load (80 events, 3 bookmakers, 20 iterations):
  - Legacy median query count: `482`
  - Optimized median query count: `4`
  - Legacy p95 latency: `634.419 ms`
  - Optimized p95 latency: `34.983 ms`
  - Opportunity count parity preserved (`160` mean in both modes)

## Reproducible Commands
```powershell
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_odds_matcher_hot_path.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
python -m py_compile apps/api/src/api/routers/odds_matcher.py apps/api/src/api/scripts/generate_pr11_matcher_perf_metrics.py apps/api/tests/test_odds_matcher_hot_path.py
$env:PYTHONPATH='apps/api/src'; python apps/api/src/api/scripts/generate_pr11_matcher_perf_metrics.py
```

## Command Output Summary
- `apps/api/tests/test_odds_matcher_hot_path.py`: `2 passed`
- `apps/api/tests/test_bookmaker_freeze.py`: `6 passed`
- `apps/api/tests/test_unibet_freeze_integration.py`: `1 passed`
- `py_compile`: success
- Perf metrics JSON generated successfully.

## Contract Assertions
- Query count reduced materially versus legacy N+1 baseline.
- p95 latency improved materially on representative synthetic load.
- Response schema remains unchanged (validated by test against `OddsMatchResponse` fields).
- No matcher request-path `print()` calls remain (guarded by regression test).
