# ADR-0021: Durable Refresh ACL and Audit Persistence

- Status: Accepted
- Date: 2026-02-22
- Owners: @api @worker

## Context
`GET /odds/refresh/status` access control was previously enforced from Redis payload fields (`requested_by`, `shared_user_ids`).
That model had two safety gaps:
1. ACL authority could be lost when Redis keys expired or on process/runtime churn.
2. ACL decisions and sharing changes were not durably auditable in Postgres.

For control-plane scale safety, refresh-job ownership/sharing/audit must be persisted and queryable.

## Decision
Implement durable DB-backed refresh ACL authority with backward compatibility:
1. Add durable models:
- `refresh_jobs`
- `refresh_job_acl_entries`
- `refresh_job_audit_events`
2. Add `RefreshJobAclService` for:
- durable job creation with owner ACL
- share/unshare ACL updates
- status access allow/deny decisions with reason codes
- audit event persistence for create/share/unshare/access decisions
- legacy payload backfill for pre-migration jobs
3. Enforce precedence rule in `/odds/refresh/status`:
- if durable refresh row exists: durable ACL is source of truth
- fallback to legacy Redis payload only for pre-migration jobs without durable row
4. Sync worker runtime status into durable refresh rows (best-effort, non-fatal).
5. Provide active/recent backfill utility:
- `python -m api.scripts.backfill_refresh_jobs_acl --hours 24`

## Consequences
Benefits:
- Refresh ACL authority survives Redis expiry/restart for durable jobs.
- ACL decisions and sharing history are queryable from Postgres.
- Cross-user status access is blocked by durable policy for new jobs.

Tradeoffs:
- Added DB writes on refresh create/share/status access paths.
- Temporary mixed-mode complexity during migration window.

Operational impact:
- Backfill should be run for active/recent jobs during rollout.
- Access investigations can query `refresh_job_audit_events`.

## Alternatives Considered
1. Keep Redis-only ACL with longer TTL:
- rejected; still non-durable and non-auditable.
2. Persist only owner and keep shared users in Redis:
- rejected; partial durability and weak audit story.
3. Replace Redis queue entirely in this slice:
- rejected as out-of-scope; durable ACL persistence was the required minimal change.

## Rollback
If production issues occur:
1. Revert API route to legacy payload ACL checks only.
2. Disable worker durable status sync by setting `REFRESH_JOB_DURABLE_SYNC_ENABLED=0`.
3. Keep new tables in place for forensic analysis (no destructive downgrade required).
4. Re-run API security regression suite before re-enable.

## Follow-ups
1. Add operator/admin endpoints for explicit share/unshare workflow (if product needs manual sharing).
2. Add retention policy for `refresh_job_audit_events`.
3. Add dashboard panels/alerts for abnormal ACL deny rates.
