# PR-M1c Read-Model Scalability Explain/Analyze

- Date: 2026-02-24
- Dataset: synthetic SQLite read-model with 50,000 rows
- Healthy supported shape: version + bookmaker_codes + ORDER BY pnl DESC,id ASC + LIMIT/OFFSET

## Count Query Plan (supported shape)
```text
(3, 0, 55, 'SEARCH matcher_read_model_rows USING COVERING INDEX idx_matcher_rm_version_bookmaker_pnl_id (read_model_version=? AND back_bookmaker_code=?)')
```

## Page Fetch Query Plan (supported shape)
```text
(7, 0, 55, 'SEARCH matcher_read_model_rows USING COVERING INDEX idx_matcher_rm_version_bookmaker_pnl_id (read_model_version=? AND back_bookmaker_code=?)')
(41, 0, 0, 'USE TEMP B-TREE FOR ORDER BY')
```

## Page Fetch Query Plan (with min_rating)
```text
(8, 0, 51, 'SEARCH matcher_read_model_rows USING INDEX idx_matcher_rm_version_rating (read_model_version=? AND rating>?)')
(29, 0, 0, 'USE TEMP B-TREE FOR ORDER BY')
```

## Notes
- Healthy supported-shape page query uses index `idx_matcher_rm_version_bookmaker_pnl_id` and applies SQL LIMIT/OFFSET.
- Request-path row materialization is bounded by requested limit (30).
- min_rating shape remains SQL-scalable (count + paged fetch), with index-assisted filtering.
