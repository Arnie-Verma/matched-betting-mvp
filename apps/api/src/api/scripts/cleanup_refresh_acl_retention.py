"""Cleanup utility for durable refresh ACL/audit retention policy."""
from __future__ import annotations

import argparse
import json

from api.core.database import SessionLocal
from api.services.refresh_acl_retention_service import (
    RefreshAclRetentionConfig,
    load_refresh_acl_retention_config_from_env,
    run_refresh_acl_retention,
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

    db = SessionLocal()
    try:
        summary = run_refresh_acl_retention(
            db,
            config=config,
            dry_run=not bool(args.execute),
        )
    finally:
        db.close()

    print(json.dumps(summary.to_dict(), indent=2))


if __name__ == "__main__":
    main()
