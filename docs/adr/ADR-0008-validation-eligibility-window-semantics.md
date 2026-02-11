# ADR-0008: Validation Eligibility Window Semantics (`SKIP` / `N_A`)

- Status: Accepted
- Date: 2026-02-11
- Owners: @team

## Context
Phase A hardening found false WARN/FAIL outcomes when the reference bookmaker
had zero fixtures that matched the expected market shape for a competition
window (for example, no valid 3-way soccer fixtures in the current slice).

This produced noisy gate outcomes and made promotion decisions non-deterministic.

## Decision
Adopt explicit eligibility-window semantics in validation:
1. Define eligible reference fixtures by required selection keys per competition.
2. Compute event coverage and probability comparisons only against eligible
   reference fixtures.
3. If eligible reference fixture count is zero:
   - Reference bookmaker status = `N_A`
   - Non-reference bookmaker status = `SKIP`
4. Include eligible vs total reference fixture counts in report output.

## Consequences
Benefits:
- Prevents false FAIL/WARN caused by empty or partial eligibility windows.
- Makes validation outputs explainable and stable across repeated runs.
- Keeps hard-fail logic focused on real scraper defects.

Tradeoffs:
- `SKIP`/`N_A` introduce two additional statuses that downstream reporting must handle.
- A `SKIP`/`N_A` run is not sufficient evidence for promotion; a later eligible run is required.

## Alternatives Considered
1. Keep PASS/WARN/FAIL only and coerce empty windows to PASS.
- Rejected: masks missing comparability and reduces gate signal quality.

2. Mark empty windows as FAIL.
- Rejected: creates persistent false negatives during seasonal or sparse windows.

## Follow-ups
1. Use priority competition evidence packs to verify repeatability (`epl`, `nba`, `nhl`, `boxing`, `nbl`).
2. Ensure gate checks treat unresolved `FAIL` as blocking and `SKIP`/`N_A` as neutral but non-promotable evidence.
3. Extend canary evidence format to include eligibility-window counts.
