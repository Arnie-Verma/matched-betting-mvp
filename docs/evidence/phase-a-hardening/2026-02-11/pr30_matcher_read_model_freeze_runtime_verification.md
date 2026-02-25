# PR-M1cA Freeze Runtime Verification

- Date: 2026-02-24
- Runtime stack: Docker compose (`mb_api`, `mb_worker`, `mb_db`, `mb_redis`)

## Verification Commands
1. `docker exec mb_api printenv BOOKMAKER_FREEZE_UNIBET`
2. `docker exec mb_worker printenv BOOKMAKER_FREEZE_UNIBET`
3. `docker exec mb_db psql -U postgres -d mb_dev -At -c "SELECT code || ',' || is_active::text FROM bookmakers WHERE code='unibet';"`

## Results
- API env `BOOKMAKER_FREEZE_UNIBET`: `true`
- Worker env `BOOKMAKER_FREEZE_UNIBET`: `true`
- DB row `bookmakers(code='unibet').is_active`: `unibet,false`

## Conclusion
- Freeze flag is enabled in both API and worker runtime environments.
- Unibet remains non-active in DB (`is_active=false`).
