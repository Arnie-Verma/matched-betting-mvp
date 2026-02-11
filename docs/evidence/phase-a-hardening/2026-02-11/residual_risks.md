# Residual risks and open issues (PR2)

1. Entain parity suite is still missing.
- `apps/worker/tests/test_entain_scraper.py` does not exist yet.
- Scheduled for PR5.

2. Live evidence currently reflects seeded/local development bookmaker set.
- Expected for local hardening but not representative of production bookmaker quality.
- Use canary runs (PR6) for trend-based evidence and breaker/latency correlation.

3. `SKIP`/`N_A` are neutral statuses.
- They correctly prevent false FAIL/WARN in no-eligible windows.
- They are not promotion evidence; eligible-window runs are still required for GO.
