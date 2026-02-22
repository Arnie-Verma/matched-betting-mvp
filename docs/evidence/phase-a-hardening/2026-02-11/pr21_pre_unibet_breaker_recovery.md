# PR-C1 Breaker Behavior + Recovery Evidence

## Objective

Demonstrate:
1. Controlled breaker failure -> open -> recovery workflow with timestamps.
2. Isolation behavior where one bookmaker failure does not block other bookmakers.

## Controlled Breaker Simulation

Command executed:

```bash
docker exec mb_worker sh -lc "cd /workspace && BOOKMAKER_BREAKER_THRESHOLD=2 BOOKMAKER_BREAKER_COOLDOWN_SECONDS=2 PYTHONPATH=apps/api/src:apps/worker/src python - <<'PY'
import json
import time
from datetime import datetime, timezone
from jobs.scrape_service import ScrapeService

svc = ScrapeService()
book='pr21_breaker_demo'
key=f'breaker:{book}'
svc.redis_client.delete(key)
steps=[]

def snap(action, note=''):
    steps.append({
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'action': action,
        'state': svc._get_breaker_state(book),
        'allowed_to_scrape': bool(svc._check_breaker(book)),
        'note': note,
    })

snap('initial_state')
svc._record_failure(book)
snap('after_failure_1', note='below threshold; expected closed with failures=1')
svc._record_failure(book)
snap('after_failure_2', note='threshold reached; expected open')
steps.append({
    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
    'action': 'immediate_open_check',
    'state': svc._get_breaker_state(book),
    'allowed_to_scrape': bool(svc._check_breaker(book)),
    'note': 'expected False while cooldown active',
})
time.sleep(svc.breaker_cooldown + 0.3)
steps.append({
    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
    'action': 'post_cooldown_check',
    'state': svc._get_breaker_state(book),
    'allowed_to_scrape': bool(svc._check_breaker(book)),
    'note': 'expected True and state transitions to half-open',
})
snap('after_half_open_observed')
svc._record_success(book)
snap('after_success_recovery', note='expected closed with failures=0')
print(json.dumps({'steps': steps}, indent=2))
PY"
```

Observed timeline:

| Timestamp (UTC) | Action | State | Failures | Allowed | Note |
|---|---|---|---:|:---:|---|
| 2026-02-22T06:28:22.454463+00:00 | initial_state | closed | 0 | true | baseline |
| 2026-02-22T06:28:22.457336+00:00 | after_failure_1 | closed | 1 | true | below threshold |
| 2026-02-22T06:28:22.464669+00:00 | after_failure_2 | open | 2 | false | threshold reached |
| 2026-02-22T06:28:22.465874+00:00 | immediate_open_check | open | 2 | false | cooldown active |
| 2026-02-22T06:28:24.768064+00:00 | post_cooldown_check | open | 2 | true | cooldown elapsed |
| 2026-02-22T06:28:24.775036+00:00 | after_half_open_observed | half-open | 2 | true | retry state |
| 2026-02-22T06:28:24.781606+00:00 | after_success_recovery | closed | 0 | true | recovered |

Result: deterministic recovery path verified.

## Isolation Proof

### Contract test proof

Command:

```bash
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/worker/tests/test_scrape_scheduler.py -q -k "failure_isolation"
```

Result: `1 passed` (`test_scheduler_failure_isolation`).

### Live canary proof (`pr21_pre_unibet_canary.json`)

Cycles with one bookmaker failure (`betfair`) while others still completed:

| Cycle | Started At (UTC) | Sport | Successful/Total | Failure | Open Breakers |
|---:|---|---|---:|---|---:|
| 3 | 2026-02-22T06:02:28.609855+00:00 | ice_hockey | 20/21 | betfair | 0 |
| 4 | 2026-02-22T06:03:48.804308+00:00 | boxing | 20/21 | betfair | 0 |
| 7 | 2026-02-22T06:13:38.478921+00:00 | ice_hockey | 20/21 | betfair | 0 |
| 11 | 2026-02-22T06:24:38.280146+00:00 | ice_hockey | 20/21 | betfair | 0 |
| 12 | 2026-02-22T06:25:53.744217+00:00 | boxing | 20/21 | betfair | 0 |

Recovery example in the same live canary:
- Cycle 7 failed for `betfair`.
- Cycle 8 immediately returned to full success (`21/21`, no failures).

Result: one-bookmaker failure did not cancel or block other bookmaker execution.
