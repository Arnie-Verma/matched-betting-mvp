"""Cleanup utility for durable refresh ACL/audit retention policy."""
from __future__ import annotations

import argparse
import json

from api.services.refresh_acl_retention_automation_service import run_refresh_acl_retention_schedule
from api.services.refresh_acl_retention_service import (
    RefreshAclRetentionConfig,
    RefreshAclRetentionGuardrailConfig,
    load_refresh_acl_retention_config_from_env,
    load_refresh_acl_retention_guardrail_config_from_env,
)


def _parse_statuses(raw: str | None, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if not raw:
        return fallback
    statuses: list[str] = []
    for item in raw.split(","):
        value = (item or "").strip().lower()
        if value and value not in statuses:
            statuses.append(value)
    return tuple(statuses) if statuses else fallback


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup durable refresh ACL/audit rows with retention policy")
    parser.add_argument("--audit-retention-days", type=int, default=None)
    parser.add_argument("--terminal-job-retention-days", type=int, default=None)
    parser.add_argument("--terminal-statuses", type=str, default=None)
    parser.add_argument("--max-delete-terminal-jobs", type=int, default=None)
    parser.add_argument("--max-delete-audit-rows", type=int, default=None)
    parser.add_argument("--max-delete-acl-rows", type=int, default=None)
    parser.add_argument("--allow-cap-breach", action="store_true")
    parser.add_argument("--lock-key", type=str, default=None)
    parser.add_argument("--lock-ttl-seconds", type=int, default=None)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute deletes. Default is dry-run only.",
    )
    args = parser.parse_args()

    env_config = load_refresh_acl_retention_config_from_env()
    config = RefreshAclRetentionConfig(
        audit_retention_days=(
            int(args.audit_retention_days)
            if isinstance(args.audit_retention_days, int) and int(args.audit_retention_days) > 0
            else int(env_config.audit_retention_days)
        ),
        terminal_job_retention_days=(
            int(args.terminal_job_retention_days)
            if isinstance(args.terminal_job_retention_days, int) and int(args.terminal_job_retention_days) > 0
            else int(env_config.terminal_job_retention_days)
        ),
        terminal_statuses=_parse_statuses(args.terminal_statuses, env_config.terminal_statuses),
        now=env_config.now,
    )
    env_guardrails = load_refresh_acl_retention_guardrail_config_from_env()
    guardrails = RefreshAclRetentionGuardrailConfig(
        max_delete_terminal_jobs=(
            int(args.max_delete_terminal_jobs)
            if isinstance(args.max_delete_terminal_jobs, int) and int(args.max_delete_terminal_jobs) > 0
            else int(env_guardrails.max_delete_terminal_jobs)
        ),
        max_delete_audit_rows=(
            int(args.max_delete_audit_rows)
            if isinstance(args.max_delete_audit_rows, int) and int(args.max_delete_audit_rows) > 0
            else int(env_guardrails.max_delete_audit_rows)
        ),
        max_delete_acl_rows=(
            int(args.max_delete_acl_rows)
            if isinstance(args.max_delete_acl_rows, int) and int(args.max_delete_acl_rows) > 0
            else int(env_guardrails.max_delete_acl_rows)
        ),
        allow_cap_breach=False,
    )

    report = run_refresh_acl_retention_schedule(
        max_runs=1,
        interval_seconds=0,
        dry_run=not bool(args.execute),
        runner_kwargs={
            "retention_config": config,
            "guardrail_config": guardrails,
            "allow_cap_breach_override": bool(args.allow_cap_breach),
            "lock_key": args.lock_key,
            "lock_ttl_seconds": (
                int(args.lock_ttl_seconds)
                if isinstance(args.lock_ttl_seconds, int) and int(args.lock_ttl_seconds) > 0
                else None
            ),
        },
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
