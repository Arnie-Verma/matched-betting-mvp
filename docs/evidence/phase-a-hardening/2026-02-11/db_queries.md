# DB evidence queries (PR2)

No database evidence queries were successfully executed in this shell context.

Reason:
- `DATABASE_URL` resolves to docker network host `db`.
- Current runtime could not reach that host, and docker daemon access was unavailable/timeouting from this shell.

Planned queries once DB connectivity is available:

1. Eligible reference fixture shape audit (per competition):
```sql
SELECT
  b.code AS bookmaker,
  c.name AS competition,
  e.id AS event_id,
  e.name AS event_name,
  COUNT(DISTINCT lower(s.selection_key)) AS selection_key_count,
  ARRAY_AGG(DISTINCT lower(s.selection_key)) AS selection_keys
FROM odds_snapshots os
JOIN bookmakers b ON b.id = os.bookmaker_id
JOIN selections s ON s.id = os.selection_id
JOIN markets m ON m.id = s.market_id
JOIN events e ON e.id = m.event_id
JOIN competitions c ON c.id = e.competition_id
WHERE os.is_current = true
  AND m.market_type = 'match_winner'
  AND b.code = 'ladbrokes'
GROUP BY b.code, c.name, e.id, e.name
ORDER BY c.name, e.name;
```

2. Cross-bookmaker eligible overlap check (Entain vs Punterstech examples):
```sql
SELECT
  c.name AS competition,
  COUNT(DISTINCT CASE WHEN b.code='ladbrokes' THEN e.id END) AS ladbrokes_events,
  COUNT(DISTINCT CASE WHEN b.code='mintbet' THEN e.id END) AS mintbet_events
FROM odds_snapshots os
JOIN bookmakers b ON b.id = os.bookmaker_id
JOIN selections s ON s.id = os.selection_id
JOIN markets m ON m.id = s.market_id
JOIN events e ON e.id = m.event_id
JOIN competitions c ON c.id = e.competition_id
WHERE os.is_current = true
  AND m.market_type = 'match_winner'
  AND b.code IN ('ladbrokes', 'mintbet')
GROUP BY c.name
ORDER BY c.name;
```
