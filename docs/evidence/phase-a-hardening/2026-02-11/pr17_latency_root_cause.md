# PR-R4B Latency Root Cause and Remediation

## Classification

- Root cause type: scraper/runtime regression with deterministic latency tail.
- Primary contributors:
  - Entain listener lifecycle bug in `EntainScraper.scrape_sport`: response listeners were attached per competition and not detached, causing repeated handler work across competition navigation loops.
  - Platform-cap default gap for Punterstech: runtime had no env overrides, so the scheduler fallback of `1` serialized a large Punterstech bookmaker set.

## Evidence

- Baseline canary (`pr16_scope_gate_canary.json`):
  - `scrape_duration_p95_seconds = 388.5932` (NO-GO, threshold `<= 360`)
  - Slowest cycles were all soccer:
    - cycle 1: `400.8325s`
    - cycle 9: `373.6340s`
    - cycle 5: `303.0016s`
  - Sport attribution:
    - soccer avg `359.1560s` (3 cycles)
    - basketball avg `133.9497s`
    - boxing avg `45.5507s`
    - ice_hockey avg `21.1767s`

- Post-fix canary (`pr17_latency_canary.json`):
  - `scrape_duration_p95_seconds = 245.1969` (GO)
  - `in_scope_fail_cycle_count = 0` (unchanged, still compliant)
  - Slowest cycles remain soccer but reduced:
    - cycle 1: `247.9957s`
    - cycle 5: `242.9070s`
    - cycle 9: `195.4642s`
  - Sport attribution:
    - soccer avg `228.7889s` (3 cycles)
    - basketball avg `128.9417s`
    - boxing avg `32.6546s`
    - ice_hockey avg `16.6543s`

- Live attribution probe (`pr17_latency_live_probe_soccer.json`):
  - Full soccer scrape duration: `198.9816s`
  - Top bookmaker contributors:
    - `ladbrokes` (`entain`): `108.5639s`
    - `betfair` (`betfair`): `93.5972s`
    - `neds` (`entain`): `90.2967s`

## Deterministic vs Burst Assessment

- Deterministic tail, not burst noise:
  - In PR16, every soccer cycle sat in the high-latency tail (303-401s), while non-soccer cycles were consistently much lower.
  - In PR17, soccer is still the slowest sport, but the tail is consistently reduced and under the gate threshold.

## Remediation Applied (Single Slice)

- `apps/worker/src/scrapers/entain_scraper.py`
  - Added `_detach_response_listener(...)`.
  - Attached per-competition response listener and detached it in `finally`.

- `apps/worker/src/jobs/scrape_service.py`
  - Added reusable default platform cap override:
    - `punterstech: 2`
  - Kept bounded default fallback at `1` for unspecified platforms.

## Validation and Regression Coverage

- `apps/worker/tests/test_entain_scraper.py`
  - Added listener-detach lifecycle tests (`remove_listener` and `off` fallback).

- `apps/worker/tests/test_scrape_scheduler.py`
  - Added default cap test asserting:
    - `platform_default_concurrency_cap == 1`
    - default override `platform_concurrency_caps['punterstech'] == 2`

## Reproducible Commands

```bash
docker exec mb_api sh -lc 'cd /workspace && PYTHONPATH=/workspace/apps/api/src:/workspace/apps/worker/src python /workspace/apps/worker/src/scripts/run_phase_a_canary.py --min-duration-seconds 1800 --min-cycles 10 --max-cycles 20 --sleep-seconds 60 --output-prefix pr17_latency_canary'
```

```bash
docker exec mb_api sh -lc 'cd /workspace && PYTHONPATH=/workspace/apps/api/src:/workspace/apps/worker/src python - <<'"'"'\"'"'"'\"'"'"'PY'"'"'\"'"'"'\"'"'"'
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.run_phase_a_canary import trigger_scrape


async def main():
    started = datetime.now(timezone.utc).isoformat()
    res = await trigger_scrape(sport="soccer", limit=None)
    rows = sorted(
        (res.get("results", []) or []),
        key=lambda x: (x.get("duration_seconds") or 0),
        reverse=True,
    )
    out = {
        "captured_at": started,
        "sport": "soccer",
        "total_duration_seconds": res.get("duration_seconds"),
        "total_bookmakers": res.get("total_bookmakers"),
        "bookmakers_scraped": res.get("bookmakers_scraped"),
        "results": rows,
    }
    Path(
        "/workspace/docs/evidence/phase-a-hardening/2026-02-11/pr17_latency_live_probe_soccer.json"
    ).write_text(json.dumps(out, indent=2), encoding="utf-8")


asyncio.run(main())
PY'
```
