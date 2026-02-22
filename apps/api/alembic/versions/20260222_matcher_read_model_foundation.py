"""Add matcher read-model foundation tables

Revision ID: 20260222_matcher_rm
Revises: 20260222_refresh_acl
Create Date: 2026-02-22 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260222_matcher_rm"
down_revision: Union[str, Sequence[str], None] = "20260222_refresh_acl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "matcher_read_model_builds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("read_model_version", sa.String(length=80), nullable=False),
        sa.Column("builder_run_id", sa.String(length=80), nullable=False),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("source_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_max_odds_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_limit", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("event_batch_size", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("row_batch_size", sa.Integer(), nullable=False, server_default="250"),
        sa.Column("processed_events", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("upserted_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_stale_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("build_summary", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("read_model_version"),
    )
    op.create_index("ix_matcher_read_model_builds_id", "matcher_read_model_builds", ["id"], unique=False)
    op.create_index(
        "ix_matcher_read_model_builds_read_model_version",
        "matcher_read_model_builds",
        ["read_model_version"],
        unique=True,
    )
    op.create_index("ix_matcher_read_model_builds_builder_run_id", "matcher_read_model_builds", ["builder_run_id"], unique=False)
    op.create_index("ix_matcher_read_model_builds_built_at", "matcher_read_model_builds", ["built_at"], unique=False)
    op.create_index(
        "idx_matcher_rm_build_version_built",
        "matcher_read_model_builds",
        ["read_model_version", "built_at"],
        unique=False,
    )

    op.create_table(
        "matcher_read_model_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("build_id", sa.Integer(), nullable=False),
        sa.Column("read_model_version", sa.String(length=80), nullable=False),
        sa.Column("row_key", sa.String(length=120), nullable=False),
        sa.Column("builder_run_id", sa.String(length=80), nullable=False),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("market_id", sa.Integer(), nullable=False),
        sa.Column("selection_id", sa.Integer(), nullable=False),
        sa.Column("back_bookmaker_code", sa.String(length=30), nullable=False),
        sa.Column("rating", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("pnl_percentage", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["build_id"], ["matcher_read_model_builds.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("read_model_version", "row_key", name="uq_matcher_rm_version_row_key"),
    )
    op.create_index("ix_matcher_read_model_rows_id", "matcher_read_model_rows", ["id"], unique=False)
    op.create_index("ix_matcher_read_model_rows_build_id", "matcher_read_model_rows", ["build_id"], unique=False)
    op.create_index(
        "ix_matcher_read_model_rows_read_model_version",
        "matcher_read_model_rows",
        ["read_model_version"],
        unique=False,
    )
    op.create_index("ix_matcher_read_model_rows_builder_run_id", "matcher_read_model_rows", ["builder_run_id"], unique=False)
    op.create_index("ix_matcher_read_model_rows_built_at", "matcher_read_model_rows", ["built_at"], unique=False)
    op.create_index("ix_matcher_read_model_rows_event_id", "matcher_read_model_rows", ["event_id"], unique=False)
    op.create_index("ix_matcher_read_model_rows_market_id", "matcher_read_model_rows", ["market_id"], unique=False)
    op.create_index("ix_matcher_read_model_rows_selection_id", "matcher_read_model_rows", ["selection_id"], unique=False)
    op.create_index(
        "ix_matcher_read_model_rows_back_bookmaker_code",
        "matcher_read_model_rows",
        ["back_bookmaker_code"],
        unique=False,
    )
    op.create_index("ix_matcher_read_model_rows_last_updated", "matcher_read_model_rows", ["last_updated"], unique=False)
    op.create_index(
        "idx_matcher_rm_version_event",
        "matcher_read_model_rows",
        ["read_model_version", "event_id"],
        unique=False,
    )
    op.create_index(
        "idx_matcher_rm_version_market",
        "matcher_read_model_rows",
        ["read_model_version", "market_id"],
        unique=False,
    )
    op.create_index(
        "idx_matcher_rm_version_rating",
        "matcher_read_model_rows",
        ["read_model_version", "rating"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_matcher_rm_version_rating", table_name="matcher_read_model_rows")
    op.drop_index("idx_matcher_rm_version_market", table_name="matcher_read_model_rows")
    op.drop_index("idx_matcher_rm_version_event", table_name="matcher_read_model_rows")
    op.drop_index("ix_matcher_read_model_rows_last_updated", table_name="matcher_read_model_rows")
    op.drop_index("ix_matcher_read_model_rows_back_bookmaker_code", table_name="matcher_read_model_rows")
    op.drop_index("ix_matcher_read_model_rows_selection_id", table_name="matcher_read_model_rows")
    op.drop_index("ix_matcher_read_model_rows_market_id", table_name="matcher_read_model_rows")
    op.drop_index("ix_matcher_read_model_rows_event_id", table_name="matcher_read_model_rows")
    op.drop_index("ix_matcher_read_model_rows_built_at", table_name="matcher_read_model_rows")
    op.drop_index("ix_matcher_read_model_rows_builder_run_id", table_name="matcher_read_model_rows")
    op.drop_index("ix_matcher_read_model_rows_read_model_version", table_name="matcher_read_model_rows")
    op.drop_index("ix_matcher_read_model_rows_build_id", table_name="matcher_read_model_rows")
    op.drop_index("ix_matcher_read_model_rows_id", table_name="matcher_read_model_rows")
    op.drop_table("matcher_read_model_rows")

    op.drop_index("idx_matcher_rm_build_version_built", table_name="matcher_read_model_builds")
    op.drop_index("ix_matcher_read_model_builds_built_at", table_name="matcher_read_model_builds")
    op.drop_index("ix_matcher_read_model_builds_builder_run_id", table_name="matcher_read_model_builds")
    op.drop_index("ix_matcher_read_model_builds_read_model_version", table_name="matcher_read_model_builds")
    op.drop_index("ix_matcher_read_model_builds_id", table_name="matcher_read_model_builds")
    op.drop_table("matcher_read_model_builds")

