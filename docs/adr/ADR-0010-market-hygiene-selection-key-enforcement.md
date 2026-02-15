# ADR-0010: Market Hygiene + Selection-Key Enforcement (Entain/Punterstech)

- Status: Accepted
- Date: 2026-02-12
- Owners: @team

## Context
Phase A PR4 requires strict market hygiene for matcher feeds before any new bookmaker
onboarding resumes.

Observed issues in current data included:
- disallowed markets (futures/outrights/partials/props) leaking into `match_winner`
- non-deterministic `selection_key` values in matcher markets
- market-shape drift (for example one-sided rows or wrong side count for competition type)
- stale pre-hardening rows remaining `is_current=true` after parser logic changes

These issues degraded validation trust and matcher quality.

## Decision
1. Enforce sport-aware matcher market allow/deny policy in both platform scrapers:
   - Entain: `apps/worker/src/scrapers/entain_scraper.py`
   - Punterstech: `apps/worker/src/scrapers/punterstech_scraper.py`
2. Enforce deterministic matcher market shape at parse time:
   - soccer (`epl`) requires `home/draw/away`
   - `nba/nhl/boxing/nbl` require `home/away`
3. Enforce `selection_key` hygiene for matcher markets:
   - only `home`, `away`, `draw` are accepted
   - unsupported keys are dropped at parse time
4. Add focused regression tests for:
   - market allow/deny per sport
   - market-shape enforcement
   - selection-key stability
5. Run one-time data hygiene cleanup to retire stale invalid `is_current=true` rows
   left from pre-hardening runs, with query outputs stored in evidence artifacts.

## Consequences
Benefits:
- Matcher path only sees fixture-safe, shape-valid match-winner markets.
- Deterministic `selection_key` behavior improves cross-bookmaker matching consistency.
- DB `is_current=true` state aligns with hardening policy rather than legacy pollution.

Tradeoffs:
- More aggressive filtering can reduce event/odds volume when source data is incomplete.
- Existing validation thresholds may still produce `WARN/FAIL` unrelated to market hygiene.

## Alternatives Considered
1. Rely on matcher-side filtering only.
- Rejected: bad rows still pollute persistence and validation surfaces.

2. Delay stale-row cleanup until canary phase.
- Rejected: evidence would remain inconsistent with enforced policy during PR4.

## Follow-ups
1. PR5: add full Entain parity suite (`apps/worker/tests/test_entain_scraper.py`).
2. PR6: include hygiene metrics in canary/go-no-go evidence output.
3. Review validation threshold tuning separately (outside PR4 scope).
