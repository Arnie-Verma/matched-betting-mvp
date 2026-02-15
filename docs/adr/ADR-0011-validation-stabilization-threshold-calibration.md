# ADR-0011: Validation Stabilization via Competition-Aware Threshold Calibration

- Status: Accepted
- Date: 2026-02-15
- Owners: @team

## Context
After PR4 market-hygiene enforcement, Phase A validation still produced many FAIL/WARN
outcomes for priority competitions (`epl`, `nba`, `nhl`, `boxing`, `nbl`).

Root causes from evidence:
- structural warnings from conservative event-count ceilings for high-volume windows
- event-coverage FAILs in competitions with platform-window asymmetry (notably `epl`, `nbl`)
- probability-anomaly FAILs dominated by competition-specific variance (`nba`, `nhl`)

This blocked stabilization progress even when parser/market hygiene behavior was correct.

## Decision
1. Calibrate expected event-count ceilings for priority competitions to reflect observed
   local windows (`epl`, `nba`, `nhl`, `nbl`).
2. Add competition-specific event-coverage thresholds in `ValidationConfig`:
   - `epl`, `nbl`, `nhl` overrides (in addition to existing `boxing`, `nba` overrides).
3. Add competition-specific anomaly thresholds (warn + critical) and consume them in
   `ScoreCalculator` for final status classification.
4. Keep anomaly detection logic unchanged; only final scoring thresholds are calibrated.

## Consequences
Benefits:
- Large reduction in false FAIL/WARN classifications in PR6 evidence.
- Better separation between structural zero-event failures and threshold noise.
- Clearer signal for remaining real blockers (for example NBL books with `0 events`).

Tradeoffs:
- Looser thresholds can mask genuine price divergence if left unmonitored.
- Requires follow-up canary evidence to validate long-term safety of calibrated values.

## Alternatives Considered
1. Keep global thresholds only.
- Rejected: produced persistent false negatives across priority competitions.

2. Disable anomaly-based scoring entirely for stabilization.
- Rejected: removes a useful safety signal; calibration is safer than disabling.

## Follow-ups
1. Revisit thresholds after PR6 canary trend evidence.
2. Keep Unibet frozen until full Phase A GO gate is met.
3. Add explicit threshold-review checkpoint in canary report output.
