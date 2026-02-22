"""Add durable refresh job ACL and audit persistence

Revision ID: 20260222_refresh_acl
Revises: 20260222_rollout_control
Create Date: 2026-02-22 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260222_refresh_acl"
down_revision: Union[str, Sequence[str], None] = "20260222_rollout_control"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="redis_queue_v1"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index("ix_refresh_jobs_id", "refresh_jobs", ["id"], unique=False)
    op.create_index("ix_refresh_jobs_job_id", "refresh_jobs", ["job_id"], unique=True)
    op.create_index("ix_refresh_jobs_owner_user_id", "refresh_jobs", ["owner_user_id"], unique=False)
    op.create_index("ix_refresh_jobs_status", "refresh_jobs", ["status"], unique=False)
    op.create_index("idx_refresh_jobs_owner_created", "refresh_jobs", ["owner_user_id", "created_at"], unique=False)
    op.create_index("idx_refresh_jobs_status_updated", "refresh_jobs", ["status", "updated_at"], unique=False)

    op.create_table(
        "refresh_job_acl_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("refresh_job_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("access_type", sa.String(length=20), nullable=False, server_default="read"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("granted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("grant_reason", sa.String(length=120), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["refresh_job_id"], ["refresh_jobs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_job_id", "user_id", "access_type", name="uq_refresh_job_acl_entry"),
    )
    op.create_index("ix_refresh_job_acl_entries_id", "refresh_job_acl_entries", ["id"], unique=False)
    op.create_index("ix_refresh_job_acl_entries_refresh_job_id", "refresh_job_acl_entries", ["refresh_job_id"], unique=False)
    op.create_index("ix_refresh_job_acl_entries_user_id", "refresh_job_acl_entries", ["user_id"], unique=False)
    op.create_index("ix_refresh_job_acl_entries_is_active", "refresh_job_acl_entries", ["is_active"], unique=False)
    op.create_index(
        "idx_refresh_job_acl_lookup",
        "refresh_job_acl_entries",
        ["refresh_job_id", "is_active", "user_id"],
        unique=False,
    )

    op.create_table(
        "refresh_job_audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("refresh_job_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=True),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_sub", sa.String(length=120), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["refresh_job_id"], ["refresh_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refresh_job_audit_events_id", "refresh_job_audit_events", ["id"], unique=False)
    op.create_index("ix_refresh_job_audit_events_job_id", "refresh_job_audit_events", ["job_id"], unique=False)
    op.create_index("ix_refresh_job_audit_events_refresh_job_id", "refresh_job_audit_events", ["refresh_job_id"], unique=False)
    op.create_index("ix_refresh_job_audit_events_created_at", "refresh_job_audit_events", ["created_at"], unique=False)
    op.create_index(
        "idx_refresh_job_audit_lookup",
        "refresh_job_audit_events",
        ["refresh_job_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_refresh_job_audit_action",
        "refresh_job_audit_events",
        ["action_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_refresh_job_audit_action", table_name="refresh_job_audit_events")
    op.drop_index("idx_refresh_job_audit_lookup", table_name="refresh_job_audit_events")
    op.drop_index("ix_refresh_job_audit_events_created_at", table_name="refresh_job_audit_events")
    op.drop_index("ix_refresh_job_audit_events_refresh_job_id", table_name="refresh_job_audit_events")
    op.drop_index("ix_refresh_job_audit_events_job_id", table_name="refresh_job_audit_events")
    op.drop_index("ix_refresh_job_audit_events_id", table_name="refresh_job_audit_events")
    op.drop_table("refresh_job_audit_events")

    op.drop_index("idx_refresh_job_acl_lookup", table_name="refresh_job_acl_entries")
    op.drop_index("ix_refresh_job_acl_entries_is_active", table_name="refresh_job_acl_entries")
    op.drop_index("ix_refresh_job_acl_entries_user_id", table_name="refresh_job_acl_entries")
    op.drop_index("ix_refresh_job_acl_entries_refresh_job_id", table_name="refresh_job_acl_entries")
    op.drop_index("ix_refresh_job_acl_entries_id", table_name="refresh_job_acl_entries")
    op.drop_table("refresh_job_acl_entries")

    op.drop_index("idx_refresh_jobs_status_updated", table_name="refresh_jobs")
    op.drop_index("idx_refresh_jobs_owner_created", table_name="refresh_jobs")
    op.drop_index("ix_refresh_jobs_status", table_name="refresh_jobs")
    op.drop_index("ix_refresh_jobs_owner_user_id", table_name="refresh_jobs")
    op.drop_index("ix_refresh_jobs_job_id", table_name="refresh_jobs")
    op.drop_index("ix_refresh_jobs_id", table_name="refresh_jobs")
    op.drop_table("refresh_jobs")
