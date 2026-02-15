# ADR-0007: Phase A Unibet Freeze Enforcement

- Status: Accepted
- Date: 2026-02-11
- Owners: @team

## Context
Phase A hardening requires a strict freeze on new bookmaker onboarding (including Unibet)
until P0 hardening gates and canary evidence pass. Before this ADR, Unibet could still be:
- enabled via `is_active=true` seed/config
- scraped if marked active in DB
- exposed in Premium/Diamond plan bookmaker allow-lists

That allowed accidental re-activation during the freeze window.

## Decision
Implement explicit code-enforced freeze controls for Unibet:
1. Add runtime freeze flag `BOOKMAKER_FREEZE_UNIBET` (default `true`).
2. Add central policy module `api.core.bookmaker_freeze`.
3. Enforce freeze in worker active bookmaker selection:
   - `ScrapeService.get_active_bookmakers_from_db` skips frozen bookmakers.
4. Enforce freeze in plan exposure:
   - `SubscriptionService.get_allowed_bookmakers` filters frozen bookmaker codes.
5. Set Unibet seed defaults to disabled:
   - `is_active=false` in bookmaker seed scripts.

## Consequences
Benefits:
- Freeze is enforced even if Unibet is accidentally set active in DB/config.
- UI plan exposure and background scraping stay aligned during freeze.
- Re-enable requires explicit, auditable action (set flag false and pass gate decision).

Tradeoffs:
- Temporary divergence from historical docs that marked Unibet "implemented/active".
- Requires explicit coordination at GO time to disable freeze flag.

## Alternatives Considered
1. Seed-only disable (`is_active=false`) without runtime gate.
- Rejected: DB/manual toggles could still reactivate Unibet.

2. Remove Unibet code paths entirely.
- Rejected: conflicts with requirement to keep code and defer activation only.

## Follow-ups
1. Keep `BOOKMAKER_FREEZE_UNIBET=true` through Phase A completion.
2. Only set `BOOKMAKER_FREEZE_UNIBET=false` after explicit GO decision with evidence.
3. Extend the same policy pattern to other freeze windows if needed.
