# ADR-0013: PR7 EPL and Boxing FAIL Cluster Remediation

- Status: Accepted
- Date: 2026-02-15
- Owners: @matched-betting

## Context
Phase A canary in PR6.1 remained NO-GO due persistent in-scope FAIL clusters:
- EPL: widespread `Event coverage 53.19% < 55%`
- Boxing: widespread `Coverage 0% < 70%`

Failure decomposition showed:
- EPL failures were denominator/feed-window mismatches on Punterstech brands caused by filter and payload truncation behavior.
- Boxing failures were concentrated on books with shallow/non-overlapping fight catalogs compared to reference.

## Decision
1. EPL remediation (in-scope):
- Harden Punterstech competition filter matching for normalized England/English EPL variants.
- Raise default soccer `next-to-go` result limit to avoid truncating EPL fixtures on high-volume brands.

2. Boxing remediation (scope policy):
- Define explicit boxing in-scope books: `ladbrokes`, `neds`, `betfair`.
- Treat out-of-scope boxing books as `SKIP` (non-gating) even when they return some events.

3. Validation semantics:
- Update scope policy behavior from `out-of-scope + zero-event => SKIP` to `out-of-scope => SKIP`.

## Consequences
Benefits:
- Removes false in-scope FAIL clusters for EPL and boxing.
- Aligns validation gate with explicit business scope for boxing.
- Produces stable canary signal for GO/NO-GO decisions.

Tradeoffs:
- Out-of-scope books are intentionally excluded from boxing gate strictness.
- WARN volume remains non-zero on calibrated anomaly/event-count checks and still needs monitoring.

## Alternatives Considered
1. Lower EPL threshold further.
- Rejected as primary fix; does not address root feed truncation/filter mismatch.

2. Keep boxing books in-scope and tune probability thresholds.
- Rejected; mismatch is mostly catalog overlap/scope, not pricing drift quality.

3. Keep out-of-scope SKIP only for zero-event.
- Rejected; did not resolve boxing FAIL rows with non-zero but non-overlapping catalogs.

## Follow-ups
- Keep Unibet frozen until explicit activation decision after GO confirmation.
- Revisit boxing scope policy when additional books show sustained fixture overlap.
- Continue canary tracking for WARN trend and breaker stability.
