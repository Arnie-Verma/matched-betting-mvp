# PR-C1 Pre-Unibet Checklist Decision

## Decision Context

This decision closes the "Final Pre-Unibet Go/No-Go Checklist" items for Entain + Punterstech hardening evidence only.

This is **not** an Unibet activation decision. Unibet remains frozen.

## Checklist Decision Table

| Checklist Item (`SCRAPER_HARDENING_PLAN.md`) | Status | Evidence |
|---|:---:|---|
| Entain and Punterstech pass identical DoD tests. | PASS | `apps/worker/tests/test_entain_scraper.py`, `apps/worker/tests/test_punterstech_scraper.py`, `docs/evidence/phase-a-hardening/2026-02-11/pr21_pre_unibet_test_matrix.json` |
| Validation output is stable and trustworthy on priority competitions. | PASS | `docs/evidence/phase-a-hardening/2026-02-11/pr21_val_run1_reason_breakdown_after.json`, `docs/evidence/phase-a-hardening/2026-02-11/pr21_val_run2_reason_breakdown_after.json`, `docs/evidence/phase-a-hardening/2026-02-11/pr21_pre_unibet_test_matrix.json` |
| Lifecycle and activation gates are code-enforced. | PASS | `docs/evidence/phase-a-hardening/2026-02-11/pr19_activation_gate_contract.md`, `docs/evidence/phase-a-hardening/2026-02-11/pr20_evidence_registry_contract.md` |
| Local canary report passes (30-60 min repeated cycles). | PASS | `docs/evidence/phase-a-hardening/2026-02-11/pr21_pre_unibet_canary.json`, `docs/evidence/phase-a-hardening/2026-02-11/pr21_pre_unibet_canary.md` |
| Breaker behavior and recovery are verified. | PASS | `docs/evidence/phase-a-hardening/2026-02-11/pr21_pre_unibet_breaker_recovery.md`, `apps/worker/tests/test_scrape_scheduler.py` |
| Evidence artifact saved and reviewed. | PASS | `docs/evidence/phase-a-hardening/2026-02-11/pr21_pre_unibet_checklist_contract.md`, `docs/evidence/phase-a-hardening/2026-02-11/pr21_pre_unibet_test_matrix.json`, `docs/evidence/phase-a-hardening/2026-02-11/pr21_pre_unibet_decision.md` |

## GO/NO-GO Outcome

- **GO** for Pre-Unibet checklist closeout evidence.
- **NO-GO** for any Unibet onboarding/activation action in this slice (out of scope).

## Freeze Verification (Runtime + DB)

- `mb_api`: `BOOKMAKER_FREEZE_UNIBET=true`
- `mb_worker`: `BOOKMAKER_FREEZE_UNIBET=true`
- DB (`bookmakers`): `unibet.is_active=false`
