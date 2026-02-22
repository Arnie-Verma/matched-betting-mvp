"""Add rollout control policy tables for scheduler selection

Revision ID: 20260222_rollout_control
Revises: 20260222_evidence_registry
Create Date: 2026-02-22 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260222_rollout_control"
down_revision: Union[str, Sequence[str], None] = "20260222_evidence_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_rollout_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("platform_code", sa.String(length=40), nullable=False),
        sa.Column("rollout_mode", sa.String(length=20), nullable=False, server_default="full"),
        sa.Column("kill_switch_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sport_cohort", sa.JSON(), nullable=True),
        sa.Column("competition_cohort", sa.JSON(), nullable=True),
        sa.Column("bookmaker_cohort", sa.JSON(), nullable=True),
        sa.Column("policy_metadata", sa.JSON(), nullable=True),
        sa.Column("updated_by", sa.String(length=120), nullable=True),
        sa.Column("updated_by_email", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform_code"),
    )
    op.create_index("ix_platform_rollout_policies_id", "platform_rollout_policies", ["id"], unique=False)
    op.create_index(
        "ix_platform_rollout_policies_platform_code",
        "platform_rollout_policies",
        ["platform_code"],
        unique=True,
    )
    op.create_index(
        "idx_platform_rollout_policy_lookup",
        "platform_rollout_policies",
        ["platform_code", "updated_at"],
        unique=False,
    )

    op.create_table(
        "bookmaker_rollout_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bookmaker_id", sa.Integer(), nullable=False),
        sa.Column("bookmaker_code", sa.String(length=30), nullable=False),
        sa.Column("rollout_mode", sa.String(length=20), nullable=False, server_default="full"),
        sa.Column("kill_switch_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sport_cohort", sa.JSON(), nullable=True),
        sa.Column("competition_cohort", sa.JSON(), nullable=True),
        sa.Column("bookmaker_cohort", sa.JSON(), nullable=True),
        sa.Column("policy_metadata", sa.JSON(), nullable=True),
        sa.Column("updated_by", sa.String(length=120), nullable=True),
        sa.Column("updated_by_email", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["bookmaker_id"], ["bookmakers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bookmaker_id"),
        sa.UniqueConstraint("bookmaker_code"),
    )
    op.create_index("ix_bookmaker_rollout_policies_id", "bookmaker_rollout_policies", ["id"], unique=False)
    op.create_index(
        "ix_bookmaker_rollout_policies_bookmaker_id",
        "bookmaker_rollout_policies",
        ["bookmaker_id"],
        unique=True,
    )
    op.create_index(
        "ix_bookmaker_rollout_policies_bookmaker_code",
        "bookmaker_rollout_policies",
        ["bookmaker_code"],
        unique=True,
    )
    op.create_index(
        "idx_bookmaker_rollout_policy_lookup",
        "bookmaker_rollout_policies",
        ["bookmaker_code", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_bookmaker_rollout_policy_lookup", table_name="bookmaker_rollout_policies")
    op.drop_index("ix_bookmaker_rollout_policies_bookmaker_code", table_name="bookmaker_rollout_policies")
    op.drop_index("ix_bookmaker_rollout_policies_bookmaker_id", table_name="bookmaker_rollout_policies")
    op.drop_index("ix_bookmaker_rollout_policies_id", table_name="bookmaker_rollout_policies")
    op.drop_table("bookmaker_rollout_policies")

    op.drop_index("idx_platform_rollout_policy_lookup", table_name="platform_rollout_policies")
    op.drop_index("ix_platform_rollout_policies_platform_code", table_name="platform_rollout_policies")
    op.drop_index("ix_platform_rollout_policies_id", table_name="platform_rollout_policies")
    op.drop_table("platform_rollout_policies")
