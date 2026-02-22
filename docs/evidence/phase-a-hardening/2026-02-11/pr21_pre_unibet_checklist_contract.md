# PR-C1 Pre-Unibet Checklist Closeout Contract

## Scope

Close the remaining "Final Pre-Unibet Go/No-Go Checklist" items with reproducible evidence only.

Constraints kept:
- No gate threshold/policy changes.
- `BOOKMAKER_FREEZE_UNIBET=true` remains enforced.
- `unibet.is_active=false` remains enforced.

## Evidence Summary

- DoD parity proof:
  - `apps/worker/tests/test_entain_scraper.py` -> 27 passed
  - `apps/worker/tests/test_punterstech_scraper.py` -> 47 passed
- Validation stability proof:
  - `pr21_val_run1_reason_breakdown_after.json`
  - `pr21_val_run2_reason_breakdown_after.json`
  - No status/scope drift between repeated runs.
- Fresh local canary pass:
  - `pr21_pre_unibet_canary.json` / `pr21_pre_unibet_canary.md`
  - Duration `1812.93s`, cycles `12`, gate `PASS=true`.
- Breaker behavior + deterministic recovery proof:
  - Controlled breaker simulation timeline in `pr21_pre_unibet_breaker_recovery.md`.
  - Isolation proof from scheduler contract test + live canary partial-failure cycles.
- Decision table:
  - `pr21_pre_unibet_decision.md`

## Reproducible Commands (Executed)

```bash
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/worker/tests/test_entain_scraper.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/worker/tests/test_punterstech_scraper.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/worker/tests/test_scrape_scheduler.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/worker/tests/test_scrape_scheduler.py -q -k "failure_isolation"
```

```bash
docker exec mb_api alembic upgrade head
docker exec mb_worker sh -lc 'cd apps/worker/src && PYTHONPATH=../../api/src:. python -m scripts.generate_phase_a_validation_evidence --suffix pr21_val_run1 --baseline-file pr7_reason_breakdown_after.json'
docker exec mb_worker sh -lc 'cd apps/worker/src && PYTHONPATH=../../api/src:. python -m scripts.generate_phase_a_validation_evidence --suffix pr21_val_run2 --baseline-file pr7_reason_breakdown_after.json'
docker exec mb_worker sh -lc 'cd apps/worker/src && PYTHONPATH=../../api/src:. python -m scripts.run_phase_a_canary --output-prefix pr21_pre_unibet_canary --min-duration-seconds 1800 --min-cycles 10 --max-cycles 20 --sleep-seconds 60 --min-scrape-success-rate 0.75 --max-open-breaker-cycles 0 --max-scrape-p95-seconds 360'
Copy-Item -Path apps/worker/src/docs/evidence/phase-a-hardening/2026-02-11/pr21_* -Destination docs/evidence/phase-a-hardening/2026-02-11/ -Force
Copy-Item -Path apps/worker/src/docs/evidence/phase-a-hardening/2026-02-11/priority_competition_summary_table_live_pr21_val_run*.json -Destination docs/evidence/phase-a-hardening/2026-02-11/ -Force
Copy-Item -Path apps/worker/src/docs/evidence/phase-a-hardening/2026-02-11/validation_live_*_pr21_val_run*.json -Destination docs/evidence/phase-a-hardening/2026-02-11/ -Force
```

```bash
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "select code, is_active from bookmakers where code='unibet';"
```

## Key Outcomes

- Canary contract thresholds unchanged and satisfied:
  - `min_cycles>=10` -> observed `12`
  - `min_duration_seconds>=1800` -> observed `1812.93`
  - `in_scope_fail_cycle_count==0` -> observed `0`
  - `min_scrape_success_rate>=0.75` -> observed `0.9802`
  - `max_open_breaker_cycle_count<=0` -> observed `0`
  - `max_scrape_p95_seconds<=360` -> observed `242.1597`
- Freeze baseline verified:
  - `mb_api`: `true`
  - `mb_worker`: `true`
  - DB: `unibet | f`
