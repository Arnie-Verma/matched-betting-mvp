# PR4 Market Hygiene DB Query Outputs

## Scope Query (current matcher markets, Entain + Punterstech, priority competitions)
```sql
SELECT b.code AS bookmaker_code,
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

Competition filtering was applied via `normalize_competition_name(...)` in the evidence script to scope to: `epl`, `nba`, `nhl`, `boxing`, `nbl`.

## One-time Cleanup Query (retire stale invalid current rows)
```sql
UPDATE odds_snapshots
SET is_current = FALSE
WHERE id = ANY(:ids);
```
`ids` were generated from current rows in the scope above when any condition was true:
- market name matched disallowed futures/outright/partial token set
- `selection_key` not in `home/away/draw`
- market shape != expected (`home,draw,away` for `epl`; `home,away` for `nba/nhl/boxing/nbl`)

## Before/After Output (from query results)

| Competition | Before disallowed groups | After disallowed groups | Before invalid keys | After invalid keys | Before shape mismatch groups | After shape mismatch groups |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| boxing | 0 | 0 | 0 | 0 | 18 | 0 |
| epl | 0 | 0 | 2 | 0 | 70 | 0 |
| nba | 2 | 0 | 2 | 0 | 20 | 0 |
| nbl | 0 | 0 | 0 | 0 | 37 | 0 |
| nhl | 10 | 0 | 12 | 0 | 30 | 0 |
| TOTAL | 12 | 0 | 16 | 0 | 175 | 0 |

- Critical anomalies: before `175`, after `0`
