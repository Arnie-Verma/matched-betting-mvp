# PR-R2 Bounded Concurrency Contract

Date: 2026-02-21  
Slice: PR-R2 (Bounded Concurrency + Scheduler Discipline)

## Scope
- Replaced unbounded full-bookmaker fan-out in worker scrape orchestration with bounded scheduling.
- Enforced both global and per-platform bookmaker concurrency caps.
- Removed `ACTIVE_BOOKMAKERS` env as worker control-plane source; active set now resolves from DB runtime state plus freeze policy.
- Preserved failure isolation (one bookmaker failure is non-fatal to others).
- Added scheduler metrics in scrape output (`scheduler` block).

## Before vs After Behavior
- Before:
  - `scrape_all_active_bookmakers` created one task per active bookmaker and awaited `asyncio.gather(*tasks, return_exceptions=True)`.
  - Effective in-flight bookmaker count could equal total active bookmaker count.
- After:
  - Bounded worker-pool (`global_cap`) consumes bookmaker queue.
  - Per-platform semaphores enforce platform-specific caps.
  - Output includes observed max in-flight global/per-platform for auditability.

## Cap Settings Used in Synthetic Evidence
- `SCRAPE_GLOBAL_CONCURRENCY_CAP=3`
- `SCRAPE_PLATFORM_CONCURRENCY_DEFAULT_CAP=2`
- `SCRAPE_PLATFORM_CONCURRENCY_CAPS_JSON={"entain":1,"punterstech":2}`

## Synthetic Runtime/Fault Comparison
- See: `docs/evidence/phase-a-hardening/2026-02-11/pr10_bounded_concurrency_metrics.json`
- Scenario:
  - 6 bookmakers synthetic workload (3 `entain`, 3 `punterstech`)
  - 1 synthetic scraper failure (`mintbet`)
- Result summary:
  - Before (unbounded): max in-flight global `6`, per-platform `entain=3`, `punterstech=3`
  - After (bounded): max in-flight global `3`, per-platform `entain=1`, `punterstech=2`
  - Failure isolation remained non-fatal (5 successes, 1 failure)

## Commands Run (Reproducible)
```powershell
pytest apps/worker/tests/test_scrape_scheduler.py -q
pytest apps/worker/tests/test_validation.py -q
pytest apps/worker/tests/test_entain_scraper.py -q
pytest apps/worker/tests/test_punterstech_scraper.py -q
$env:PYTHONPATH='apps/api/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; python apps/worker/src/scripts/generate_pr10_bounded_concurrency_metrics.py --output docs/evidence/phase-a-hardening/2026-02-11/pr10_bounded_concurrency_metrics.json
```

## Command Output Summary
- `apps/worker/tests/test_scrape_scheduler.py`: `4 passed, 1 warning`
- `apps/worker/tests/test_validation.py`: `62 passed`
- `apps/worker/tests/test_entain_scraper.py`: `25 passed`
- `apps/worker/tests/test_punterstech_scraper.py`: `47 passed`
- `apps/api/tests/test_bookmaker_freeze.py`: `6 passed, 1 warning`
- `apps/api/tests/test_unibet_freeze_integration.py`: `1 passed, 3 warnings`

## Determinism/Isolation Assertions
- Global cap and per-platform caps are enforced and tested.
- Active bookmaker control path is runtime DB + freeze policy.
- Scraper exceptions are contained per bookmaker and converted to non-fatal result rows.

## Freeze Verification (Runtime)
- `docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'` -> `BOOKMAKER_FREEZE_UNIBET=true`
- `docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'` -> `BOOKMAKER_FREEZE_UNIBET=true`
- `docker exec mb_db psql -U postgres -d mb_dev -c "select code,is_active from bookmakers where code='unibet';"` -> `unibet | f`
- `SubscriptionService.get_allowed_bookmakers` runtime check (`free/premium/diamond`) -> `{'free': False, 'premium': False, 'diamond': False}` for `unibet in allowed`
- `ScrapeService.get_active_bookmakers_from_db()` runtime check -> `unibet` not present
