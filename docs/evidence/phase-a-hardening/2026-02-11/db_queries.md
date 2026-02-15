# DB evidence queries

## PR2 note
- Live DB validation outputs were generated in Docker context (see `commands.txt`).

## PR4 market-hygiene queries

1. Current matcher-market scope extraction (Entain + Punterstech):
```sql
SELECT
  os.id AS odds_snapshot_id,
  b.code AS bookmaker_code,
  b.scraping_config->>'scraper_class' AS scraper_class,
  c.name AS competition_name,
  e.id AS event_id,
  m.id AS market_id,
  m.name AS market_name,
  s.selection_key
FROM odds_snapshots os
JOIN selections s ON s.id = os.selection_id
JOIN markets m ON m.id = s.market_id
JOIN events e ON e.id = m.event_id
JOIN competitions c ON c.id = e.competition_id
JOIN bookmakers b ON b.id = os.bookmaker_id
WHERE os.is_current = TRUE
  AND m.market_type = 'match_winner'
  AND (b.scraping_config->>'scraper_class') IN ('entain', 'punterstech');
```

2. One-time stale-row cleanup update:
```sql
UPDATE odds_snapshots
SET is_current = FALSE
WHERE id = ANY(:ids);
```

Selection of `:ids` was driven by query result evaluation for priority competitions
(`epl`, `nba`, `nhl`, `boxing`, `nbl`) when any of the following was true:
- disallowed market token match (futures/outright/partial)
- invalid `selection_key` (not `home/away/draw`)
- invalid expected market shape (`home,draw,away` for `epl`; `home,away` for `nba/nhl/boxing/nbl`)

3. Query outputs:
- `market_hygiene_before_pr4.json`
- `market_hygiene_after_pr4.json`
- `market_hygiene_mismatch_summary_pr4.json`
- `market_hygiene_db_query_outputs_pr4.md`

## PR6.1 validation/canary query outputs

DB-backed supporting queries (event-count and freeze-state checks) are captured in:
- `pr6_1_db_query_outputs.md`

Includes:
1. EPL current `match_winner` event counts by bookmaker
2. Boxing current `match_winner` event counts by bookmaker
3. NBL current `match_winner` event counts for out-of-scope policy candidates
4. Unibet freeze status check (`bookmakers.is_active = false`)

## PR7 validation/canary query outputs

DB-backed supporting queries for PR7 remediation and gate rerun are captured in:
- `pr7_db_query_outputs.md`

Includes:
1. EPL current `match_winner` event counts by bookmaker after Punterstech EPL hardening
2. Boxing current `match_winner` event counts by bookmaker for in-scope/out-of-scope policy review
3. Unibet freeze status check (`bookmakers.is_active = false`)
