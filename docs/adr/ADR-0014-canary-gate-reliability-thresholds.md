# ADR-0014: Canary Gate Reliability Thresholds

- Status: Accepted
- Date: 2026-02-21
- Owners: @matched-betting

## Context
Phase A canary GO/NO-GO decisions were primarily validation-gated (`in-scope FAIL=0`)
with minimum cycles/runtime checks. For scale to 100+ bookmakers, this is not
sufficient by itself because:

1. A canary can be validation-clean but operationally unhealthy (high scrape failures).
2. Breaker instability is an early indicator of system stress that should gate promotion.
3. High scrape p95 latency degrades user freshness and should be blocked before rollout.

We need deterministic, explainable, and reproducible canary gate contracts that combine
validation and runtime reliability.

## Decision
Add a pure gate evaluation contract in `run_phase_a_canary.py`:

- `evaluate_gate(summary, thresholds)` returns criterion-level pass/fail and
  explicit `failure_reasons`.
- Gate thresholds are CLI-configurable with defaults:
  - `min_cycles = 10`
  - `min_duration_seconds = 1800`
  - `requires_in_scope_fail_zero = true`
  - `min_scrape_success_rate = 0.75`
  - `max_open_breaker_cycle_count = 0`
  - `max_scrape_p95_seconds = 360`

Metric definitions:

1. `scrape_success_rate`:
   - numerator: sum of `cycle.scrape.bookmakers_scraped`
   - denominator: sum of `cycle.scrape.total_bookmakers` across cycles where
     `total_bookmakers > 0`
2. `open_breaker_cycle_count`:
   - count of cycles where `cycle.breaker.open_count > 0`
3. `scrape_p95_seconds`:
   - p95 of `cycle.scrape.duration_seconds`

Gate pass requires all criteria to pass.

## Consequences
Benefits:

1. Promotion decisions become deterministic and explainable (`failure_reasons`).
2. Reliability regressions are blocked even when validation status looks clean.
3. Gate policy scales with bookmaker count by using aggregate operational metrics.

Tradeoffs:

1. Initial thresholds can be noisy in constrained local environments.
2. Overly strict thresholds can block progress without indicating code defects.

Operational impact:

1. Canary JSON and markdown reports include criterion threshold, observed value,
   pass/fail, and explicit reasons for NO-GO.
2. Evidence reviews can compare historical canaries against consistent policy.

## Alternatives Considered
1. Keep validation-only gate.
- Rejected: misses reliability degradations (failure rate, breaker opens, latency spikes).

2. Hardcode reliability thresholds in function body.
- Rejected: harder to tune and less reproducible across environments.

3. Rely on manual interpretation of latency/failure charts.
- Rejected: non-deterministic and error-prone for frequent rollout decisions.

## Follow-ups
1. After R2 + R3 execution improvements, tighten defaults:
   - `min_scrape_success_rate` to `0.85`
   - `max_scrape_p95_seconds` to `300`
   - keep `max_open_breaker_cycle_count = 0`
2. Monitor false NO-GO patterns and adjust thresholds with evidence-backed ADR updates.
3. Keep Unibet frozen (`BOOKMAKER_FREEZE_UNIBET=true`, `unibet.is_active=false`) until
   explicit activation approval.

## Rollback Procedure
If the gate is too strict/noisy for local canary signal:

1. Use CLI threshold overrides for temporary evidence runs.
2. Revert to previous gate behavior by restoring the pre-ADR evaluator logic in
   `run_phase_a_canary.py` (min cycles, min duration, in-scope FAIL=0 only).
3. Preserve before/after evidence artifacts and open a follow-up ADR to adjust defaults
   rather than silently weakening the policy.
