# ADR-0012: Bookmaker x Competition Coverage Scope Policy

- Status: Accepted
- Date: 2026-02-15
- Owners: @platform

## Context
Validation status was over-penalizing bookmaker/competition pairs that are currently
not expected to provide coverage in local Phase A windows. In PR6, NBL had persistent
`FAIL` statuses for books returning `0 events`, even when those books were outside
the intended NBL coverage scope.

At the same time, we still need strict failure behavior for in-scope bookmakers:
`0 events` should remain a blocking signal.

## Decision
Add explicit bookmaker x competition coverage scope policy in validation config and
apply it in final score classification:

1. Add `BOOKMAKER_COMPETITION_COVERAGE_POLICY` in `validation/config.py`.
2. Add `ValidationConfig.get_bookmaker_competition_scope(bookmaker, competition)`.
3. In `validation/score_calculator.py`:
   - out-of-scope + zero-event => `SKIP`
   - in-scope + zero-event => existing `FAIL` rules remain.
4. Initial scope policy is NBL-only out-of-scope list:
   - `betblitz`, `starsports`, `truebet`, `wizbet`

## Consequences
Positive:
- Removes false blocking failures for explicitly out-of-scope NBL books.
- Keeps strict blocking behavior for in-scope broken output.
- Preserves compatibility with alerts and gate logic (`has_failures` driven by `FAIL` only).

Tradeoffs:
- Scope policy must be actively maintained as bookmaker coverage expectations evolve.
- Misclassification risk exists if policy drifts from real onboarding intent.

Operational impact:
- Reporting now distinguishes neutral scope-based `SKIP` from genuine in-scope `FAIL`.
- Canary gate still blocks promotion when in-scope failures persist in other competitions.

## Alternatives Considered
1. Lower thresholds globally:
- Rejected; reduces signal quality and masks true in-scope failures.

2. Treat all zero-event windows as `SKIP`:
- Rejected; would hide genuinely broken in-scope scrapers.

3. Hardcode NBL exceptions in score calculator:
- Rejected; less maintainable than explicit config policy.

## Follow-ups
1. Expand scope policy only with explicit evidence and reviewer approval.
2. Add policy review step to phase gate checklist.
3. Revisit EPL/boxing in-scope failures surfaced by canary before declaring Phase A GO.
