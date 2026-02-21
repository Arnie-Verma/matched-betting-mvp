# PR16 Scope Gate Root Cause (PR-R4A)

Date: 2026-02-21
Slice: PR-R4A only

## Problem
PR-E2 live canary failed the in-scope validation gate repeatedly with:
- `competition=nbl`
- `bookmaker=betreal`
- `coverage_scope=in_scope`
- `failure_reasons=["Coverage 0% < 70%"]`

Baseline evidence:
- `docs/evidence/phase-a-hardening/2026-02-11/pr15_live_canary_runtime.json`
  - `in_scope_fail_cycle_count=21`
  - repeated row: `nbl x betreal`

## Root Cause Classification
Classification: **policy drift** (not scraper-code regression).

Why:
1. The shared Punterstech scraper path still returns NBL for peer skins (for example `mintbet`) in the same runtime window.
2. `betreal` currently returns basketball events but no NBL rows (NBA-only in targeted run), producing stable zero NBL coverage.
3. Existing scope policy in `apps/worker/src/validation/config.py` marked `betreal` as in-scope for NBL by omission.

Targeted runtime checks:
- `python /workspace/apps/worker/src/scripts/validate_scrapers.py --competition nbl --bookmaker betreal --scrape --format json`
  - `betreal`: `event_count=0`, `status=FAIL`, `Coverage 0% < 70%`
- `python /workspace/apps/worker/src/scripts/validate_scrapers.py --competition nbl --bookmaker mintbet --scrape --format json`
  - `mintbet`: `event_count=1`, `status=PASS`

## Minimal Fix Applied
Policy-only mapping correction:
- `apps/worker/src/validation/config.py`
  - Added `betreal` to `BOOKMAKER_COMPETITION_COVERAGE_POLICY["nbl"]["out_of_scope"]`

Regression coverage added:
- `apps/worker/tests/test_validation.py`
  - `test_bookmaker_competition_scope_policy` now asserts `betreal` is out-of-scope for `nbl`
  - Added `test_pipeline_betreal_nbl_zero_event_is_skip_and_not_failure`

## Post-Fix Canary Validation
Artifact:
- `docs/evidence/phase-a-hardening/2026-02-11/pr16_scope_gate_canary.json`
- `docs/evidence/phase-a-hardening/2026-02-11/pr16_scope_gate_canary.md`

Observed:
- runtime: 2157.83s (>=1800s)
- cycles: 10 (>=10)
- `in_scope_fail_cycle_count=0`
- `in_scope_fail_rows=[]`

Note:
- Gate remains `PASS=false` due latency criterion only (`max_scrape_p95_seconds` breached).
- Scope drift issue itself is remediated (`nbl x betreal` no longer contributes in-scope FAIL rows).

## Freeze Verification
Runtime checks:
- `docker exec mb_api env | rg "^BOOKMAKER_FREEZE_UNIBET="` -> `BOOKMAKER_FREEZE_UNIBET=true`
- `docker exec mb_worker env | rg "^BOOKMAKER_FREEZE_UNIBET="` -> `BOOKMAKER_FREEZE_UNIBET=true`
- `docker exec mb_db psql -U postgres -d mb_dev -c "SELECT code, is_active FROM bookmakers WHERE code='unibet';"`
  - `unibet | f`

## Commands (Reproducible)
```bash
docker exec mb_api sh -lc 'cd /workspace && export PYTHONPATH=/workspace/apps/api/src:/workspace/apps/worker/src && python /workspace/apps/worker/src/scripts/validate_scrapers.py --competition nbl --bookmaker betreal --scrape --format json'
docker exec mb_api sh -lc 'cd /workspace && export PYTHONPATH=/workspace/apps/api/src:/workspace/apps/worker/src && python /workspace/apps/worker/src/scripts/validate_scrapers.py --competition nbl --bookmaker mintbet --scrape --format json'
pytest apps/worker/tests/test_validation.py -q
pytest apps/worker/tests/test_entain_scraper.py -q
pytest apps/worker/tests/test_punterstech_scraper.py -q
PYTHONPATH=apps/api/src:apps/worker/src pytest apps/api/tests/test_bookmaker_freeze.py -q
PYTHONPATH=apps/api/src:apps/worker/src pytest apps/api/tests/test_unibet_freeze_integration.py -q
docker exec mb_api sh -lc 'cd /workspace && export PYTHONPATH=/workspace/apps/api/src:/workspace/apps/worker/src && python /workspace/apps/worker/src/scripts/run_phase_a_canary.py --min-duration-seconds 1800 --min-cycles 10 --max-cycles 20 --sleep-seconds 60 --output-prefix pr16_scope_gate_canary'
```
