# Scraper Hardening Plan (Entain + Punterstech First)

## Purpose
Harden existing Entain and Punterstech scrapers to a repeatable, low-risk standard before onboarding Unibet and other bookmakers.

This is a pre-Unibet stabilization plan.

## Why This Comes First
If Entain/Punterstech are not hardened first, adding Unibet will compound:
- false validation failures
- inconsistent competition mapping
- unclear go/no-go decisions
- harder debugging when a bookmaker breaks

Hardening first gives you a reusable onboarding pattern for 100+ bookmakers.

## Alignment to `BOOKMAKER_OPERATING_SYSTEM.md`
This plan directly implements:
- `Non-Negotiable Guardrails`
- `Lifecycle (Required)`
- `Quality Gates (Go/No-Go)`
- `Activation Gates (Operational)`
- `Outstanding Build Items For Reliable Scale`

## Scope
- In scope: Entain (`ladbrokes`, `neds`) and Punterstech (`mintbet`, `tradiebet`, same platform peers)
- Out of scope: adding new platforms/bookmakers until hardening exit criteria pass

## Workstreams

## 1) Validation Semantics Hardening (P0)
What it is:
- Make validation results reflect real scraper quality, not naming/seasonality noise.

Why it matters:
- Prevents false FAIL/WARN that block promotion decisions.

Changes:
- Add `SKIP`/`N_A` handling for no-eligible-fixture windows.
- Calibrate event-count thresholds per competition/season.
- Ensure event coverage is calculated only against valid reference fixture sets.

Primary files:
- `apps/worker/src/validation/config.py`
- `apps/worker/src/validation/pipeline.py`
- `apps/worker/src/validation/score_calculator.py`

Exit criteria:
- EPL/NBA/NHL/boxing/NBL validation status is stable and explainable across repeated runs.
- No hard FAIL caused solely by empty windows or threshold mismatch.

## 2) Competition + Event Normalization Hardening (P0)
What it is:
- Standardize how competition and event names map across platforms.

Why it matters:
- Cross-bookmaker matching is the foundation of odds comparison and validation.

Changes:
- Expand canonical competition aliases and team/event normalization coverage.
- Add explicit test cases for Entain vs Punterstech naming variations.

Primary files:
- `apps/api/src/api/services/normalization_service.py`
- `apps/worker/tests/test_validation.py` (add mapping cases)

Exit criteria:
- Same real-world fixture maps to same canonical key across Entain and Punterstech.
- Competition filters (e.g., EPL) consistently return expected fixtures in both platforms.

## 3) Market Hygiene + Selection Key Hardening (P0)
What it is:
- Enforce fixture-only match markets and stable `selection_key` (`home/away/draw`).

Why it matters:
- Outrights/partials/non-match markets poison matcher quality and validation.

Changes:
- Strictly filter out futures/outrights/partial-game markets from matcher pipeline.
- Add assertions for expected market shape by sport (2-way vs 3-way).

Primary files:
- `apps/worker/src/scrapers/entain_scraper.py`
- `apps/worker/src/scrapers/punterstech_scraper.py`
- `apps/worker/src/jobs/save_odds.py`

Exit criteria:
- Priority competitions only store valid match winner markets for matcher use.
- Selection keys are deterministic and consistent across both platforms.

## 4) Test Parity Hardening (P0)
What it is:
- Equal definition-of-done test coverage for Entain and Punterstech.

Why it matters:
- Same platform quality bar means predictable onboarding quality.

Changes:
- Add `apps/worker/tests/test_entain_scraper.py` with parity coverage:
  - parsing
  - competition filtering
  - market filtering
  - selection key mapping
  - error handling
- Keep existing Punterstech suite as baseline.

Primary files:
- `apps/worker/tests/test_entain_scraper.py` (new)
- `apps/worker/tests/test_punterstech_scraper.py`

Exit criteria:
- Both scraper families pass equivalent contract tests in CI/local.

## 5) Lifecycle + Activation Gate Enforcement in Code (P1)
What it is:
- Turn lifecycle/gate rules from documentation into enforced runtime checks.

Why it matters:
- Prevents accidental activation of broken bookmakers.

Changes:
- Add lifecycle state storage and transition checks.
- Block `active` promotion unless gates pass:
  - structural/coverage thresholds
  - anomaly limits
  - local canary evidence
  - breaker stability

Primary files:
- `apps/api` models + migration
- `apps/worker/src/jobs/scrape_service.py`
- promotion/admin scripts

Exit criteria:
- Bookmaker cannot be promoted by config flip alone.
- Promotion requires machine-verifiable gate evidence.

## 6) Local Canary + Evidence Artifact (P1)
What it is:
- Automated local canary loop (30-60 min) with report output.

Why it matters:
- You run locally (Docker), so this is your production-like confidence step.

Changes:
- Add script to run repeated refresh/validate cycles and emit a Go/No-Go report.
- Include per-bookmaker metrics:
  - success rate
  - latency p50/p95
  - breaker opens
  - validation trend
  - event/odds drift

Primary files:
- `apps/worker/src/scripts/*` (new canary script)
- report artifact in `docs/` or root evidence folder

Exit criteria:
- Entain + Punterstech pass local canary with no unresolved critical failures.

## 7) Runtime Policy Config (P1)
What it is:
- Per-bookmaker runtime controls in config (timeouts/retries/concurrency/proxy class).

Why it matters:
- Local resource constraints and production scale require different execution profiles.

Changes:
- Move runtime behavior to config-driven policy.
- Keep local conservative defaults (e.g., `SCRAPER_BATCH_SIZE=1`) without changing architecture.

Primary files:
- `apps/worker/src/jobs/scrape_service.py`
- bookmaker config (`seed_all_bookmakers.py` + DB config)

Exit criteria:
- Same codebase runs local/staging/prod profiles via env+config only.

## Delivery Sequence
1. Complete Workstreams 1-4 (P0) before touching Unibet rollout.
2. Complete Workstreams 5-7 (P1) immediately after.
3. Re-run Entain/Punterstech proof canary.
4. Start Unibet onboarding only after all exit criteria pass.

## Hard Stop Rule
Pause new bookmaker onboarding if either condition is true:
- Active scraper reliability drops below agreed threshold.
- Validation outcomes are unstable/non-deterministic across repeated runs.

## Final Pre-Unibet Go/No-Go Checklist
- [ ] Entain and Punterstech pass identical DoD tests.
- [ ] Validation output is stable and trustworthy on priority competitions.
- [ ] Lifecycle and activation gates are code-enforced.
- [ ] Local canary report passes (30-60 min repeated cycles).
- [ ] Breaker behavior and recovery are verified.
- [ ] Evidence artifact saved and reviewed.

---

If all boxes above are checked, proceed to Unibet using the same operating model.
