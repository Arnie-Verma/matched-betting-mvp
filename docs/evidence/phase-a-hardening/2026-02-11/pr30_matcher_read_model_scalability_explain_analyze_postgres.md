# PR-M1cA Postgres Explain Analyze

- Date: 2026-02-24
- Backend: PostgreSQL (mb_dev)
- Dataset: 50,000 matcher_read_model_rows synthetic rows (single read_model_version)
- Request shape: supported read-model shape, limit=30, offsets=0/300/3000

## Count Query Plan
```text
Aggregate  (cost=4.31..4.32 rows=1 width=8) (actual time=24.815..24.816 rows=1 loops=1)
  Buffers: shared hit=6292
  ->  Index Scan using ix_matcher_read_model_rows_read_model_version on matcher_read_model_rows  (cost=0.29..4.31 rows=1 width=0) (actual time=0.018..20.654 rows=50000 loops=1)
        Index Cond: ((read_model_version)::text = 'pr30_postgres_benchmark_v1'::text)
        Filter: ((back_bookmaker_code)::text = ANY ('{ladbrokes,neds,betfair}'::text[]))
        Buffers: shared hit=6292
Planning Time: 0.106 ms
Execution Time: 24.838 ms
```

## Page Fetch Query Plan (offset=3000)
```text
Limit  (cost=4.32..4.33 rows=1 width=10) (actual time=37.777..37.784 rows=30 loops=1)
  Buffers: shared hit=6292
  ->  Sort  (cost=4.32..4.32 rows=1 width=10) (actual time=37.419..37.637 rows=3030 loops=1)
        Sort Key: pnl_percentage DESC, id
        Sort Method: top-N heapsort  Memory: 311kB
        Buffers: shared hit=6292
        ->  Index Scan using ix_matcher_read_model_rows_read_model_version on matcher_read_model_rows  (cost=0.29..4.31 rows=1 width=10) (actual time=0.026..23.793 rows=50000 loops=1)
              Index Cond: ((read_model_version)::text = 'pr30_postgres_benchmark_v1'::text)
              Filter: ((back_bookmaker_code)::text = ANY ('{ladbrokes,neds,betfair}'::text[]))
              Buffers: shared hit=6292
Planning Time: 0.180 ms
Execution Time: 37.814 ms
```

## Notes
- Query uses DB-side ORDER BY + LIMIT/OFFSET page fetch; no request-path full-table payload materialization.
- Index reference for serving path: idx_matcher_rm_version_bookmaker_pnl_id.
