# PR6.1 DB Query Outputs

## Query 1: EPL current match_winner event counts by bookmaker
```sql
SELECT b.code AS bookmaker, COUNT(DISTINCT e.id) AS event_count
FROM odds_snapshots os
JOIN selections s ON s.id = os.selection_id
JOIN markets m ON m.id = s.market_id
JOIN events e ON e.id = m.event_id
JOIN competitions c ON c.id = e.competition_id
JOIN bookmakers b ON b.id = os.bookmaker_id
WHERE os.is_current = TRUE
  AND m.market_type = 'match_winner'
  AND lower(c.name) LIKE '%premier league%'
GROUP BY b.code
ORDER BY b.code;
```

   bookmaker   | event_count 
---------------+-------------
 betblitz      |          48
 betbuzz       |         168
 betchamps     |          49
 betfair       |          20
 betfocus      |          60
 betreal       |          28
 betvista      |         168
 blondebet     |          37
 cashcage      |          69
 ladbrokes     |          47
 lightningbet  |          68
 millennialbet |          41
 mintbet       |         168
 neds          |          47
 ripperbet     |         168
 starsports    |          53
 teambet       |         124
 topbet        |          60
 tradiebet     |          33
 truebet       |          51
 unibet        |          22
 wizbet        |          30
(22 rows)


## Query 2: Boxing current match_winner event counts by bookmaker
```sql
SELECT b.code AS bookmaker, COUNT(DISTINCT e.id) AS event_count
FROM odds_snapshots os
JOIN selections s ON s.id = os.selection_id
JOIN markets m ON m.id = s.market_id
JOIN events e ON e.id = m.event_id
JOIN competitions c ON c.id = e.competition_id
JOIN bookmakers b ON b.id = os.bookmaker_id
WHERE os.is_current = TRUE
  AND m.market_type = 'match_winner'
  AND lower(c.name) LIKE '%boxing%'
GROUP BY b.code
ORDER BY b.code;
```

   bookmaker   | event_count 
---------------+-------------
 betblitz      |           3
 betbuzz       |           3
 betchamps     |           3
 betfair       |          42
 betfocus      |           3
 betreal       |           3
 betvista      |           3
 blondebet     |           3
 cashcage      |           3
 lightningbet  |           3
 millennialbet |           3
 mintbet       |           3
 ripperbet     |           3
 starsports    |           3
 teambet       |           3
 topbet        |           3
 tradiebet     |           3
 truebet       |           3
 unibet        |          24
 wizbet        |           3
(20 rows)


## Query 3: NBL current match_winner event counts for out-of-scope policy candidates
```sql
SELECT b.code AS bookmaker, COUNT(DISTINCT e.id) AS event_count
FROM odds_snapshots os
JOIN selections s ON s.id = os.selection_id
JOIN markets m ON m.id = s.market_id
JOIN events e ON e.id = m.event_id
JOIN competitions c ON c.id = e.competition_id
JOIN bookmakers b ON b.id = os.bookmaker_id
WHERE os.is_current = TRUE
  AND m.market_type = 'match_winner'
  AND lower(c.name) LIKE '%nbl%'
  AND b.code IN ('betblitz', 'starsports', 'truebet', 'wizbet')
GROUP BY b.code
ORDER BY b.code;
```

 bookmaker | event_count 
-----------+-------------
(0 rows)


## Query 4: Unibet freeze status
```sql
SELECT code, is_active
FROM bookmakers
WHERE code = 'unibet';
```

  code  | is_active 
--------+-----------
 unibet | f
(1 row)

