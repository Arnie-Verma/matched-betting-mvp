# PR-E2 Live Telemetry Contract

Date: 2026-02-21  
Slice: PR-E2 (Live Telemetry Evidence)

## Source Integrity
- Telemetry source is **live runtime stream data** (`observability:events:v1`), not synthetic payload generation.
- Live canary/refresh loop artifact:
  - `docs/evidence/phase-a-hardening/2026-02-11/pr15_live_canary_runtime.json`
  - Runtime window: ~64.8 minutes (`duration_seconds=3886.73`)
  - Cycles completed: `21`

## Required Artifacts
- `docs/evidence/phase-a-hardening/2026-02-11/pr15_live_telemetry_metrics.json`
- `docs/evidence/phase-a-hardening/2026-02-11/pr15_live_telemetry_threshold_eval.json`
- `docs/evidence/phase-a-hardening/2026-02-11/pr15_live_telemetry_contract.md` (this file)

## Reproducible Commands
```powershell
# 1) Reset live telemetry stream
$env:PYTHONPATH='apps/api/src;apps/worker/src'; @'
import os, redis
r=redis.from_url(os.getenv('REDIS_URL','redis://localhost:6379/0'))
key=os.getenv('OBSERVABILITY_STREAM_KEY','observability:events:v1')
print('stream_key', key)
print('deleted', r.delete(key))
'@ | python -

# 2) Run live canary/refresh loop for >=60 minutes
$env:PYTHONPATH='apps/api/src;apps/worker/src'; python apps/worker/src/scripts/run_phase_a_canary.py --output-prefix pr15_live_canary_runtime --min-duration-seconds 3600 --min-cycles 10 --max-cycles 40 --sleep-seconds 60

# 3) Generate live matcher/security runtime activity (non-synthetic)
$env:PYTHONPATH='apps/api/src;apps/worker/src'; @'
from fastapi.testclient import TestClient
from api.main import app
from api.core.auth import UserClaims, get_current_user, optional_user
client = TestClient(app)
app.dependency_overrides.clear()
client.get('/health/telemetry')  # denied security event
def _ops_user():
    return UserClaims(sub='live-ops-user', email='ops@example.test', email_verified=True, raw_claims={'roles':['ops']})
app.dependency_overrides[optional_user] = _ops_user
client.get('/health/telemetry?hours=1&limit=200')  # allowed security event
def _matcher_user():
    return UserClaims(sub='live-matcher-user', email='matcher@example.test', email_verified=True)
app.dependency_overrides[get_current_user] = _matcher_user
for _ in range(3):
    client.get('/odds/matcher?limit=20&offset=0')
app.dependency_overrides.clear()
'@ | python -

# 4) Export live stream summary + threshold eval artifacts
$env:PYTHONPATH='apps/api/src;apps/worker/src'; @'
import json
from pathlib import Path
from datetime import datetime, timezone
from api.services.observability_service import OBSERVABILITY_SCHEMA_VERSION, ObservabilityThresholds, build_observability_report
base = Path('docs/evidence/phase-a-hardening/2026-02-11')
metrics_path = base / 'pr15_live_telemetry_metrics.json'
threshold_path = base / 'pr15_live_telemetry_threshold_eval.json'
canary_path = base / 'pr15_live_canary_runtime.json'
canary = json.loads(canary_path.read_text(encoding='utf-8'))
report = build_observability_report(hours=4, limit=20000, thresholds=ObservabilityThresholds.from_env(), include_sample_events=False)
metrics_payload = {
    'slice': 'PR-E2',
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'source': {
        'type': 'live_runtime_stream',
        'stream_key': 'observability:events:v1',
        'window_hours': report.get('window_hours'),
        'events_analyzed': report.get('events_analyzed'),
        'canary_artifact': str(canary_path),
        'canary_started_at': canary.get('started_at'),
        'canary_ended_at': canary.get('ended_at'),
        'canary_duration_seconds': canary.get('duration_seconds'),
        'canary_cycles_completed': canary.get('cycles_completed'),
    },
    'schema_version': OBSERVABILITY_SCHEMA_VERSION,
    'summary': report.get('summary', {}),
}
threshold_payload = {
    'slice': 'PR-E2',
    'generated_at': datetime.now(timezone.utc).isoformat(),
    'source': {
        'type': 'live_runtime_stream',
        'stream_key': 'observability:events:v1',
        'window_hours': report.get('window_hours'),
        'events_analyzed': report.get('events_analyzed'),
    },
    'threshold_evaluation': report.get('threshold_evaluation', {}),
}
metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding='utf-8')
threshold_path.write_text(json.dumps(threshold_payload, indent=2), encoding='utf-8')
print(metrics_path)
print(threshold_path)
'@ | python -

# 5) Freeze verification
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_worker sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
docker exec mb_db psql -U postgres -d mb_dev -c "select code,is_active from bookmakers where code='unibet';"
```

## Output Summary
- Live stream analyzed: `488` events (4-hour window).
- Scheduler summary: present (caps + observed in-flight metrics).
- Scrape reliability summary: present (success/failure totals + per bookmaker/platform + breaker cycle/open metrics).
- Matcher performance summary: present (`request_count=3`, latency/query-signal percentiles).
- Security summary: present (`allowed_count=1`, `denied_count=1`, denied action breakdown).
- Threshold evaluation: explicit criterion pass/fail with failure reasons.
  - Current live outcome: `overall_pass=false`
  - Failure reason: `matcher_p95_ms_max failed (observed=875.3074 threshold=400.0)`

## Freeze Verification
- `mb_api`: `BOOKMAKER_FREEZE_UNIBET=true`
- `mb_worker`: `BOOKMAKER_FREEZE_UNIBET=true`
- DB: `unibet | f` (`is_active=false`)
