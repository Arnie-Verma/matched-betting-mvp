"""Add bookmaker lifecycle state enforcement tables and metadata

Revision ID: 20260222_lifecycle
Revises: ad28040a33b6
Create Date: 2026-02-22 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260222_lifecycle"
down_revision: Union[str, Sequence[str], None] = "ad28040a33b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add lifecycle columns to bookmaker registry.
    op.add_column(
        "bookmakers",
        sa.Column(
            "lifecycle_state",
            sa.String(length=40),
            nullable=True,
            server_default="backlog",
        ),
    )
    op.add_column(
        "bookmakers",
        sa.Column(
            "lifecycle_state_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column(
        "bookmakers",
        sa.Column("lifecycle_last_transition_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "bookmakers",
        sa.Column("lifecycle_last_transition_by", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "bookmakers",
        sa.Column("lifecycle_last_transition_reason", sa.Text(), nullable=True),
    )

    # Backfill lifecycle state from current active flag to preserve behavior.
    op.execute(
        """
        UPDATE bookmakers
        SET lifecycle_state = CASE WHEN is_active = true THEN 'active' ELSE 'backlog' END
        WHERE lifecycle_state IS NULL
        """
    )
    op.execute(
        """
        UPDATE bookmakers
        SET lifecycle_state_updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
        WHERE lifecycle_state_updated_at IS NULL
        """
    )

    op.alter_column("bookmakers", "lifecycle_state", nullable=False)
    op.alter_column("bookmakers", "lifecycle_state_updated_at", nullable=False)
    op.create_index(
        "idx_bookmakers_lifecycle_state",
        "bookmakers",
        ["lifecycle_state"],
        unique=False,
    )

    # Lifecycle transition audit trail.
    op.create_table(
        "bookmaker_lifecycle_transitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bookmaker_id", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.String(length=40), nullable=False),
        sa.Column("to_state", sa.String(length=40), nullable=False),
        sa.Column("transition_reason", sa.Text(), nullable=False),
        sa.Column("transition_metadata", sa.JSON(), nullable=True),
        sa.Column("transitioned_by", sa.String(length=120), nullable=True),
        sa.Column("transitioned_by_email", sa.String(length=255), nullable=True),
        sa.Column("transition_source", sa.String(length=50), nullable=False, server_default="api"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["bookmaker_id"], ["bookmakers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bookmaker_lifecycle_transitions_id",
        "bookmaker_lifecycle_transitions",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_bookmaker_lifecycle_transitions_bookmaker_id",
        "bookmaker_lifecycle_transitions",
        ["bookmaker_id"],
        unique=False,
    )
    op.create_index(
        "idx_bookmaker_lifecycle_transition_lookup",
        "bookmaker_lifecycle_transitions",
        ["bookmaker_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_bookmaker_lifecycle_transition_to_state",
        "bookmaker_lifecycle_transitions",
        ["to_state", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_bookmaker_lifecycle_transition_to_state", table_name="bookmaker_lifecycle_transitions")
    op.drop_index("idx_bookmaker_lifecycle_transition_lookup", table_name="bookmaker_lifecycle_transitions")
    op.drop_index("ix_bookmaker_lifecycle_transitions_bookmaker_id", table_name="bookmaker_lifecycle_transitions")
    op.drop_index("ix_bookmaker_lifecycle_transitions_id", table_name="bookmaker_lifecycle_transitions")
    op.drop_table("bookmaker_lifecycle_transitions")

    op.drop_index("idx_bookmakers_lifecycle_state", table_name="bookmakers")
    op.drop_column("bookmakers", "lifecycle_last_transition_reason")
    op.drop_column("bookmakers", "lifecycle_last_transition_by")
    op.drop_column("bookmakers", "lifecycle_last_transition_at")
    op.drop_column("bookmakers", "lifecycle_state_updated_at")
    op.drop_column("bookmakers", "lifecycle_state")
