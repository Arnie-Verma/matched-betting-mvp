# PR9 Canary Gate Contract Hardening

Date executed: 2026-02-21  
Scope: PR-R1 canary gate reliability threshold contract

## Gate defaults implemented

- `min_cycles = 10`
- `min_duration_seconds = 1800`
- `requires_in_scope_fail_zero = true`
- `min_scrape_success_rate = 0.75`
- `max_open_breaker_cycle_count = 0`
- `max_scrape_p95_seconds = 360`

## Commands and outputs

### 1) Test run

Commands:

```powershell
pytest apps/worker/tests/test_phase_a_canary_gate.py -q
pytest apps/worker/tests/test_validation.py -q
pytest apps/worker/tests/test_entain_scraper.py -q
pytest apps/worker/tests/test_punterstech_scraper.py -q
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
```

Outputs (summary):

- `test_phase_a_canary_gate.py`: `8 passed`
- `test_validation.py`: `62 passed`
- `test_entain_scraper.py`: `25 passed`
- `test_punterstech_scraper.py`: `47 passed`
- `test_bookmaker_freeze.py`: `6 passed`

### 2) Gate evaluation against existing canary artifacts under new logic

Command:

```powershell
$env:PYTHONPATH='apps/worker/src;apps/api/src'
@'
import json
from datetime import datetime, timezone
from pathlib import Path
from scripts.run_phase_a_canary import build_gate_thresholds, evaluate_gate

base = Path("docs/evidence/phase-a-hardening/2026-02-11")
thresholds = build_gate_thresholds(
    min_cycles=10,
    min_duration_seconds=1800,
    requires_in_scope_fail_zero=True,
    min_scrape_success_rate=0.75,
    max_open_breaker_cycle_count=0,
    max_scrape_p95_seconds=360,
)

def load(name):
    return json.loads((base / name).read_text(encoding="utf-8"))

result = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "thresholds": thresholds,
    "real_canary_evaluations": {
        "phase_a_canary_pr6_1": {
            "file": "phase_a_canary_pr6_1.json",
            "gate": evaluate_gate(load("phase_a_canary_pr6_1.json"), thresholds),
        },
        "phase_a_canary_pr7": {
            "file": "phase_a_canary_pr7.json",
            "gate": evaluate_gate(load("phase_a_canary_pr7.json"), thresholds),
        },
    },
    "synthetic_gate_evaluations": {},
}

def synthetic_summary(success_rate, open_cycles, scrape_p95, cycles=10, duration=1800, in_scope_fail_cycles=0):
    return {
        "cycles_completed": cycles,
        "duration_seconds": float(duration),
        "latency_metrics": {"scrape_duration_p95_seconds": float(scrape_p95)},
        "breaker_metrics": {"open_breaker_cycle_count": int(open_cycles)},
        "validation_gate_metrics": {"in_scope_fail_cycle_count": int(in_scope_fail_cycles)},
        "reliability_metrics": {"scrape_success_rate": float(success_rate)},
        "cycles": [],
    }

synthetic_cases = {
    "pass_case": synthetic_summary(0.80, 0, 300),
    "fail_success_rate_case": synthetic_summary(0.74, 0, 300),
    "fail_breaker_case": synthetic_summary(0.80, 1, 300),
    "fail_latency_case": synthetic_summary(0.80, 0, 361),
    "fail_min_cycles_case": synthetic_summary(0.80, 0, 300, cycles=9),
    "fail_min_duration_case": synthetic_summary(0.80, 0, 300, duration=1799),
    "fail_in_scope_fail_case": synthetic_summary(0.80, 0, 300, in_scope_fail_cycles=1),
}

for name, payload in synthetic_cases.items():
    result["synthetic_gate_evaluations"][name] = evaluate_gate(payload, thresholds)
(base / "pr9_canary_gate_synthetic_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print("PR6_1 pass=", result["real_canary_evaluations"]["phase_a_canary_pr6_1"]["gate"]["pass"])
print("PR7 pass=", result["real_canary_evaluations"]["phase_a_canary_pr7"]["gate"]["pass"])
for name, gate in result["synthetic_gate_evaluations"].items():
    print(name, "pass=", gate["pass"])
'@ | python -
```

Output:

```text
PR6_1 pass= False
PR7 pass= False
pass_case pass= True
fail_success_rate_case pass= False
fail_breaker_case pass= False
fail_latency_case pass= False
fail_min_cycles_case pass= False
fail_min_duration_case pass= False
fail_in_scope_fail_case pass= False
```

### 3) Synthetic branch targets

Synthetic branch evaluations are recorded in:
- `pr9_canary_gate_synthetic_results.json`

Expected outcomes (verified):
- pass case (`success=0.80`, `open=0`, `p95=300`) -> PASS
- fail-success-rate (`success=0.74`) -> FAIL
- fail-breaker (`open cycles=1`) -> FAIL
- fail-latency (`scrape p95=361`) -> FAIL
- fail-min-cycles (`cycles=9`) -> FAIL
- fail-min-duration (`duration=1799`) -> FAIL
- fail-in-scope (`in_scope_fail_cycle_count=1`) -> FAIL
