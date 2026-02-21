# PR8 Runtime Freeze Verification

Date executed: 2026-02-21
Scope: PR-F1 freeze baseline lock + doc consistency (no Unibet activation work)

## 1) Docker runtime freeze flag pin

Command:

```bash
docker compose -f infra/dev/docker-compose.yml up -d api worker
docker exec mb_api sh -lc 'echo BOOKMAKER_FREEZE_UNIBET=$BOOKMAKER_FREEZE_UNIBET'
```

Output:

```text
BOOKMAKER_FREEZE_UNIBET=true
```

## 2) DB baseline: `unibet.is_active=false`

Command:

```bash
docker exec mb_db psql -U postgres -d mb_dev -c "SELECT code, is_active FROM bookmakers WHERE code = 'unibet';"
```

Output:

```text
  code  | is_active
--------+-----------
 unibet | f
(1 row)
```

## 3) Plan exposure freeze enforcement

Command:

```powershell
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_bookmaker_freeze.py -q
```

Result:

```text
6 passed
```

Coverage notes:
- verifies default freeze-on and env-override behavior
- verifies `SubscriptionService.get_allowed_bookmakers` excludes `unibet` for `free`, `premium`, and `diamond` while frozen

## 4) Worker active selection freeze enforcement

Command:

```powershell
$env:PYTHONPATH='apps/api/src;apps/worker/src'; pytest apps/api/tests/test_unibet_freeze_integration.py -q
```

Result:

```text
1 passed
```

Coverage notes:
- verifies metadata exposure excludes `unibet` while frozen
- verifies `ScrapeService.get_active_bookmakers_from_db()` excludes `unibet` while frozen

## 5) Doc consistency sweep

Command:

```bash
rg -n "ready to activate|Enable Unibet in DB|is_active=true.*unibet|activate Unibet now|Unibet is implemented and active|Unibet/Kindred is now \\*\\*active\\*\\*" Unibet.md BOOKMAKER_IMPLEMENTATION_GUIDE.md DISCOVERY_SUMMARY.md VALIDATION_FRAMEWORK.md
```

Result:
- No "activate now" contradictions found in targeted docs after PR-F1 updates.
