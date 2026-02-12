# ADR-0009: Priority Normalization Alias Hardening (Entain + Punterstech)

- Status: Accepted
- Date: 2026-02-11
- Owners: @team

## Context
Phase A PR3 requires normalization hardening before additional bookmaker onboarding.
Observed cross-platform mismatches in priority competitions were primarily caused by:
- missing competition aliases (for example `National Basketball Association`, `NHL Hockey`)
- team-name alias gaps (`Manchester Utd`, `NY Knicks`)
- event normalization applying multiple string replacements in-sequence, which could
  create unstable keys (for example duplicate replacement effects)
- abbreviated fighter naming variants in boxing (`N. Inoue`, `C. Simpson`, `Jr`)

## Decision
1. Expand canonical competition and team alias coverage for Entain + Punterstech
   priority competitions (`epl`, `nba`, `nhl`, `boxing`, `nbl`).
2. Make event normalization side-based and reuse team normalization per side:
   - normalize each participant independently
   - sort normalized participants for order-invariant event keys
3. Harden individual-name normalization for boxing-style abbreviations/suffixes:
   - normalize punctuation
   - drop trailing person suffixes (`jr`, `sr`, `ii`, `iii`, `iv`)
   - drop leading single-letter initials in two-token names
4. Add focused regression tests covering the priority competitions and alias cases.

## Consequences
Benefits:
- Reduced cross-platform event-key mismatches for priority competitions.
- More deterministic matching between Entain and Punterstech naming variants.
- Better stability for validation/event coverage calculations.

Tradeoffs:
- Broader alias mapping may require periodic tuning as new brands/leagues are added.
- Boxing abbreviation handling is heuristic and should be monitored with evidence checks.

## Alternatives Considered
1. Keep existing replacement-based event normalization.
- Rejected: produced avoidable alias drift and unstable normalization outcomes.

2. Add bookmaker-specific one-off translation layers.
- Rejected: increases maintenance cost and conflicts with centralized normalization policy.

## Follow-ups
1. Continue adding aliases as discovery/onboarding exposes new naming variants.
2. Re-run mismatch evidence checks during PR3+ changes.
3. Keep market-hygiene changes out of normalization PR scope (handled in PR4).
