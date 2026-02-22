# PR-C2 Rollout Control Plane Baseline Contract

## Objective

Add deterministic rollout control-plane enforcement so worker runnable selection is derived from:
- lifecycle eligibility
- freeze policy
- rollout policy
- kill switches

No canary threshold or gate-policy semantics were changed.

## Implemented Control Surface

- Persistence:
  - `platform_rollout_policies`
  - `bookmaker_rollout_policies`
- Service:
  - `RolloutControlService` with deterministic selection reasons.
- Worker/runtime selection:
  - `ScrapeService.get_active_bookmakers_from_db(...)` now enforces rollout controls.
  - `refresh_worker` passes request context (`sport`, `competition`, `bookmakers`) into selection.
  - `trigger_scrape(...)` now consumes the resolved bookmaker subset to prevent bypass.
- Admin/internal endpoints:
  - `GET/PUT /admin/rollout/bookmakers/{bookmaker_code}/policy`
  - `GET/PUT /admin/rollout/bookmakers/{bookmaker_code}/kill-switch`
  - `GET/PUT /admin/rollout/platforms/{platform_code}/policy`
  - `GET/PUT /admin/rollout/platforms/{platform_code}/kill-switch`
  - `GET /admin/rollout/status`

## Reproducible Commands

```bash
python -m py_compile apps/api/src/api/models/odds.py apps/api/src/api/services/rollout_control_service.py apps/api/src/api/routers/rollout_control.py apps/api/src/api/main.py apps/worker/src/jobs/scrape_service.py apps/worker/src/jobs/refresh_worker.py apps/api/tests/test_rollout_control.py apps/worker/tests/test_scrape_scheduler.py
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_rollout_control.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/worker/tests/test_scrape_scheduler.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_bookmaker_lifecycle.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
```

```bash
docker exec mb_api alembic upgrade head
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "select code, is_active from bookmakers where code='unibet';"
```

## Acceptance Mapping

1. Cohort-limited canary selection works as configured.
   - Covered by `test_rollout_selection_cohort_and_kill_switch_controls`
   - Scenario evidence: `pr22_rollout_control_scenarios.json` (`platform_canary_cohort_limited`)
2. Bookmaker kill switch has immediate effect.
   - Covered by `test_rollout_selection_cohort_and_kill_switch_controls`
   - Scenario evidence: `pr22_rollout_control_scenarios.json` (`bookmaker_kill_switch_immediate`)
3. Platform kill switch has immediate effect.
   - Covered by `test_rollout_selection_cohort_and_kill_switch_controls`
   - Scenario evidence: `pr22_rollout_control_scenarios.json` (`platform_kill_switch_immediate`)
4. Rollback path is deterministic.
   - Covered by `test_rollout_selection_cohort_and_kill_switch_controls`
   - Scenario evidence: `pr22_rollout_control_scenarios.json` (`deterministic_rollback_after_disable`)
5. Access controls enforce admin/internal policy.
   - Covered by `test_rollout_endpoints_enforce_access_and_support_internal_token`
6. Freeze baseline remains enforced.
   - `mb_api`: `BOOKMAKER_FREEZE_UNIBET=true`
   - `mb_worker`: `BOOKMAKER_FREEZE_UNIBET=true`
   - DB: `unibet | f`
