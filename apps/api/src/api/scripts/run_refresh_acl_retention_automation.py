"""Automated runner for refresh ACL/audit retention cleanup with lock + guardrails."""
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


def _positive_int_or(default_value: int, candidate: int | None) -> int:
    if isinstance(candidate, int) and candidate > 0:
        return int(candidate)
    return int(default_value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run automated refresh ACL retention cleanup")
    parser.add_argument("--execute", action="store_true", help="Execute deletes; default is dry-run")
    parser.add_argument("--max-runs", type=int, default=1, help="Number of scheduled runs in this invocation")
    parser.add_argument("--interval-seconds", type=int, default=0, help="Seconds between scheduled runs")

    parser.add_argument("--audit-retention-days", type=int, default=None)
    parser.add_argument("--terminal-job-retention-days", type=int, default=None)
    parser.add_argument("--terminal-statuses", type=str, default=None)

    parser.add_argument("--max-delete-terminal-jobs", type=int, default=None)
    parser.add_argument("--max-delete-audit-rows", type=int, default=None)
    parser.add_argument("--max-delete-acl-rows", type=int, default=None)
    parser.add_argument("--allow-cap-breach", action="store_true")

    parser.add_argument("--lock-key", type=str, default=None)
    parser.add_argument("--lock-ttl-seconds", type=int, default=None)

    args = parser.parse_args()

    env_retention = load_refresh_acl_retention_config_from_env()
    retention_config = RefreshAclRetentionConfig(
        audit_retention_days=_positive_int_or(env_retention.audit_retention_days, args.audit_retention_days),
        terminal_job_retention_days=_positive_int_or(
            env_retention.terminal_job_retention_days,
            args.terminal_job_retention_days,
        ),
        terminal_statuses=_parse_statuses(args.terminal_statuses, env_retention.terminal_statuses),
        now=env_retention.now,
    )

    env_guardrails = load_refresh_acl_retention_guardrail_config_from_env()
    guardrail_config = RefreshAclRetentionGuardrailConfig(
        max_delete_terminal_jobs=_positive_int_or(env_guardrails.max_delete_terminal_jobs, args.max_delete_terminal_jobs),
        max_delete_audit_rows=_positive_int_or(env_guardrails.max_delete_audit_rows, args.max_delete_audit_rows),
        max_delete_acl_rows=_positive_int_or(env_guardrails.max_delete_acl_rows, args.max_delete_acl_rows),
        allow_cap_breach=bool(args.allow_cap_breach or env_guardrails.allow_cap_breach),
    )

    report = run_refresh_acl_retention_schedule(
        max_runs=max(1, int(args.max_runs)),
        interval_seconds=max(0, int(args.interval_seconds)),
        dry_run=not bool(args.execute),
        runner_kwargs={
            "retention_config": retention_config,
            "guardrail_config": guardrail_config,
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
